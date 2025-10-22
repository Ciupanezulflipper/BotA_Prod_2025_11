#!/usr/bin/env python3
import os, requests

# load from env
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID")

def send_telegram_message(text: str) -> bool:
    """Send plain text message to Telegram. Returns True if success."""
    if not BOT_TOKEN or not CHAT_ID:
        print("Telegram config missing (TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID).")
        return False
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        r = requests.post(url, json={"chat_id": CHAT_ID, "text": text})
        return r.status_code == 200
    except Exception as e:
        print("Telegram send failed:", e)
        return False
