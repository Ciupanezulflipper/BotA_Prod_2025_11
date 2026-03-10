#!/usr/bin/env python3
"""
FILE: BotA/tools/telegramalert.py

ROLE
- Provide a stable Telegram send function for BotA callers.

WHY THIS EXISTS
- Other modules import: `from BotA.tools.telegramalert import send_telegram_message`
- Previous version only exposed `send_message()`, causing ImportError.

PUBLIC API (do not break)
- send_telegram_message(text: str, ...) -> (ok: bool, error: Optional[str])

ENV (accepted aliases)
- Token: TELEGRAM_BOT_TOKEN or TELEGRAM_TOKEN or BOT_TOKEN
- Chat:  TELEGRAM_CHAT_ID or CHAT_ID or TG_CHAT_ID or TELEGRAM_CHAT
- VERIFY_SSL: "true"/"false" (default true)

DEPENDENCIES
- Python stdlib only (urllib).
"""

from __future__ import annotations

import argparse
import json
import os
import ssl
import sys
import urllib.parse
import urllib.request
from typing import Optional, Tuple


def _env_first(*keys: str) -> str:
    for k in keys:
        v = os.getenv(k, "")
        if v and v.strip():
            return v.strip()
    return ""


def _resolve_token() -> str:
    # Accept common aliases used across the repo
    return _env_first("TELEGRAM_BOT_TOKEN", "TELEGRAM_TOKEN", "BOT_TOKEN")


def _resolve_chat_id() -> str:
    return _env_first("TELEGRAM_CHAT_ID", "CHAT_ID", "TG_CHAT_ID", "TELEGRAM_CHAT")


def _bool_env(name: str, default: bool = True) -> bool:
    v = os.getenv(name, "")
    if not v:
        return default
    v = v.strip().lower()
    if v in ("1", "true", "yes", "y", "on"):
        return True
    if v in ("0", "false", "no", "n", "off"):
        return False
    return default


def send_telegram_message(
    text: str,
    parse_mode: str = "HTML",
    disable_web_page_preview: bool = True,
    timeout_sec: int = 15,
) -> Tuple[bool, Optional[str]]:
    """
    Send a Telegram message.
    Returns:
      (True, None) on success
      (False, "reason") on failure (never raises for env/config issues)
    """
    token = _resolve_token()
    chat_id = _resolve_chat_id()

    if not token:
        return (False, "missing TELEGRAM_BOT_TOKEN (or TELEGRAM_TOKEN/BOT_TOKEN)")
    if not chat_id:
        return (False, "missing TELEGRAM_CHAT_ID (or CHAT_ID/TG_CHAT_ID)")

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": "true" if disable_web_page_preview else "false",
    }
    data = urllib.parse.urlencode(payload).encode("utf-8")

    verify_ssl = _bool_env("VERIFY_SSL", True)
    ctx = None
    if not verify_ssl:
        ctx = ssl._create_unverified_context()  # noqa: S501 (intentional opt-out)

    try:
        req = urllib.request.Request(url, data=data, method="POST")
        with urllib.request.urlopen(req, timeout=timeout_sec, context=ctx) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        try:
            j = json.loads(raw)
        except Exception:
            return (False, f"telegram non-json response: {raw[:200]}")
        if isinstance(j, dict) and j.get("ok") is True:
            return (True, None)
        return (False, f"telegram api error: {j}")
    except Exception as e:
        return (False, f"request failed: {repr(e)}")


# Backward-compatible helper: keep the old name working if anything calls it.
def send_message(text: str) -> dict:
    ok, err = send_telegram_message(text, parse_mode="HTML")
    if not ok:
        raise RuntimeError(err or "telegram send failed")
    # Return a minimal success dict (old code returned Telegram JSON; callers rarely need it)
    return {"ok": True}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", action="store_true", help="send test message")
    ap.add_argument("--send", action="store_true", help="send custom text")
    ap.add_argument("--text", default="", help="text to send with --send")
    args = ap.parse_args()

    if args.test:
        ok, err = send_telegram_message("🧪 Telegram test — BotA online")
        out = {"ok": ok, "error": err}
        print(json.dumps(out, ensure_ascii=False))
        raise SystemExit(0 if ok else 2)

    if args.send:
        if not args.text:
            print("ERROR: --send requires --text", file=sys.stderr)
            raise SystemExit(2)
        ok, err = send_telegram_message(args.text)
        out = {"ok": ok, "error": err}
        print(json.dumps(out, ensure_ascii=False))
        raise SystemExit(0 if ok else 2)

    print("Usage: --test | --send --text '...'", file=sys.stderr)
    raise SystemExit(2)


if __name__ == "__main__":
    main()
