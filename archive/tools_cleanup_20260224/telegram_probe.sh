#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
set -a && . config/strategy.env && set +a
resp="$(curl -sS "https://api.telegram.org/bot$TELEGRAM_TOKEN/getMe")"
echo "$resp"
echo "$resp" | grep -q '"ok":true' && echo "✅ token valid" || { echo "❌ token invalid"; exit 1; }
