from datetime import datetime, timezone
from BotA.tools.telegramalert import send_telegram_message
send_telegram_message("✅ Probe " + datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"))
