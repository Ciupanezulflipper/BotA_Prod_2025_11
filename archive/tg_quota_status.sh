#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

DRY=0
[[ "${1:-}" == "--dry-run" ]] && DRY=1

BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)"
set -a; . "$BASE/.env"; set +a
: "${TELEGRAM_TOKEN:?TELEGRAM_TOKEN missing in $BASE/.env}"
: "${TELEGRAM_CHAT_ID:?TELEGRAM_CHAT_ID missing in $BASE/.env}"

snapshot="$("$BASE/tools/status_quota.sh")"
host_line="Host: $(uname -s) $(uname -n) $(uname -r)"
text=$'📊 BotA Quota — TwelveData\n• '"${snapshot}"$'\n• '"${host_line}"

if [[ "$DRY" -eq 1 ]]; then
  echo "$text"
  exit 0
fi

url="https://api.telegram.org/bot${TELEGRAM_TOKEN}/sendMessage"
curl -sS -X POST "$url" \
  -d "chat_id=${TELEGRAM_CHAT_ID}" \
  --data-urlencode "text=${text}" \
  -d "parse_mode=HTML" >/dev/null

echo "[tg_quota] sent OK @ $(date -u +%Y-%m-%dT%H:%M:%SZ)"
