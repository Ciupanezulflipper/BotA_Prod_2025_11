import os, time, requests

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT  = os.getenv("TELEGRAM_CHAT_ID")
VERIFY_SSL = os.getenv("VERIFY_SSL","true").lower()=="true"

def send_telegram_message(text: str, token: str|None=None, chat_id: str|None=None, timeout=10, retries=2):
    token = token or TOKEN
    chat_id = chat_id or CHAT
    if not token or not chat_id:
        return False, "TELEGRAM_BOT_TOKEN/CHAT_ID not set"
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    for attempt in range(retries+1):
        try:
            r = requests.post(url, json=payload, timeout=timeout, verify=VERIFY_SSL)
            if r.status_code == 200:
                return True, ""
            if r.status_code == 429:
                wait = int(r.headers.get("Retry-After","5"))
                time.sleep(min(wait,15))
                continue
            return False, f"HTTP {r.status_code}"
        except requests.Timeout:
            if attempt==retries: return False, "timeout"
            time.sleep(2**attempt)
        except Exception as e:
            if attempt==retries: return False, str(e)
            time.sleep(2**attempt)
    return False, "unknown"
