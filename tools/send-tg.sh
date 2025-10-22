#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
. "$HOME/bot-a/config/tele.env"

if [[ -z "${BOT_TOKEN:-}" || -z "${CHAT_ID:-}" ]]; then
  echo "send-tg: BOT_TOKEN/CHAT_ID not set" >&2; exit 1
fi

msg="${1:-"(empty)"}"
curl -s -X POST "https://api.telegram.org/bot${BOT_TOKEN}/sendMessage" \
  -d chat_id="$CHAT_ID" \
  -d text="$msg" \
  -d parse_mode=Markdown >/dev/null
