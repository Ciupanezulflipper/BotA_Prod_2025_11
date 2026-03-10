#!/data/data/com.termux/files/usr/bin/python3
# -*- coding: utf-8 -*-
"""
status_card.py — Bot-A Status + Market Context card

What it shows:
- Bot health: PID running, last heartbeat, last error
- Signal overview: analyzed today, strong sent, avg confidence
- Market context: forex open/closed, session countdowns (Sydney/Tokyo/London/NY)
- Next holiday (optional, from config/holidays.json)
- Config snapshot: thresholds, digest guard
- Security check: tele.env present and usable

Usage:
  python3 tools/status_card.py            # print card
  python3 tools/status_card.py --send     # print + send to Telegram (if TG env is set)

Notes:
- No external libs. Pure stdlib.
- Time is UTC. Session open times are approximate UTC anchors:
    Sydney  = 22:00 UTC
    Tokyo   = 00:00 UTC
    London  = 08:00 UTC
    NewYork = 13:00 UTC
- Holidays file is optional: ~/bot-a/config/holidays.json
  Format: [{"date":"2025-12-25","label":"Christmas (major closure)"}]
"""

import os, sys, json, time, traceback
from datetime import datetime, timezone, timedelta

# ---------- Paths ----------
BOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGS_DIR = os.path.join(BOT_DIR, "logs")
DATA_DIR = os.path.join(BOT_DIR, "data")
CONFIG_DIR = os.path.join(BOT_DIR, "config")

PID_FILE        = os.path.join(LOGS_DIR, "auto_conf.pid")
HEARTBEAT_FILE  = os.path.join(LOGS_DIR, "last_heartbeat.txt")
MAIN_LOG        = os.path.join(LOGS_DIR, "auto_conf.log")
SIGNALS_CSV     = os.path.join(DATA_DIR, "signals.csv")
POLICY_JSON     = os.path.join(CONFIG_DIR, "policy.json")
TELE_ENV        = os.path.join(CONFIG_DIR, "tele.env")
HOLIDAYS_JSON   = os.path.join(CONFIG_DIR, "holidays.json")  # optional

# ---------- Helpers ----------
def now_utc():
    return datetime.now(timezone.utc)

