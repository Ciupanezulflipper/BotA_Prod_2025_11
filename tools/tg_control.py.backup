#!/data/data/com.termux/files/usr/bin/python3
# -*- coding: utf-8 -*-
"""
Telegram controller for Bot-A
- Commands: /start /stop /status /analyze /digest /help /restart /uptime
- Heartbeat monitor (warn if no heartbeat > 2 min; rate-limited)
- Unified logging (~/bot-a/logs/tg_control.log)
- Single-instance lock
- Sets Telegram bot commands on launch
"""

import os, sys, time, json, signal, subprocess, traceback
from datetime import datetime, timezone, timedelta

import requests

# --- Paths & constants ---
HOME = "/data/data/com.termux/files/home"
BOT   = os.path.join(HOME, "bot-a")
TOOLS = os.path.join(BOT, "tools")
CONF  = os.path.join(BOT, "config")
DATA  = os.path.join(BOT, "data")
LOGS  = os.path.join(BOT, "logs")

os.makedirs(DATA, exist_ok=True)
os.makedirs(LOGS, exist_ok=True)

LOG_FILE         = os.path.join(LOGS, "tg_control.log")
LOCK_FILE        = os.path.join(DATA, "tg_control.lock")
ENABLED_FILE     = os.path.join(DATA, "loop_enabled.flag")     # present => ON
HEARTBEAT_FILE   = os.path.join(LOGS, "last_heartbeat.txt")    # written by auto_conf.sh
LAST_SEND_FILE   = os.path.join(DATA, "last_send.txt")         # written by runner on real send
LAST_ALERT_FILE  = os.path.join(DATA, "last_alert_heartbeat.txt")
AUTO_CONF_SH     = os.path.join(TOOLS, "auto_conf.sh")
RUNNER_PY        = os.path.join(TOOLS, "runner_confluence.py")

LOOP_CADENCE_SEC      = int(os.environ.get("LOOP_SEC", "60"))  # shown in /status
HEARTBEAT_WARN_SEC    = 120   # if no heartbeat > 2 min -> warn
HEARTBEAT_ALERT_COOLD = 3600  # don't spam: 1 alert/hour max

START_TS = time.time()

# --- Logging ---
def log(line: str):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    try:
        with open(LOG_FILE, "a") as f:
            f.write(f"[{ts}] {line}\n")
    except Exception:
        pass

# --- Env / Telegram ---
def load_env():
    tele_env = os.path.join(CONF, "tele.env")
    if os.path.exists(tele_env):
        with open(tele_env, "r") as f:
            for ln in f:
                ln = ln.strip()
                if not ln or ln.startswith("#") or "=" not in ln:
                    continue
                k, v = ln.split("=", 1)
                os.environ[k] = v.strip(' "\'')

load_env()
TOKEN = os.getenv("TG_BOT_TOKEN", "").strip()
CHAT  = os.getenv("TG_CHAT_ID", "").strip()
API   = f"https://api.telegram.org/bot{TOKEN}"

if not TOKEN or not CHAT:
    print("ERROR: TG_BOT_TOKEN or TG_CHAT_ID missing in config/tele.env")
    sys.exit(1)

def tg_post(method: str, data: dict) -> dict:
    try:
        r = requests.post(f"{API}/{method}", data=data, timeout=30)
        return r.json()
    except Exception as e:
        log(f"tg_post error {method}: {e}")
        return {"ok": False, "error": str(e)}

def tg_get(method: str, params: dict) -> dict:
    try:
        r = requests.get(f"{API}/{method}", params=params, timeout=30)
        return r.json()
    except Exception as e:
        log(f"tg_get error {method}: {e}")
        return {"ok": False, "error": str(e)}

def send_text(text: str, parse_mode: str = None):
    data = {"chat_id": CHAT, "text": text}
    if parse_mode:
        data["parse_mode"] = parse_mode
    resp = tg_post("sendMessage", data)
    if not resp.get("ok"):
        log(f"send_text failed: {resp}")
    return resp

# --- Single-instance lock ---
def acquire_lock():
    if os.path.exists(LOCK_FILE):
        # stale lock? if older than 10 minutes, take over
        try:
            age = time.time() - os.path.getmtime(LOCK_FILE)
            if age < 600:
                print("Another tg_control instance appears to be running. Exiting.")
                sys.exit(0)
        except Exception:
            pass
    with open(LOCK_FILE, "w") as f:
        f.write(str(os.getpid()))

def release_lock():
    try:
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)
    except Exception:
        pass

# --- Helpers ---
def is_enabled() -> bool:
    return os.path.exists(ENABLED_FILE)

def set_enabled(flag: bool):
    if flag:
        open(ENABLED_FILE, "a").close()
    else:
        if os.path.exists(ENABLED_FILE):
            os.remove(ENABLED_FILE)

def read_file(path: str) -> str:
    try:
        with open(path, "r") as f:
            return f.read().strip()
    except Exception:
        return ""

def human_time(ts: float) -> str:
    if ts <= 0:
        return "n/a"
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

def uptime_str() -> str:
    delta = int(time.time() - START_TS)
    h = delta // 3600
    m = (delta % 3600) // 60
    s = delta % 60
    return f"{h}h {m}m {s}s"

# --- Set Commands & clear webhook ---
def setup_bot_commands():
    # Make sure no webhook is set (409 Conflict avoidance)
    tg_post("deleteWebhook", {})

    commands = [
        {"command": "start",   "description": "Start the bot loop"},
        {"command": "stop",    "description": "Stop the bot loop"},
        {"command": "status",  "description": "Show bot status"},
        {"command": "analyze", "description": "Run one analysis now"},
        {"command": "digest",  "description": "Send daily digest now"},
        {"command": "uptime",  "description": "Show controller uptime"},
        {"command": "restart", "description": "Restart controller"},
        {"command": "help",    "description": "Show commands"},
    ]
    tg_post("setMyCommands", {"commands": json.dumps(commands)})
    log("Bot commands set.")

