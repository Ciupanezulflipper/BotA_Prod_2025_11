# ---------- tg.py ----------
"""
Thin Telegram helper.
Reads TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID from env.
Exports:
  tg_send_text(chat_id, text, parse_mode=None) -> (ok, why)
  tg_send_photo(chat_id, png_bytes, caption="", parse_mode=None) -> (ok, why)
"""

import os, logging, requests

log = logging.getLogger("tg")
SESSION = requests.Session()
API = "https://api.telegram.org"

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
CHAT  = os.getenv("TELEGRAM_CHAT_ID", "").strip()
CAPTION_MAX = 1024
DEFAULT_TIMEOUT = 15

def _post(method: str, data=None, files=None):
    if not TOKEN:
        return False, "missing TELEGRAM_BOT_TOKEN"
    url = f"{API}/bot{TOKEN}/{method}"
    try:
        r = SESSION.post(url, data=data, files=files, timeout=DEFAULT_TIMEOUT)
        if r.status_code != 200:
            return False, f"http {r.status_code} {r.text[:200]}"
        j = r.json()
        if not j.get("ok", False):
            return False, f"tg error {j}"
        return True, "ok"
    except Exception as e:
        return False, str(e)

def tg_send_text(chat_id: str|None, text: str, parse_mode: str|None=None):
    cid = (chat_id or CHAT).strip()
    if not cid: return (False, "missing TELEGRAM_CHAT_ID")
    if not TOKEN: return (False, "missing TELEGRAM_BOT_TOKEN")
    if not text: return (False, "empty text")
    data = {"chat_id": cid, "text": text}
    if parse_mode: data["parse_mode"] = parse_mode
    ok, why = _post("sendMessage", data=data)
    if not ok: log.warning("telegram send text failed: %s", why)
    return ok, why

def tg_send_photo(chat_id: str|None, png_bytes: bytes, caption: str="", parse_mode: str|None=None):
    cid = (chat_id or CHAT).strip()
    if not cid:   return (False, "missing TELEGRAM_CHAT_ID")
    if not TOKEN: return (False, "missing TELEGRAM_BOT_TOKEN")
    if not png_bytes: return (False, "empty image bytes")
    cap = caption or ""
    if len(cap) > CAPTION_MAX:
        cap = cap[:CAPTION_MAX-1] + "…"
    data = {"chat_id": cid}
    if cap: data["caption"] = cap
    if parse_mode: data["parse_mode"] = parse_mode
    files = {"photo": ("chart.png", png_bytes, "image/png")}
    ok, why = _post("sendPhoto", data=data, files=files)
    if not ok: log.warning("telegram send photo failed: %s", why)
    return ok, why
