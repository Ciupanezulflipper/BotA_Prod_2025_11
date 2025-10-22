from __future__ import annotations
import os, time, math, requests
from typing import Optional

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
DEBUG = os.environ.get("TELEGRAM_DEBUG", "0") == "1"

API = "https://api.telegram.org"

def _send_once(text: str, parse_mode: Optional[str]=None, disable_web_page_preview: bool=True) -> requests.Response:
    if not TOKEN or not CHAT_ID:
        # mirror old interface: print & fail
        print("[TG] missing_env token/chat")
        class _Dummy: status_code=0; text="missing_env"
        return _Dummy()  # type: ignore
    url = f"{API}/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "disable_web_page_preview": "true" if disable_web_page_preview else "false",
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode
    return requests.post(url, data=payload, timeout=15)

def _diagnostic(prefix: str, r: requests.Response, text: str):
    tail = TOKEN[-6:] if TOKEN else "NONE"
    body = (r.text or "")[:180].replace("\n"," ")
    print(f"[TG] {prefix} status={getattr(r,'status_code',-1)} len={len(text)} chat={CHAT_ID} token_tail={tail} body={body}")

def _chunk(text: str, limit: int=3500):
    # Telegram hard max ~4096; we keep a safe margin
    for i in range(0, len(text), limit):
        yield text[i:i+limit]

def send_telegram_message(text: str, parse_mode: Optional[str]=None, disable_web_page_preview: bool=True) -> bool:
    """
    Returns True only when every chunk is delivered (status 200).
    """
    # Split text safely; send chunk-by-chunk
    for idx, chunk in enumerate(_chunk(text)):
        # up to 3 tries per chunk; backoff for 429
        tries = 0
        while True:
            tries += 1
            r = _send_once(chunk, parse_mode=parse_mode, disable_web_page_preview=disable_web_page_preview)
            sc = getattr(r, "status_code", -1)
            if sc == 200:
                if DEBUG: _diagnostic("ok", r, chunk)
                break  # next chunk
            if sc == 429 and hasattr(r, "json"):
                try:
                    retry_after = r.json().get("parameters",{}).get("retry_after", 2)
                except Exception:
                    retry_after = 2
                _diagnostic("rate_limited", r, chunk)
                time.sleep(max(1,int(retry_after)))
                if tries <= 3:  # retry
                    continue
            # For 400 “message is too long”, our chunking should prevent it.
            _diagnostic("error", r, chunk)
            return False
    print("Telegram sent.")
    return True

# Tiny CLI
if __name__ == "__main__":
    import sys
    msg = " ".join(sys.argv[1:]) or "🧪 telegramalert CLI test"
    ok = send_telegram_message(msg)
    sys.exit(0 if ok else 2)
