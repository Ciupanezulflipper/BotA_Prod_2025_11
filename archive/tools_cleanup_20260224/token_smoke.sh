#!/bin/bash
# token_smoke.sh — send a quick test message using config/tele.env

set -euo pipefail
ENV="$HOME/BotA/config/tele.env"
[ -f "$ENV" ] || { echo "❌ $ENV missing. Run tele_env_sync.sh first."; exit 1; }
# shellcheck disable=SC1090
source "$ENV"

API="https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}"
TEXT="$(printf 'BotA smoke test at %s' "$(date -u +'%Y-%m-%d %H:%M:%S UTC')")"

echo "📨 Sending smoke message to $TELEGRAM_CHAT_ID …"
curl -m 10 -sS -X POST "$API/sendMessage" \
  -d chat_id="$TELEGRAM_CHAT_ID" \
  -d text="$TEXT" \
  -d parse_mode="HTML" | grep -q '"ok":true' && echo "✅ Delivered." || { echo "❌ Failed."; exit 1; }
