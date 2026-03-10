#!/usr/bin/env python3
# Curl-based telecontroller (bypasses Python SSL issues)
import os, sys, time, json, subprocess

HOME = os.path.expanduser("~")
ROOT = os.path.join(HOME, "BotA")
CACHE = os.path.join(ROOT, "cache")
LOGS = os.path.join(ROOT, "logs")

os.makedirs(CACHE, exist_ok=True)
os.makedirs(LOGS, exist_ok=True)

def read_env():
    cfg = {}
    cfg_path = os.path.join(ROOT, "config", "strategy.env")
    if os.path.isfile(cfg_path):
        with open(cfg_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    cfg[k.strip()] = v.strip().strip('"').strip("'")
    return cfg

CFG = read_env()
TOKEN = os.environ.get("TELEGRAM_TOKEN") or CFG.get("TELEGRAM_TOKEN")
API_BASE = f"https://api.telegram.org/bot{TOKEN}"

def curl_request(path, data=None, timeout=30):
    """Use curl instead of urllib (bypasses Python SSL issues)"""
    url = API_BASE + path
    cmd = ["curl", "-s", "-m", str(timeout)]
    
    if data:
        for k, v in data.items():
            cmd.extend(["-d", f"{k}={v}"])
    
    cmd.append(url)
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout+5)
        return json.loads(result.stdout)
    except Exception as e:
        print(f"[curl] error: {e}", file=sys.stderr, flush=True)
        return {"ok": False}

def send_msg(chat_id, text, parse_mode="Markdown"):
    try:
        return curl_request("/sendMessage", {
            "chat_id": str(chat_id),
            "text": text[:4000],
            "parse_mode": parse_mode
        })
    except Exception as e:
        print(f"[send_msg] error: {e}", flush=True)

def write_int(path, val):
    try:
        with open(path, "w") as f:
            f.write(str(int(val)))
    except:
        pass

def read_int(path):
    try:
        with open(path) as f:
            c = f.read().strip()
        return int(c) if c.isdigit() else None
    except:
        return None

def heartbeat_age():
    hb = os.path.join(CACHE, "watcher.heartbeat")
    try:
        with open(hb) as f:
            c = f.read().strip()
        if not c or not c.isdigit():
            return None
        return max(0, int(time.time()) - int(c))
    except:
        return None

def market_phase():
    cmd = os.path.join(ROOT, "tools", "market_open.sh")
    if not os.path.isfile(cmd):
        return "Unknown"
    try:
        out = subprocess.check_output(["bash", cmd], stderr=subprocess.DEVNULL, timeout=8).decode().strip()
        last = out.splitlines()[-1].strip()
        return last if last in ("Open", "Closed", "Unknown") else "Unknown"
    except:
        return "Unknown"

def handle(chat_id, text):
    if not text:
        return
    
    parts = text.strip().split()
    cmd = parts[0].lower()
    
    if cmd == "/start":
        write_int(os.path.join(CACHE, "telecontroller.started"), int(time.time()))
        phase = market_phase()
        age = heartbeat_age()
        age_s = f"{age}s" if age else "n/a"
        return send_msg(chat_id,
            f"✅ *Controller Started* (curl mode)\n"
            f"Market: `{phase}`\n"
            f"Heartbeat: `{age_s}`"
        )
    
    if cmd == "/status":
        phase = market_phase()
        age = heartbeat_age()
        age_s = f"{age}s" if age else "n/a"
        status_emoji = "✅" if age and age < 180 else "⚠️"
        market_emoji = "🟢" if phase == "Open" else "🔴"
        
        return send_msg(chat_id,
            f"{status_emoji} *Status*\n"
            f"{market_emoji} Market: `{phase}`\n"
            f"💓 Heartbeat: `{age_s}`"
        )
    
    return send_msg(chat_id, "Use /start or /status")

def main():
    if not TOKEN:
        print("[telecontroller] ERROR: TELEGRAM_TOKEN missing", flush=True)
        return
    
    offset_file = os.path.join(CACHE, "tele.offset")
    offset = read_int(offset_file) or 0
    
    print("[telecontroller] started (curl mode)", flush=True)
    
    while True:
        try:
            r = curl_request("/getUpdates", {"timeout": 25, "offset": offset + 1})
            
            if not r.get("ok"):
                print(f"[telecontroller] API error: {r}", flush=True)
                time.sleep(5)
                continue
            
            for upd in r.get("result", []):
                offset = max(offset, upd.get("update_id", 0))
                
                msg = upd.get("message") or {}
                chat = msg.get("chat") or {}
                chat_id = chat.get("id")
                text = msg.get("text")
                
                if chat_id and text:
                    print(f"[handle] chat_id={chat_id} cmd={text}", flush=True)
                    handle(chat_id, text)
                
                write_int(offset_file, offset)
        except Exception as e:
            print(f"[telecontroller] poll error: {e}", flush=True)
            time.sleep(5)

if __name__ == "__main__":
    main()
