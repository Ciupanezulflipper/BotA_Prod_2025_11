# BotA/tools/tg_utils.py
from __future__ import annotations

import os
import json
import time
import warnings
from typing import Optional

import requests
from urllib3.exceptions import InsecureRequestWarning

# --- Config helpers ---------------------------------------------------------

def _env_bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return str(val).strip().lower() in ("1", "true", "yes", "on")

def _resolve_verify_ssl() -> bool:
    """
    Decide SSL verify behavior from env/runtime:
      - If VERIFY_SSL is set -> use it
      - Else if INTERNET_MODE=ship -> False
      - Else -> True
    """
    if os.getenv("VERIFY_SSL") is not None:
        return _env_bool("VERIFY_SSL", True)
    mode = (os.getenv("INTERNET_MODE") or "").strip().lower()
    return False if mode == "ship" else True

def _maybe_disable_ssl_warning(verify_ssl: bool) -> None:
    if not verify_ssl:
        warnings.filterwarnings("ignore", category=InsecureRequestWarning)

# --- Telegram send ----------------------------------------------------------

def _tg_endpoint(token: str, method: str) -> str:
    return f"https://api.telegram.org/bot{token}/{method}"

def send_message(
    text: str,
    chat_id: Optional[str] = None,
    parse_mode: Optional[str] = None,
    disable_web_page_preview: bool = True,
    disable_notification: bool = False,
) -> bool:
    """
    Send a Telegram message honoring SSL mode (land/ship).
    Returns True on success, False otherwise.
    """
    token = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TG_BOT_TOKEN") or ""
    chat  = chat_id or os.getenv("TELEGRAM_CHAT_ID") or os.getenv("TG_CHAT_ID") or ""
    if not token or not chat:
        print("tg_utils: missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID")
        return False

    verify_ssl = _resolve_verify_ssl()
    _maybe_disable_ssl_warning(verify_ssl)

    url = _tg_endpoint(token, "sendMessage")
    payload = {
        "chat_id": chat,
        "text": text,
        "disable_web_page_preview": disable_web_page_preview,
        "disable_notification": disable_notification,
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode

    try:
        r = requests.post(url, json=payload, timeout=20, verify=verify_ssl)
        if r.ok:
            return True
        else:
            # print useful context but avoid dumping secrets
            print(f"tg_utils: send failed status={r.status_code} body={r.text[:300]}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"tg_utils: error {type(e).__name__}: {e}")
        return False

# --- CLI test ---------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Telegram transport smoke test")
    ap.add_argument("--test", metavar="TEXT", nargs="?", const="BotA transport test", help="Send a test message")
    args = ap.parse_args()
    if args.test is not None:
        ok = send_message(args.test)
        print("sent" if ok else "failed")
