#!/usr/bin/env python3
"""
tools/tg_send.py

Minimal, robust Telegram sender with NO repo-root imports.
Contract:
- Accept message from argv (or stdin if no argv).
- Print "SUCCESS" on success so callers can detect delivery.
- Exit 0 on success, 1 on failure.
"""

from __future__ import annotations

import os
import sys
import time
from typing import Optional

import requests


def _env(key: str) -> Optional[str]:
    v = os.getenv(key)
    return v.strip() if isinstance(v, str) and v.strip() else None


def _read_message(argv) -> str:
    if len(argv) >= 2:
        return " ".join(argv[1:]).strip()
    # fallback: read stdin
    data = sys.stdin.read()
    return (data or "").strip()


def send_message(text: str) -> bool:
    token = _env("TELEGRAM_BOT_TOKEN")
    chat_id = _env("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        print("tg_send: missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID", flush=True)
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"

    max_attempts = int(os.getenv("TG_SEND_MAX_ATTEMPTS", "3"))
    base_sleep = float(os.getenv("TG_SEND_BASE_SLEEP", "1.5"))
    timeout_sec = float(os.getenv("TG_SEND_TIMEOUT_SEC", "20"))

    payload = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": True,
    }

    last_err = ""
    for attempt in range(1, max_attempts + 1):
        try:
            r = requests.post(url, data=payload, timeout=timeout_sec)

            # Telegram rate limit
            if r.status_code == 429:
                retry_after = None
                try:
                    j = r.json()
                    retry_after = int(j.get("parameters", {}).get("retry_after", 0)) or None
                except Exception:
                    retry_after = None

                sleep_s = retry_after if retry_after else max(base_sleep, base_sleep * attempt)
                last_err = f"rate_limited retry_after={sleep_s}"
                time.sleep(float(sleep_s))
                continue

            if r.ok:
                return True

            # non-200 responses
            last_err = f"http_{r.status_code} {r.text[:200]}"

        except Exception as e:
            last_err = f"{type(e).__name__}: {str(e)[:200]}"

        # backoff before retry (except after last attempt)
        if attempt < max_attempts:
            time.sleep(base_sleep * attempt)

    print(f"tg_send: send failed ({last_err})", flush=True)
    return False


def main() -> int:
    msg = _read_message(sys.argv)
    if not msg:
        print("tg_send: no message provided", flush=True)
        return 1

    ok = send_message(msg)
    if ok:
        print("SUCCESS", flush=True)
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
