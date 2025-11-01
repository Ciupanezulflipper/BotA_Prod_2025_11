#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
: "${TELEGRAM_BOT_TOKEN:?Missing TELEGRAM_BOT_TOKEN}"
API="https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}"
echo "[fix] getWebhookInfo:"
curl -s "${API}/getWebhookInfo" | sed 's/,/\n/g' | sed -n '1,20p'
echo
echo "[fix] deleteWebhook (drop_pending_updates=true):"
curl -s -H 'Content-Type: application/json' -X POST \
     -d '{"drop_pending_updates":true}' \
     "${API}/deleteWebhook"
echo
echo "[fix] done."
