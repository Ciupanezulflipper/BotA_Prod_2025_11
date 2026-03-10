import os, urllib.request, urllib.parse
bot = os.getenv("BOT_TOKEN","")
chat = os.getenv("CHAT_ID","")
if not bot or not chat:
    print("ERR: BOT_TOKEN/CHAT_ID missing. Run: source .env"); raise SystemExit(1)
url = f"https://api.telegram.org/bot{bot}/sendMessage"
payload = urllib.parse.urlencode({
    "chat_id": chat,
    "text": "✅ Test OK from Termux (runner_test.py)",
    "disable_web_page_preview": "true"
}).encode("utf-8")
try:
    with urllib.request.urlopen(urllib.request.Request(url, data=payload, method="POST"), timeout=10) as r:
        print("HTTP", r.status, r.read(200))
except Exception as e:
    print("ERR", e)
