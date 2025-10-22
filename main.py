#!/usr/bin/env python3
import os, sys, requests
from dotenv import load_dotenv

def send_tg(text: str) -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        print("ERROR: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID missing in .env")
        sys.exit(1)
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    r = requests.post(url, json=payload, timeout=15)
    r.raise_for_status()
    print("Telegram message sent.")

if __name__ == "__main__":
    load_dotenv()
    if len(sys.argv) >= 3 and sys.argv[1] == "--test":
        msg = " ".join(sys.argv[2:])
        send_tg(msg)
    else:
        print("Bot A skeleton ready. Use: python main.py --test 'Your message'")
