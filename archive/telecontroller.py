#!/data/data/com.termux/files/usr/bin/python3
# FILE: tools/telecontroller.py
# PURPOSE: Single-instance Telegram controller (polling + buttons), ASCII-only output.

import os
import sys
import time
import json
import signal
import urllib.request
import urllib.parse
import subprocess
import datetime

HOME  = os.path.expanduser("~")
ROOT  = os.path.join(HOME, "BotA")
TOOLS = os.path.join(ROOT, "tools")
CACHE = os.path.join(ROOT, "cache")
LOGS  = os.path.join(ROOT, "logs")
CONF  = os.path.join(ROOT, "config", "strategy.env")

OFFSET_FILE = os.path.join(CACHE, "tele.offset")
START_FILE  = os.path.join(CACHE, "telecontroller.started")

os.makedirs(CACHE, exist_ok=True)
os.makedirs(LOGS,  exist_ok=True)

# -------------------------------
# Config / ENV
# -------------------------------
def load_env_file(path):
    cfg = {}
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    cfg[k.strip()] = v.strip().strip('"').strip("'")
        except Exception:
            pass
    return cfg

CFG = load_env_file(CONF)
TOKEN = os.environ.get("TELEGRAM_TOKEN") or CFG.get("TELEGRAM_TOKEN")
CHAT_ID_ALLOWED = os.environ.get("TELEGRAM_CHAT_ID") or CFG.get("TELEGRAM_CHAT_ID")
ALLOWED_CHAT_IDS = set()
if CHAT_ID_ALLOWED:
    try:
        ALLOWED_CHAT_IDS.add(int(CHAT_ID_ALLOWED))
    except Exception:
        pass

if not TOKEN:
    print("[telecontroller] ERROR: TELEGRAM_TOKEN missing", flush=True)
    sys.exit(1)

API_BASE = f"https://api.telegram.org/bot{TOKEN}"

# -------------------------------
# HTTP helpers
# -------------------------------
def http_get(path, params=None, timeout=25):
    qs = "?" + urllib.parse.urlencode(params) if params else ""
    req = urllib.request.Request(API_BASE + path + qs)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))

def http_post(path, data, timeout=25):
    body = urllib.parse.urlencode(data).encode("utf-8")
    req = urllib.request.Request(API_BASE + path, data=body)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))

def send_msg(chat_id, text, parse_mode="Markdown", reply_markup=None):
    try:
        payload = {
            "chat_id": str(chat_id),
            "text": text[:4000],
            "parse_mode": parse_mode
        }
        if reply_markup:
            payload["reply_markup"] = json.dumps(reply_markup)
        return http_post("/sendMessage", payload)
    except Exception as e:
        print(f"[send_msg] error: {e}", flush=True)

# -------------------------------
# Files
# -------------------------------
def write_int_file(path, val):
    try:
        with open(path, "w") as f:
            f.write(str(int(val)))
    except Exception:
        pass

def read_int_file(path):
    try:
        with open(path, "r") as f:
            c = f.read().strip()
        return int(c) if c.isdigit() else None
    except Exception:
        return None

# -------------------------------
# Bot status helpers
# -------------------------------
def heartbeat_age():
    hb = os.path.join(CACHE, "watcher.heartbeat")
    try:
        with open(hb, "r") as f:
            c = f.read().strip()
        if not c or not c.isdigit():
            return None
        return max(0, int(time.time()) - int(c))
    except Exception:
        return None

def market_phase():
    cmd = os.path.join(TOOLS, "market_open.sh")
    if not os.path.isfile(cmd):
        return "Unknown"
    try:
        out = subprocess.check_output(
            ["bash", cmd],
            stderr=subprocess.DEVNULL,
            timeout=8
        ).decode().strip().splitlines()
        last = out[-1].strip() if out else "Unknown"
        return last if last in ("Open", "Closed", "Unknown") else "Unknown"
    except Exception:
        return "Unknown"

