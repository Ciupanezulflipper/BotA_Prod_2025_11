#!/usr/bin/env bash
set -euo pipefail

LOG="$HOME/bot-a/logs/auto_h1.log"

# Collect last lines nicely formatted
if [[ -s "$LOG" ]]; then
  tail -n 20 "$LOG" | sed 's/^/│ /' > /data/data/com.termux/files/home/BotA/cache/botA_h1_tail.txt
else
  printf '│ (log file not found or empty)\n' > /data/data/com.termux/files/home/BotA/cache/botA_h1_tail.txt
fi

# Send to Telegram through the bot helper
PYTHONPATH="$HOME/bot-a" python3 - <<'PY'
from tools.tg_send import send_message
with open('/data/data/com.termux/files/home/BotA/cache/botA_h1_tail.txt','r') as f:
    tail = f.read()
msg = "⚠️ BotA H1 watchdog:\n" + tail
ok, info = send_message(msg)
print("sent:", ok, info)
PY
