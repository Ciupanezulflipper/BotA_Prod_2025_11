#!/usr/bin/env python3
"""
tg_smoke_honey.py
- Reads .env.runtime ONLY (no edits)
- A) getMe      : token validity
- B) sendMessage: chat_id validity + bot permissions (only runs if token is valid)
- Prints ONLY: HTTP status, TG ok flag, TG error description (no token, no URL)
"""

import json
import re
import sys
import time
import pathlib
import urllib.parse
import urllib.request
from urllib.error import HTTPError, URLError

ASSIGN_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$")
TOKEN_RE = re.compile(r"^\d{6,}:[A-Za-z0-9_-]{20,}$")  # format-only sanity check


def strip_one_layer_quotes(v: str) -> str:
    v2 = v.strip()
    if len(v2) >= 2 and v2[0] == v2[-1] and v2[0] in ("'", '"'):
        return v2[1:-1]
    return v2


def load_env(path: pathlib.Path) -> dict:
    vals = {}
    if not path.is_file():
        return vals
    for line in path.read_text(errors="replace").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        m = ASSIGN_RE.match(line)
        if not m:
            # ignore non KEY=VALUE lines
            continue
        k, v = m.group(1), m.group(2)
        vals[k] = strip_one_layer_quotes(v)
    return vals


def chat_kind(chat: str) -> str:
    if not chat:
        return "MISSING"
    if chat.startswith("-100"):
        return "CHANNEL_OR_SUPERGROUP (-100...)"
    if chat.startswith("-"):
        return "GROUP (-...)"
    if chat.isdigit():
        return "PRIVATE_USER_CHAT (digits)"
    return "NON_NUMERIC (bad)"


def http_json(req: urllib.request.Request, timeout: int = 20):
    """
    Returns: (http_status, json_body_dict, error_type_or_empty)
    Never prints token/URL.
    """
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read().decode("utf-8", "replace")
            j = json.loads(body) if body else {}
            st = getattr(r, "status", "UNKNOWN")
            return st, j, ""
    except HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", "replace")
        except Exception:
            body = ""
        j = {}
        try:
            j = json.loads(body) if body else {}
        except Exception:
            j = {}
        return getattr(e, "code", "UNKNOWN"), j, "HTTPError"
    except URLError:
        return "NETWORK_FAIL", {}, "URLError"
    except Exception as ex:
        return "UNKNOWN_FAIL", {}, type(ex).__name__


def main() -> int:
    env_path = pathlib.Path(".env.runtime")
    vals = load_env(env_path)

    token = vals.get("TELEGRAM_BOT_TOKEN") or vals.get("BOT_TOKEN") or ""
    chat_id = vals.get("TELEGRAM_CHAT_ID") or vals.get("CHAT_ID") or ""

    print("=== tg_smoke_honey.py ===")
    print(f"DATE_UTC={time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}")
    print(f"ENV_FILE={env_path}")

    if not env_path.is_file():
        print("FAIL: .env.runtime missing")
        return 10

    if not token:
        print("FAIL: missing TELEGRAM_BOT_TOKEN/BOT_TOKEN in .env.runtime (value not printed)")
        return 11

    # Safe metadata only
    print(f"TOKEN_LEN={len(token)}")
    print(f"TOKEN_HAS_WHITESPACE={int(any(ch.isspace() for ch in token))}")
    print(f"TOKEN_REGEX_OK={int(bool(TOKEN_RE.match(token)))}")
    print(f"CHAT_ID_LEN={len(chat_id) if chat_id else 'MISSING'}")
    print(f"CHAT_KIND_HINT={chat_kind(chat_id)}")
    print(f"CHAT_DIGITS_OR_MINUS={int(bool(chat_id) and all(ch.isdigit() or ch=='-' for ch in chat_id)) if chat_id else 'MISSING'}")

    # A) getMe (token validity)
    req_getme = urllib.request.Request(f"https://api.telegram.org/bot{token}/getMe", method="GET")
    st, j, err = http_json(req_getme)
    ok = bool(j.get("ok"))
    desc = str(j.get("description", "")) if not ok else ""

    print("\n[A] getMe (token validity)")
    print(f"HTTP_STATUS={st}")
    print(f"TG_OK={int(ok)}")
    if not ok:
        print(f"TG_ERROR={desc or err or 'UNKNOWN'}")
        print("GETME_STATUS=FAIL")
        print("\nOVERALL=FAIL ❌")
        print("NEXT_HINT: If HTTP_STATUS=401 Unauthorized => token is invalid/revoked/wrong in BotFather.")
        return 20

    res = j.get("result", {}) or {}
    print(f"BOT_USERNAME={res.get('username','UNKNOWN')}")
    print("GETME_STATUS=PASS")

    # B) sendMessage (chat_id validity + permissions)
    if not chat_id:
        print("\n[B] sendMessage")
        print("SKIP: CHAT_ID missing")
        print("\nOVERALL=FAIL ❌")
        print("NEXT_HINT: Set TELEGRAM_CHAT_ID/CHAT_ID in .env.runtime after token is valid.")
        return 21

    msg = f"✅ BotA TG smoke+honey {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}"
    data = urllib.parse.urlencode({"chat_id": chat_id, "text": msg}).encode("utf-8")
    req_send = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=data, method="POST")

    st2, j2, err2 = http_json(req_send)
    ok2 = bool(j2.get("ok"))
    desc2 = str(j2.get("description", "")) if not ok2 else ""

    print("\n[B] sendMessage (chat_id + permissions)")
    print(f"HTTP_STATUS={st2}")
    print(f"TG_OK={int(ok2)}")
    if not ok2:
        print(f"TG_ERROR={desc2 or err2 or 'UNKNOWN'}")
        print("SEND_STATUS=FAIL")
        print("\nOVERALL=FAIL ❌")
        print("NEXT_HINTS:")
        print("- 400 chat not found => wrong chat_id OR you never pressed Start with the bot / added it to group/channel.")
        print("- 403 forbidden => bot blocked or missing permissions in group/channel.")
        return 30

    print("SEND_STATUS=PASS")
    print("\nOVERALL=PASS ✅ (token valid + message sent)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
