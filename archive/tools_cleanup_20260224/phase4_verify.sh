#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

TOOLS="$HOME/BotA/tools"

# Load env from .env (and optional CHAT_ID override arg)
# shellcheck source=/dev/null
source "$TOOLS/tele_env.sh" "${1:-}"

if [ -z "${TELEGRAM_CHAT_ID:-}" ]; then
  echo "[phase4_verify] ℹ️ No TELEGRAM_CHAT_ID yet. If this is a new bot, open Telegram, /start the bot, then:"
  echo "  source $TOOLS/tele_env.sh <YOUR_CHAT_ID>"
  exit 2
fi

# Send test
if "$TOOLS/telegram_verify.sh" >/dev/null; then
  echo "✅ Telegram send OK."
  exit 0
else
  echo "❌ Telegram send FAILED." >&2
  exit 1
fi
