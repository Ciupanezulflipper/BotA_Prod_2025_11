#!/usr/bin/env python3
import json, os, sys, time, urllib.parse, urllib.request

HOME = os.path.expanduser("~")
ENV_PATH = os.path.join(HOME, "BotA", ".env")
if os.path.exists(ENV_PATH):
    for line in open(ENV_PATH, "r", encoding="utf-8"):
        if not line.strip() or line.strip().startswith("#"): continue
        if "=" in line:
            k, v = line.strip().split("=", 1)
            os.environ.setdefault(k, v)

TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
STATE_DIR = os.environ.get("STATE_DIR", os.path.join(HOME, "BotA", "state"))
LOG_DIR = os.path.join(HOME, "BotA", "logs")
os.makedirs(STATE_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

OFFSET_FILE = os.path.join(STATE_DIR, "telecontrol.offset")
BOT_STATE_SH = os.path.join(HOME, "BotA", "tools", "bot_state.sh")
API = f"https://api.telegram.org/bot{TOKEN}"

def log(msg: str):
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with open(os.path.join(LOG_DIR, "telecontroller.log"), "a", encoding="utf-8") as f:
        f.write(f"[telecontrol] {ts} {msg}\n")

def http_get(url, params=None, timeout=30):
    if params:
        url = url + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))

def http_post(url, data: dict, timeout=30):
    payload = urllib.parse.urlencode(data).encode("utf-8")
    req = urllib.request.Request(url, data=payload)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))

def send_message(text: str):
    if not TOKEN or not CHAT_ID: return
    try:
        http_post(API + "/sendMessage", {"chat_id": CHAT_ID, "text": text})
    except Exception as e:
        log(f"send_message error: {e}")

def read_offset():
    try:
        return int(open(OFFSET_FILE, "r", encoding="utf-8").read().strip() or "0")
    except:
        return 0

def write_offset(off: int):
    with open(OFFSET_FILE, "w", encoding="utf-8") as f:
        f.write(str(off))

def bot_state(cmd: str) -> str:
    # Call the shell helper
    try:
        import subprocess
        out = subprocess.check_output(["/data/data/com.termux/files/usr/bin/bash", BOT_STATE_SH, cmd], stderr=subprocess.STDOUT)
        return out.decode("utf-8").strip()
    except Exception as e:
        log(f"bot_state error: {e}")
        return "error"

def handle_text(text: str):
    t = (text or "").strip().lower()
    if t.startswith("/bot_off"):
        s = bot_state("pause")
        send_message(f"⏸️ BotA paused (state={s})")
        return True
    if t.startswith("/bot_on"):
        s = bot_state("resume")
        send_message(f"▶️ BotA resumed (state={s})")
        return True
    if t.startswith("/bot_status"):
        s = bot_state("status")
        send_message(f"ℹ️ BotA status: {s}")
        return True
    return False

def main():
    if not TOKEN or not CHAT_ID:
        print("Missing TELEGRAM_TOKEN or TELEGRAM_CHAT_ID in environment", file=sys.stderr)
        sys.exit(1)
    log("telecontrol start")
    off = read_offset()
    while True:
        try:
            upd = http_get(API + "/getUpdates", {"timeout": 25, "offset": off+1, "allowed_updates": json.dumps(["message"])}, timeout=30)
            if not upd.get("ok", False):
                time.sleep(2); continue
            for u in upd.get("result", []):
                off = max(off, int(u.get("update_id", 0)))
                msg = u.get("message") or {}
                chat = msg.get("chat") or {}
                text = msg.get("text", "")
                # Restrict to allowed chat id (string compare)
                if str(chat.get("id", "")) != str(CHAT_ID):
                    continue
                handled = handle_text(text)
                if handled:
                    log(f"handled: {text!r}")
            write_offset(off)
        except Exception as e:
            log(f"loop error: {e}")
            time.sleep(3)
        time.sleep(1)

if __name__ == "__main__":
    main()
