#!/usr/bin/env python3
import os, sys, json

def http_get(url, timeout=12):
    try:
        import requests  # type: ignore
        r = requests.get(url, timeout=timeout)
        return r.status_code, r.text
    except Exception:
        try:
            import urllib.request
            with urllib.request.urlopen(url, timeout=timeout) as resp:
                code = getattr(resp, "status", 200)
                txt = resp.read().decode("utf-8","replace")
                return code, txt
        except Exception as e:
            return 0, str(e)

def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN","").strip()
    if not token:
        print("[get_chat_id] ❌ TELEGRAM_BOT_TOKEN not set (source tele_env.sh first)", file=sys.stderr)
        sys.exit(1)
    url = f"https://api.telegram.org/bot{token}/getUpdates"
    code, txt = http_get(url)
    if code != 200:
        print(f"[get_chat_id] ❌ HTTP {code}: {txt[:200]}", file=sys.stderr)
        sys.exit(1)
    try:
        j = json.loads(txt)
    except Exception as e:
        print(f"[get_chat_id] ❌ JSON decode error: {e}", file=sys.stderr)
        sys.exit(1)
    if not j.get("ok"):
        print(f"[get_chat_id] ❌ API error: {j.get('description','unknown')}", file=sys.stderr)
        sys.exit(1)
    # Collect unique chat IDs and titles/usernames
    seen = {}
    for upd in j.get("result", []):
        msg = upd.get("message") or upd.get("edited_message") or {}
        chat = msg.get("chat") or {}
        cid = chat.get("id")
        if cid is None: 
            continue
        title = chat.get("title") or chat.get("username") or (chat.get("first_name","") + " " + chat.get("last_name","")).strip()
        seen[cid] = title or "(no title)"
    if not seen:
        print("[get_chat_id] ℹ️ No chats found. Send a message to your bot and re-run.", file=sys.stderr)
        sys.exit(2)
    print("[get_chat_id] ✅ Chats discovered:")
    for cid, name in seen.items():
        print(f"{cid}\t{name}")
    sys.exit(0)

if __name__ == "__main__":
    main()
