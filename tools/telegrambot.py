#!/usr/bin/env python3
import os, urllib.request, urllib.parse

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
CHAT_ID   = os.getenv("CHAT_ID", "")

def send_telegram(text: str) -> bool:
    """Send a text message via Telegram. Returns True on 200. Safe if unset."""
    if not BOT_TOKEN or not CHAT_ID:
        print(f"[TG] BOT_TOKEN/CHAT_ID missing; would send:\n{text}")
        return False
    try:
        url  = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        data = urllib.parse.urlencode({
            "chat_id": CHAT_ID,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": "true",
        }).encode("utf-8")
        req  = urllib.request.Request(url, data=data, method="POST")
        with urllib.request.urlopen(req, timeout=10) as r:
            ok = (r.status == 200)
            if not ok:
                print("[TG] HTTP", r.status, r.read())
            return ok
    except Exception as e:
        print("[TG] ERR:", e)
        return False
