#!/data/data/com.termux/files/usr/bin/bash
# Bot A — Phase 4: Telegram connectivity smoke test
set -euo pipefail

if [ -z "${TELEGRAM_BOT_TOKEN:-}" ] || [ -z "${TELEGRAM_CHAT_ID:-}" ]; then
  echo "[telegram_verify] ❌ Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in env." >&2
  exit 1
fi

MSG="BotA Telegram test ✅ $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
if python3 "$HOME/BotA/tools/telegram_push.py" "$MSG" >/dev/null; then
  echo "✅ Telegram send OK."
  exit 0
else
  echo "❌ Telegram send FAILED." >&2
  exit 1
fi
