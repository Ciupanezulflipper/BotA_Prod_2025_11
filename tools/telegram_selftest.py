#!/usr/bin/env python3
# tools/telegram_selftest.py
# Deep diagnostics for Telegram connectivity and token formatting.

import os, sys, json, socket, urllib.request, urllib.error
from datetime import datetime, timezone

API_ROOT = os.environ.get("TELEGRAM_API_ROOT", "https://api.telegram.org").rstrip("/")
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID", "")

def mask(s: str, keep=6) -> str:
    if not s: return "(empty)"
    if len(s) <= keep: return s
    return s[:keep] + "…" + s[-keep:]

def hex_dump(s: str) -> str:
    return " ".join(f"{ord(c):02x}" for c in s)

def resolve(host: str):
    try:
        infos = socket.getaddrinfo(host, 443)
        addrs = sorted({ai[4][0] for ai in infos})
        return addrs
    except Exception as e:
        return [f"resolve-error:{e}"]

def http_get_json(url: str):
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            raw = r.read().decode("utf-8", "ignore")
            return r.status, raw
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8", "ignore")
        except Exception:
            body = "<no body>"
        return e.code, body
    except Exception as e:
        return None, f"<exception: {e}>"

def main():
    print(f"API_ROOT: {API_ROOT}")
    print(f"TOKEN len: {len(BOT_TOKEN)}  masked: {mask(BOT_TOKEN)}")
    print(f"TOKEN hex head: {hex_dump(BOT_TOKEN[:8])}")
    print(f"TOKEN hex tail: {hex_dump(BOT_TOKEN[-8:]) if BOT_TOKEN else ''}")
    print(f"CHAT_ID: {CHAT_ID or '(empty)'}")
    print()

    host = API_ROOT.split("://",1)[-1].split("/",1)[0]
    print(f"DNS for {host}: {resolve(host)}")
    print()

    if not BOT_TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN is missing"); sys.exit(1)

    url_getme = f"{API_ROOT}/bot{BOT_TOKEN}/getMe"
    print(f"GET {url_getme[:60]}…")
    code, body = http_get_json(url_getme)
    print(f"HTTP status: {code}")
    print(f"Body:\n{body}\n")

    if code == 200 and '"ok":true' in body:
        print("✅ getMe OK")
    elif code == 401:
        print("❌ Unauthorized (token wrong).")
    elif code == 404:
        print("⚠️ 404 from Telegram endpoint. Common causes:")
        print("   - hidden space/newline in token (check hex above)")
        print("   - DNS/VPN/proxy rewrote the URL")
        print("   - regional block / captive portal")
    elif code is None:
        print("❌ Network/SSL error shown above.")
    else:
        print("⚠️ Unexpected status. See body above.")

if __name__ == "__main__":
    main()
