#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

TOOLS="$HOME/BotA/tools"
CHAT_ID="${1:-}"

if [ -z "${TELEGRAM_BOT_TOKEN:-}" ]; then
  echo "[phase4_fix] ❌ TELEGRAM_BOT_TOKEN not exported."
  echo "Export it or use: source \$HOME/BotA/tools/tele_env.sh <CHAT_ID>"
  exit 1
fi

if [ -z "$CHAT_ID" ] && [ -z "${TELEGRAM_CHAT_ID:-}" ]; then
  echo "[phase4_fix] ❗ Provide your chat id: $TOOLS/phase4_fix.sh 6074056245"
  exit 2
fi

# Prefer CLI arg; else use env
if [ -n "$CHAT_ID" ]; then
  export TELEGRAM_CHAT_ID="$CHAT_ID"
fi
echo "[phase4_fix] Using CHAT_ID=$TELEGRAM_CHAT_ID"

# Send a clear test message
MSG="BotA Telegram test ✅ $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
if "$TOOLS/telegram_verify.sh" >/dev/null; then
  echo "✅ Telegram send OK."
  exit 0
fi

echo "❌ Telegram send FAILED. Running deeper diagnostics..."

# Deeper diagnostics:
# 1) Check getUpdates (shows chats that have messaged the bot)
python3 "$TOOLS/telegram_get_chat_id.py" || true

# 2) Direct API call with curl (helpful error strings)
if command -v curl >/dev/null 2>&1; then
  echo "--- curl probe ---"
  curl -sS -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
       -H 'Content-Type: application/json' \
       -d "{\"chat_id\": \"${TELEGRAM_CHAT_ID}\", \"text\": \"${MSG}\", \"disable_web_page_preview\": true}" \
       | sed 's/\\n/\n/g'
else
  echo "[phase4_fix] curl not installed; skipping curl probe."
fi

echo
echo "Common fixes:"
echo "  • Open Telegram, search your bot, press Start, send any message."
echo "  • Ensure TELEGRAM_CHAT_ID is correct (your user or group id)."
echo "  • If still failing, regenerate the token with BotFather and export again."
exit 1
