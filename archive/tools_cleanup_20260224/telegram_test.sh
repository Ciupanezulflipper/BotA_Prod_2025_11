#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

# Load config
if [[ -n "${BASH_SOURCE[0]:-}" ]]; then
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
else
  SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
fi
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"
set -a; source config/strategy.env; set +a

if [[ -z "${TELEGRAM_TOKEN:-}" || -z "${TELEGRAM_CHAT_ID:-}" ]]; then
  echo "❌ TELEGRAM_TOKEN or TELEGRAM_CHAT_ID missing in config/strategy.env"
  exit 1
fi

TEXT="🔧 BotA Telegram test — $(date -Iseconds)"
URL="https://api.telegram.org/bot${TELEGRAM_TOKEN}/sendMessage"
curl -sS -X POST "$URL" \
  -d "chat_id=${TELEGRAM_CHAT_ID}" \
  -d "text=${TEXT}" \
  -d "parse_mode=${TELEGRAM_PARSE_MODE:-Markdown}" >/dev/null

echo "✅ Telegram test sent: ${TEXT}"