def load_json_safe(path, default=None):
    try:
        with open(path, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return default
    except Exception:
        return default

def read_first_env(file_path):
    """source-like read: key=value lines into env (no export)."""
    if not os.path.exists(file_path):
        return False
    try:
        with open(file_path, "r") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                os.environ[k.strip()] = v.strip().strip('"').strip("'")
        return True
    except Exception:
        return False

def file_tail_lines(path, max_bytes=100_000):
    """Read end of file safely (last ~max_bytes)."""
    if not os.path.exists(path):
        return ""
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as f:
            if size > max_bytes:
                f.seek(-max_bytes, os.SEEK_END)
            data = f.read().decode("utf-8", errors="ignore")
        return data
    except Exception:
        return ""

def format_td(delta):
    """Format timedelta as 'Xd Yh Zm' or 'Hh Mm'."""
    if delta.total_seconds() < 0:
        delta = -delta
        sign = "-"
    else:
        sign = ""
    minutes = int(delta.total_seconds() // 60)
    days, minutes = divmod(minutes, 1440)
    hours, minutes = divmod(minutes, 60)
    parts = []
    if days: parts.append(f"{days}d")
    if hours: parts.append(f"{hours}h")
    parts.append(f"{minutes}m")
    return sign + " ".join(parts)

# ---------- Health ----------
def check_pid_running(pid_file):
    try:
        with open(pid_file, "r") as f:
            pid_str = f.read().strip()
        if not pid_str.isdigit():
            return ("Unknown", False)
        pid = int(pid_str)
        # On Android/Termux, /proc/<pid> exists if running
        running = os.path.exists(f"/proc/{pid}")
        return (pid_str, running)
    except FileNotFoundError:
        return ("Not found", False)
    except Exception:
        return ("Unknown", False)

def read_heartbeat(hb_file):
    try:
        with open(hb_file, "r") as f:
            txt = f.read().strip()
        # If text is a datetime string, show it raw; otherwise show file mtime
        return txt
    except FileNotFoundError:
        return "None"
    except Exception:
        return "Unknown"

def last_error_from_log(log_path):
    tail = file_tail_lines(log_path, max_bytes=80_000)
    if not tail:
        return "None"
    lines = tail.splitlines()
    # search latest line with error markers
    for line in reversed(lines):
        low = line.lower()
        if "error" in low or "traceback" in low or "send-fail" in low or "failed" in low:
            return line.strip()[:200]
    return "None"

# ---------- Signals ----------
def parse_signals_today(csv_path):
    today = now_utc().date()
    analyzed = 0
    strong_sent = 0
    conf_sum = 0.0
    try:
        if not os.path.exists(csv_path):
            return (0, 0, 0.0)
        with open(csv_path, "r") as f:
            for raw in f:
                line = raw.strip()
                if not line:
                    continue
                parts = line.split(",")
                # Expected: iso_ts,bias,confidence,sentiment,notes...
                if len(parts) < 3:
                    continue
                ts = parts[0]
                try:
                    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                except Exception:
                    continue
                if dt.date() != today:
                    continue
                analyzed += 1
                try:
                    conf = float(parts[2])
                except Exception:
                    conf = 0.0
                conf_sum += conf
                # Treat “strong” as conf >= strong_threshold if available; else >=6
                # We will fetch strong threshold from policy below and recompute there.
        # avg later after threshold read for strong count
        return (analyzed, -1, conf_sum)  # strong placeholder
    except Exception:
        return (0, 0, 0.0)

# ---------- Market context ----------
SESSION_ANCHORS_UTC = {
    "Sydney":  (22, 0),
    "Tokyo":   (0, 0),
    "London":  (8, 0),
    "NewYork": (13, 0),
}

def next_session_delta(anchor_h, anchor_m, ref):
    session_time = ref.replace(hour=anchor_h, minute=anchor_m, second=0, microsecond=0)
    if session_time <= ref:
        session_time += timedelta(days=1)
    return session_time - ref

def forex_open_status(ref):
    # Simple model:
    # Closed: from Friday 21:00 UTC until Sunday ~21:00 UTC
    wd = ref.weekday()  # Mon=0 ... Sun=6
    hour = ref.hour
    if wd == 5:  # Saturday
        return "CLOSED"
    if wd == 6 and hour < 21:
        return "CLOSED"
    if wd == 4 and hour >= 21:
        return "CLOSED"
    return "OPEN"

def next_holiday_note(path, ref_date):
    h = load_json_safe(path, default=[])
    if not h:
        return "None configured"
    upcoming = []
    for item in h:
        try:
            d = datetime.fromisoformat(item["date"]).date()
            if d >= ref_date:
                upcoming.append((d, item.get("label", "Holiday")))
        except Exception:
            continue
    if not upcoming:
        return "None soon"
    upcoming.sort(key=lambda x: x[0])
    d, label = upcoming[0]
    return f"{d.isoformat()} — {label}"

# ---------- Config / Security ----------
def load_policy_snapshot(path):
    pol = load_json_safe(path, default={})
    # Defaults
    conf_th  = pol.get("confidence_threshold", pol.get("conf_gate", 3.2))
    strong_th = pol.get("strong_send_threshold", pol.get("strong_threshold", 6))
    throttle_min = pol.get("throttle_minutes", pol.get("throttle_seconds", 1800) / 60 if pol.get("throttle_seconds") else 15)
    digest_guard = pol.get("digest_guard", pol.get("digest", {}).get("weekend_guard_on", False))
    return (conf_th, strong_th, float(throttle_min), bool(digest_guard))

def security_check(tele_env_path):
    ok_env = read_first_env(tele_env_path)
    tok = os.getenv("TG_BOT_TOKEN", "")
    cid = os.getenv("TG_CHAT_ID", "")
    if not ok_env:
        return (False, "tele.env missing")
    if not tok or not cid:
        return (False, "Telegram vars not loaded")
    return (True, "Config & token loaded")

# ---------- Card ----------
def build_status_card():
    ref = now_utc()

    # Health
    pid_text, pid_running = check_pid_running(PID_FILE)
    hb_text = read_heartbeat(HEARTBEAT_FILE)
    last_err = last_error_from_log(MAIN_LOG)

    # Config snapshot
    conf_th, strong_th, throttle_min, digest_guard = load_policy_snapshot(POLICY_JSON)

    # Signals
    analyzed, strong_placeholder, conf_sum = parse_signals_today(SIGNALS_CSV)
    avg_conf = (conf_sum / analyzed) if analyzed else 0.0
    # Count strong sent by scanning log for "send-OK" lines today
    strong_count = 0
    tail = file_tail_lines(MAIN_LOG, max_bytes=200_000)
    if tail:
        today_str = ref.strftime("%Y-%m-%d")
        for line in tail.splitlines():
            if today_str in line and ("send-OK" in line or "Strong signal sent" in line):
                strong_count += 1

    # Market context
    fx_status = forex_open_status(ref)
    session_lines = []
    for name, (h, m) in SESSION_ANCHORS_UTC.items():
        delta = next_session_delta(h, m, ref)
        session_lines.append(f"• {name} opens in {format_td(delta)}")

    # Holiday
    hol_note = next_holiday_note(HOLIDAYS_JSON, ref.date())

    # Security
    sec_ok, sec_msg = security_check(TELE_ENV)

    # Build HTML card
    parts = []
    parts.append("🤖 <b>BOT STATUS</b>")
    parts.append("")
    parts.append(f"{'✅' if pid_running else '❌'} Health: {'Running' if pid_running else 'Stopped'} (PID {pid_text})")
    parts.append(f"🫀 Last heartbeat: {hb_text}")
    parts.append(f"⚠️ Last error: {last_err}")
    parts.append("")
    parts.append("📊 <b>Signals Today</b>")
    parts.append(f"• Analyzed: {analyzed}")
    parts.append(f"• Strong Signals Sent: {strong_count}")
    parts.append(f"• Avg Confidence: {avg_conf:.1f}/10")
    parts.append("")
    parts.append("📅 <b>Market Context</b>")
    parts.append(f"• Forex: <b>{fx_status}</b> (Weekend guard may mute sends)")
    parts.extend(session_lines)
    parts.append(f"• Next holiday: {hol_note}")
    parts.append("")
    parts.append("⚙️ <b>Config</b>")
    parts.append(f"• Confidence threshold: {conf_th}")
    parts.append(f"• Strong send threshold: {strong_th}")
    parts.append(f"• Throttle: {throttle_min:.0f} min")
    parts.append(f"• Digest Guard: {'ON' if digest_guard else 'OFF'}")
    parts.append("")
    parts.append(f"🔒 Security: {sec_msg}")
    parts.append("")
    parts.append(f"🕒 {ref.strftime('%Y-%m-%d %H:%M UTC')}")
    return "\n".join(parts)

# ---------- Telegram ----------
def send_telegram(html_text):
    tok = os.getenv("TG_BOT_TOKEN", "")
    cid = os.getenv("TG_CHAT_ID", "")
    if not tok or not cid:
        print("Telegram send skipped: TG_BOT_TOKEN / TG_CHAT_ID not loaded")
        return False
    import requests
    url = f"https://api.telegram.org/bot{tok}/sendMessage"
    data = {"chat_id": cid, "text": html_text, "parse_mode": "HTML", "disable_web_page_preview": True}
    try:
        r = requests.post(url, data=data, timeout=20)
        ok = (r.status_code == 200)
        if not ok:
            print(f"Telegram send error: HTTP {r.status_code} {r.text[:200]}")
        return ok
    except Exception as e:
        print(f"Telegram send exception: {e}")
        return False

# ---------- Main ----------
def main():
    # make sure dirs exist
    for p in (LOGS_DIR, DATA_DIR, CONFIG_DIR):
        os.makedirs(p, exist_ok=True)

    card = build_status_card()
    print(card)

    if "--send" in sys.argv:
        # ensure env loaded
        read_first_env(TELE_ENV)
        ok = send_telegram(card)
        print("Sent to Telegram" if ok else "Failed to send")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # Never crash silently; print minimal info
        print(f"Status card error: {e}")
        traceback.print_exc()
        sys.exit(1)
