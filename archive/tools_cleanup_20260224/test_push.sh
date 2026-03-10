#!/bin/bash
set -euo pipefail
ROOT="$HOME/BotA"; ENV="$ROOT/config/tele.env"
[[ -f "$ENV" ]] || { echo "❌ Missing $ENV" >&2; exit 1; }
source "$ENV"
: "${TELEGRAM_BOT_TOKEN:?tele.env missing TELEGRAM_BOT_TOKEN}"
: "${TELEGRAM_CHAT_ID:?tele.env missing TELEGRAM_CHAT_ID}"
API="https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}"
NOW="$(date -u +"%Y-%m-%d %H:%M:%S UTC")"
curl -sS -X POST "$API/sendMessage" \
  --data-urlencode "chat_id=$TELEGRAM_CHAT_ID" \
  --data-urlencode "text=✅ Test push OK — $NOW" \
  --data-urlencode "parse_mode=HTML" >/dev/null
echo "✅ Sent test push at $NOW"