def digest_last_hour():
    path = os.path.join(LOGS, "alerts.csv")
    counts = {"BUY": 0, "SELL": 0, "HOLD": 0}
    if not os.path.isfile(path):
        return counts
    cutoff = time.time() - 3600
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
        if len(lines) <= 1:
            return counts
        for line in lines[1:]:
            if not line.strip():
                continue
            parts = line.strip().split(",")
            if len(parts) < 4:
                continue
            ts_str = parts[0].replace("Z", "+00:00")
            try:
                ts = int(datetime.datetime.fromisoformat(ts_str).timestamp())
                if ts < cutoff:
                    continue
            except Exception:
                continue
            verdict = parts[2].strip().upper()
            if verdict in counts:
                counts[verdict] += 1
    except Exception:
        pass
    return counts

def format_daily_report():
    path = os.path.join(LOGS, "alerts.csv")
    if not os.path.isfile(path):
        return "Daily Report\nNo data available."
    cutoff = time.time() - 86400
    data = {}
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
        if len(lines) <= 1:
            return "Daily Report\nNo rows in alerts.csv."
        for line in lines[1:]:
            if not line.strip():
                continue
            parts = line.strip().split(",")
            # Expected: ts, pair, verdict, timeframe, price, ...
            if len(parts) < 5:
                continue
            ts_str = parts[0].replace("Z", "+00:00")
            try:
                ts = int(datetime.datetime.fromisoformat(ts_str).timestamp())
                if ts < cutoff:
                    continue
            except Exception:
                continue
            pair    = parts[1].strip()
            verdict = parts[2].strip().upper()
            price   = parts[4].strip() if len(parts) > 4 else "N/A"
            if pair not in data:
                data[pair] = {"total": 0, "BUY": 0, "SELL": 0, "HOLD": 0, "last_price": price, "last_time": ts}
            data[pair]["total"] += 1
            if verdict in ("BUY", "SELL", "HOLD"):
                data[pair][verdict] += 1
            data[pair]["last_price"] = price
            data[pair]["last_time"]  = ts
    except Exception as e:
        return f"Daily Report\nError: {e}"

    lines = []
    lines.append("Daily Report (24h)")
    lines.append("------------------")
    for pair in sorted(data.keys()):
        d = data[pair]
        bias = "BUY" if d["BUY"] > d["SELL"] else ("SELL" if d["SELL"] > d["BUY"] else "HOLD")
        last_dt = datetime.datetime.utcfromtimestamp(d["last_time"]).strftime("%H:%M UTC")
        lines.append("")
        lines.append(f"{pair}  bias={bias}")
        lines.append(f"  Total: {d['total']}  BUY: {d['BUY']}  SELL: {d['SELL']}  HOLD: {d['HOLD']}")
        lines.append(f"  Last:  {last_dt}  @ {d['last_price']}")
    return "\n".join(lines)

def control_panel_markup():
    return {
        "inline_keyboard": [
            [
                {"text": "Analyze Now", "callback_data": "analyze"},
                {"text": "Status",       "callback_data": "status"}
            ],
            [
                {"text": "Audit",        "callback_data": "audit"},
                {"text": "Health",       "callback_data": "health"}
            ],
            [
                {"text": "Pause Alerts", "callback_data": "pause"},
                {"text": "Daily Report", "callback_data": "daily"}
            ]
        ]
    }

def send_control_panel(chat_id):
    msg = (
        "BotA - Control Panel\n"
        "mode: RUNNING\n"
        f"pairs: {CFG.get('PAIRS', 'EURUSD,GBPUSD')}\n\n"
        "Use the buttons below."
    )
    send_msg(chat_id, msg, reply_markup=control_panel_markup())

