#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
cd ~/BotA
[ -f .env ] && export $(grep -v ^# .env | xargs) || true
PAIR="${1:-EURUSD}"
TF="${2:-M15}"
CARD="$(python -m tools.runner_confluence --pair "$PAIR" --tf "$TF" --force --dry-run=false)"
curl -sS -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
  -d "chat_id=${TELEGRAM_CHAT_ID}" \
  --data-urlencode "text=${CARD}" >/dev/null
echo "[sent] ${PAIR} ${TF}"
