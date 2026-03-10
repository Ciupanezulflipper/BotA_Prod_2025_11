#!/usr/bin/env python3
"""
FILE: tools/api_credit_tracker.py
ROLE: Local Twelve Data API credit tracker.
- Counts every API call made by the bot
- Resets daily at 00:00 UTC
- Warns via Telegram if approaching limit
- Called by indicators_updater.sh after each fetch
Usage:
  python3 tools/api_credit_tracker.py increment [N]  # add N credits (default 1)
  python3 tools/api_credit_tracker.py status          # print current usage
  python3 tools/api_credit_tracker.py reset           # force reset (manual)
"""
import sys, json, os
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).parent.parent
STATE_FILE = ROOT / "logs" / "api_credits.json"
DAILY_LIMIT = int(os.environ.get("API_DAILY_LIMIT", "800"))
WARN_PCT = int(os.environ.get("API_WARN_PCT", "75"))
WARN_THRESHOLD = int(DAILY_LIMIT * WARN_PCT / 100)

def load():
    if not STATE_FILE.exists():
        return {"date": "", "used": 0, "warned": False}
    try:
        return json.loads(STATE_FILE.read_text())
    except Exception:
        return {"date": "", "used": 0, "warned": False}

def save(state):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))

def today():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")

def status_line(state):
    used = state["used"]
    pct = round(used / DAILY_LIMIT * 100, 1)
    bar = "🟢" if pct < 50 else "🟡" if pct < 75 else "🔴"
    return f"📡 API: {used}/{DAILY_LIMIT} credits ({pct}%) {bar}"

def send_telegram_warn(msg):
    env = ROOT / ".env"
    kv = {}
    for line in env.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"): continue
        if "=" in line:
            k, v = line.split("=", 1)
            kv[k.strip()] = v.strip().strip('"').strip("'")
    token = kv.get("TELEGRAM_BOT_TOKEN") or kv.get("TELEGRAM_TOKEN", "")
    chat  = kv.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat:
        return
    import urllib.request, urllib.parse
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": chat,
        "text": msg,
        "parse_mode": "HTML"
    }).encode()
    try:
        urllib.request.urlopen(url, data=data, timeout=10)
    except Exception:
        pass

cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
state = load()

# Auto-reset on new day
if state["date"] != today():
    state = {"date": today(), "used": 0, "warned": False}

if cmd == "increment":
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    state["used"] += n
    # Warn once per day when threshold crossed
    if state["used"] >= WARN_THRESHOLD and not state["warned"]:
        state["warned"] = True
        msg = (f"⚠️ BotA API Warning\n"
               f"Twelve Data credits: {state['used']}/{DAILY_LIMIT} "
               f"({round(state['used']/DAILY_LIMIT*100,1)}%)\n"
               f"Approaching daily limit. Bot may go silent.")
        send_telegram_warn(msg)
    save(state)
    print(status_line(state))

elif cmd == "reset":
    state = {"date": today(), "used": 0, "warned": False}
    save(state)
    print("Reset done.")

else:  # status
    save(state)
    print(status_line(state))