# -------------------------------
# Command handler
# -------------------------------
def handle(chat_id, text, callback_data=None):
    cmd = (callback_data or (text.strip().split()[0].lower() if text else ""))
    print(f"[handle] chat_id={chat_id} cmd={cmd}", flush=True)

    # Authorization
    if ALLOWED_CHAT_IDS and chat_id not in ALLOWED_CHAT_IDS:
        send_msg(chat_id, "Unauthorized chat id.")
        return

    if cmd in ("/start", "start"):
        write_int_file(START_FILE, int(time.time()))
        send_control_panel(chat_id)
        ph = market_phase()
        age = heartbeat_age()
        age_s = f"{age}s" if age is not None else "n/a"
        send_msg(chat_id, f"Controller started\nMarket: {ph}\nHeartbeat: {age_s}")
        return

    if cmd in ("/status", "status"):
        ph = market_phase()
        age = heartbeat_age()
        age_s = f"{age}s" if age is not None else "n/a"
        pairs = CFG.get("PAIRS", "EURUSD GBPUSD").split()
        digest = digest_last_hour()
        total = sum(digest.values())
        msg = (
            "Status\n"
            "------\n"
            f"Market: {ph}\n"
            f"Heartbeat: {age_s}\n"
            f"Pairs: {', '.join(pairs[:3])}\n\n"
            "Signals (last 60m)\n"
            "------------------\n"
            f"Total: {total}\n"
            f"BUY: {digest.get('BUY',0)}  SELL: {digest.get('SELL',0)}  HOLD: {digest.get('HOLD',0)}"
        )
        send_msg(chat_id, msg)
        return

    if cmd in ("/dailyreport", "daily"):
        send_msg(chat_id, format_daily_report())
        return

    if cmd in ("/analyze", "analyze"):
        pairs = CFG.get("PAIRS", "EURUSD GBPUSD").split()[:2]
        send_msg(chat_id, "Analyze requested: " + ", ".join(pairs))
        return

    if cmd == "/help":
        send_msg(chat_id,
                 "Commands\n"
                 "/start - control panel\n"
                 "/status - watcher status\n"
                 "/dailyreport - 24h summary\n"
                 "/analyze - analyze pairs\n"
                 "/help - this help")
        return

    # Default: show panel
    send_control_panel(chat_id)

# -------------------------------
# Signal handling
# -------------------------------
def _signal_handler(sig, frame):
    print("[telecontroller] Shutting down...", flush=True)
    sys.exit(0)

signal.signal(signal.SIGINT,  _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)

# -------------------------------
# Main long polling loop
# -------------------------------
def main():
    write_int_file(START_FILE, int(time.time()))
    offset = read_int_file(OFFSET_FILE) or 0
    print("[telecontroller] started (polling)", flush=True)

    backoff = 2
    while True:
        try:
            resp = http_get("/getUpdates", {"timeout": 25, "offset": offset + 1})
            results = resp.get("result", [])
            for upd in results:
                offset = max(offset, int(upd.get("update_id", 0)))
                # messages
                msg = upd.get("message") or {}
                if msg:
                    chat_id = (msg.get("chat") or {}).get("id")
                    text = msg.get("text")
                    if chat_id and text:
                        handle(chat_id, text)
                # callbacks
                cb = upd.get("callback_query") or {}
                if cb:
                    cb_chat_id = ((cb.get("message") or {}).get("chat") or {}).get("id") or (cb.get("from") or {}).get("id")
                    cb_data    = cb.get("data")
                    if cb_chat_id and cb_data:
                        handle(cb_chat_id, None, callback_data=cb_data)
                        try:
                            http_post("/answerCallbackQuery", {"callback_query_id": cb.get("id")})
                        except Exception:
                            pass
                write_int_file(OFFSET_FILE, offset)
            # success path: reset backoff
            backoff = 2
        except urllib.error.HTTPError as e:
            # Common cause of HTTP 409: another instance polling. Keep retrying with backoff.
            print(f"[telecontroller] poll error: HTTP {e.code}: {e.reason}", flush=True)
            time.sleep(backoff)
            backoff = min(backoff * 2, 30)
        except Exception as e:
            print(f"[telecontroller] poll error: {e}", flush=True)
            time.sleep(backoff)
            backoff = min(backoff * 2, 30)

if __name__ == "__main__":
    main()
