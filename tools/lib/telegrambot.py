import os, json, urllib.request
TOKEN=os.environ.get("TELEGRAM_BOT_TOKEN") or os.environ.get("TELEGRAM_TOKEN") or ""
CHAT_ID=os.environ.get("TELEGRAM_CHAT_ID") or os.environ.get("CHAT_ID") or ""
def send_telegram(text, chat_id=None):
    t = TOKEN.strip(); c = (chat_id or CHAT_ID).strip()
    if not t or not c: return False
    data = urllib.parse.urlencode({"chat_id": c, "text": text}).encode()
    url  = f"https://api.telegram.org/bot{t}/sendMessage"
    try:
        urllib.request.urlopen(url, data=data, timeout=15).read()
        return True
    except Exception as e:
        print("TG_ERR:", e, flush=True); return False
