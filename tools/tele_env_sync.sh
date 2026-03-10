#!/bin/bash
# tele_env_sync.sh — verify Telegram token & write config/tele.env

set -euo pipefail

mask() { local s="${1:-}"; [ -z "$s" ] && echo "(empty)" || echo "${s:0:8}********"; }

echo "🔍 Checking TELEGRAM_BOT_TOKEN …"
if [[ -z "${TELEGRAM_BOT_TOKEN:-}" ]]; then
  echo "❌ TELEGRAM_BOT_TOKEN not exported in this shell."
  echo "   Export it, e.g.:  export TELEGRAM_BOT_TOKEN='123:ABC...'"
  exit 1
fi
CHAT_ID_TEST="${TELEGRAM_CHAT_ID:-6074056245}"
API="https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}"

echo "→ Token prefix: $(mask "$TELEGRAM_BOT_TOKEN")"
echo "→ Test chat id: ${CHAT_ID_TEST}"

# Quick token check
if curl -m 10 -sS "${API}/getMe" | grep -q '"ok":true'; then
  echo "✅ Token valid. Writing $HOME/BotA/config/tele.env"
  cat > "$HOME/BotA/config/tele.env" <<EOF
TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
TELEGRAM_CHAT_ID=${CHAT_ID_TEST}
EOF
  echo "✅ Saved."
else
  echo "❌ Invalid token or network issue."
  exit 1
fi
