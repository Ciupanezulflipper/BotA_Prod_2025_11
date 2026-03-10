#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

echo "=== Smoke Test: env_loader check ==="
bash tools/env_loader.sh

echo "=== Smoke Test: health-check ==="
bash tools/go_nogo.sh

echo "=== Smoke Test: send message to Telegram ==="
curl -sS -X POST "https://api.telegram.org/bot${TELEGRAM_TOKEN}/sendMessage" \
  -d chat_id="${TELEGRAM_CHAT_ID}" \
  -d text="🔥 Smoke test — $(date -Iseconds)"
echo "Message sent. Check Telegram for receipt."

echo "=== Smoke Test: check log startup ==="
tail -n 10 logs/telecontroller.log

echo "✅ Smoke test completed (CHECK Telegram chat + logs)"
