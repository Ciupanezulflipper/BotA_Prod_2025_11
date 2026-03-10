#!/usr/bin/env python3
import os, requests

token = os.getenv("TELEGRAM_BOT_TOKEN")
chat  = os.getenv("TELEGRAM_CHAT_ID")

if not token or not chat:
    raise SystemExit("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID in .env")

msg = "Hello Toma 👋 — this is a test from Bot-A!"

url = f"https://api.telegram.org/bot{token}/sendMessage"
res = requests.post(url, data={"chat_id": chat, "text": msg})

print("Status:", res.status_code, "Response:", res.text)
