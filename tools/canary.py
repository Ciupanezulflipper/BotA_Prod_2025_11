from datetime import datetime, timezone
import os, requests
tok = os.environ["TELEGRAM_BOT_TOKEN"]
cid = os.environ["TELEGRAM_CHAT_ID"]
msg = "🩺 daily canary " + datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
r = requests.post(f"https://api.telegram.org/bot{tok}/sendMessage", data={"chat_id": cid, "text": msg}, timeout=10)
print("canary status:", r.status_code)