# --- Command handlers ---
def cmd_start():
    set_enabled(True)
    send_text("🟢 Bot loop: ON\nThe analyzer will continue at its normal cadence.")
    log("Command /start -> enabled")

def cmd_stop():
    set_enabled(False)
    send_text("🔴 Bot loop: OFF\nAnalyzer keeps heartbeat but will not send strong signals.")
    log("Command /stop -> disabled")

def cmd_status():
    hb = read_file(HEARTBEAT_FILE) or "n/a"
    last_send_ts = 0.0
    try:
        if os.path.exists(LAST_SEND_FILE):
            last_send_ts = float(read_file(LAST_SEND_FILE) or "0")
    except Exception:
        last_send_ts = 0.0
    last_send = human_time(last_send_ts)
    state = "ON" if is_enabled() else "OFF"
    msg = (
        f"🤖 Bot: {state}\n"
        f"⏱ Loop cadence: {LOOP_CADENCE_SEC}s\n"
        f"❤️ Heartbeat: {hb}\n"
        f"📤 Last strong send: {last_send}"
    )
    send_text(msg)
    log("Command /status -> reported")

def cmd_analyze():
    # Trigger one analysis (same as your manual test)
    try:
        subprocess.run(["python3", RUNNER_PY], cwd=TOOLS, check=False)
        send_text("🔎 Analyze triggered.\nOK")
        log("Command /analyze -> runner invoked")
    except Exception as e:
        send_text(f"Analyze error: {e}")
        log(f"/analyze error: {e}")

def cmd_digest():
    try:
        subprocess.run(["python3", RUNNER_PY, "--digest"], cwd=TOOLS, check=False)
        send_text("🧾 Digest triggered.\nOK")
        log("Command /digest -> digest invoked")
    except Exception as e:
        send_text(f"Digest error: {e}")
        log(f"/digest error: {e}")

def cmd_help():
    send_text(
        "Available commands:\n"
        "/start – start auto loop\n"
        "/stop – stop auto loop\n"
        "/status – show bot status\n"
        "/analyze – run one analysis now\n"
        "/digest – send daily digest now\n"
        "/uptime – show controller uptime\n"
        "/restart – restart controller\n"
        "/help – show this help"
    )

def cmd_uptime():
    send_text(f"⏳ Controller uptime: {uptime_str()}")

def cmd_restart():
    send_text("♻️ Restarting controller…")
    log("Command /restart -> restarting")
    # Re-exec ourselves
    release_lock()
    os.execv(sys.executable, [sys.executable, __file__])

# --- Heartbeat watcher ---
def maybe_alert_stale_heartbeat():
    try:
        hb_raw = read_file(HEARTBEAT_FILE)
        if not hb_raw:
            return
        # Expect format like "2025-09-20 01:42:35 UTC"
        hb = datetime.strptime(hb_raw.replace(" UTC", ""), "%Y-%m-%d %H:%M:%S")
        hb = hb.replace(tzinfo=timezone.utc)
        age = (datetime.now(timezone.utc) - hb).total_seconds()

        if age > HEARTBEAT_WARN_SEC:
            last_alert_ts = 0.0
            if os.path.exists(LAST_ALERT_FILE):
                try:
                    last_alert_ts = float(read_file(LAST_ALERT_FILE) or "0")
                except Exception:
                    last_alert_ts = 0.0
            if (time.time() - last_alert_ts) > HEARTBEAT_ALERT_COOLD:
                send_text(f"⚠️ Heartbeat stale: last at {hb_raw} (age {int(age)}s).")
                with open(LAST_ALERT_FILE, "w") as f:
                    f.write(str(time.time()))
                log("Heartbeat stale alert sent.")
    except Exception as e:
        log(f"maybe_alert_stale_heartbeat error: {e}")

# --- Update loop ---
def handle_update(upd: dict):
    if "message" not in upd:
        return
    msg = upd["message"]
    if str(msg.get("chat", {}).get("id")) != CHAT:
        return  # ignore other chats

    text = (msg.get("text") or "").strip()
    if not text.startswith("/"):
        return

    cmd = text.split()[0].lower()
    if cmd == "/start":
        cmd_start()
    elif cmd == "/stop":
        cmd_stop()
    elif cmd == "/status":
        cmd_status()
    elif cmd == "/analyze":
        cmd_analyze()
    elif cmd == "/digest":
        cmd_digest()
    elif cmd == "/help":
        cmd_help()
    elif cmd == "/uptime":
        cmd_uptime()
    elif cmd == "/restart":
        cmd_restart()
    else:
        send_text("Unknown command. Type /help")

def main():
    acquire_lock()
    setup_bot_commands()
    send_text("🤖 tg_control online.")
    log("tg_control started")

    offset = 0
    while True:
        try:
            # long-poll updates
            resp = tg_get("getUpdates", {"timeout": 25, "offset": offset})
            if resp.get("ok"):
                for upd in resp.get("result", []):
                    offset = max(offset, upd["update_id"] + 1)
                    handle_update(upd)
            else:
                # 409 Conflict typically means webhook was set; we already deleteWebhook on start.
                log(f"getUpdates error: {resp}")
                time.sleep(2)

            # periodic heartbeat check
            maybe_alert_stale_heartbeat()

            # small idle
            time.sleep(1)

        except KeyboardInterrupt:
            break
        except Exception as e:
            log(f"main loop error: {e}\n{traceback.format_exc()}")
            time.sleep(2)

    send_text("tg_control stopping.")
    release_lock()

if __name__ == "__main__":
    main()
