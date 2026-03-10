#!/usr/bin/env python3
"""
Bot A — Phase 4: Telegram Push

Usage:
  python3 tools/telegram_push.py "your message text"
  echo "msg" | python3 tools/telegram_push.py

Env:
  TELEGRAM_BOT_TOKEN   (required)
  TELEGRAM_CHAT_ID     (required)
  TELEGRAM_PARSE_MODE  (optional: "MarkdownV2" | "HTML" | "None"; default None/plain)
  TELEGRAM_DISABLE_WEB_PREVIEW (optional: "1" to disable preview)

Exit codes: 0 on success, 1 on failure
"""
from __future__ import annotations
import os, sys, json

API_URL = "https://api.telegram.org/bot{token}/sendMessage"

def _read_message_from_stdin() -> str:
    if sys.stdin.isatty():
        return ""
    return sys.stdin.read().strip()

def _send_http(url: str, payload: dict, timeout: int = 12) -> tuple[int, str]:
    # Try requests if available; fallback to urllib
    try:
        import requests  # type: ignore
        r = requests.post(url, json=payload, timeout=timeout)
        return r.status_code, r.text
    except Exception:
        try:
            import urllib.request
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(url, data=data, headers={"Content-Type":"application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                code = getattr(resp, "status", 200)
                txt = resp.read().decode("utf-8","replace")
                return code, txt
        except Exception as e:
            return 0, str(e)

def main() -> int:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        print("[telegram_push] ❌ Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID", file=sys.stderr)
        return 1

    msg = " ".join(sys.argv[1:]).strip()
    if not msg:
        msg = _read_message_from_stdin()
    if not msg:
        print("[telegram_push] ❌ No message provided", file=sys.stderr)
        return 1

    parse_mode = os.getenv("TELEGRAM_PARSE_MODE", "").strip()
    disable_preview = os.getenv("TELEGRAM_DISABLE_WEB_PREVIEW", "1").strip() in ("1","true","TRUE","yes","YES")

    payload = {
        "chat_id": chat_id,
        "text": msg,
        "disable_web_page_preview": disable_preview,
    }
    if parse_mode and parse_mode.lower() != "none":
        payload["parse_mode"] = parse_mode

    url = API_URL.format(token=token)
    code, txt = _send_http(url, payload)
    ok = False
    try:
        j = json.loads(txt)
        ok = bool(j.get("ok"))
        if not ok:
            desc = j.get("description","unknown")
            print(f"[telegram_push] ❌ API error: {desc}", file=sys.stderr)
    except Exception:
        if code == 200:
            ok = True  # assume ok if 200 but non-json (rare)
        else:
            print(f"[telegram_push] ❌ HTTP {code}: {txt[:200]}", file=sys.stderr)

    if ok:
        print("[telegram_push] ✅ sent")
        return 0
    return 1

if __name__ == "__main__":
    sys.exit(main())
