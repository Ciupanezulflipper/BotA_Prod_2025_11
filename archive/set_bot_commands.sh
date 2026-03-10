#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -f "$BASE/.env" ]]; then set -a; . "$BASE/.env"; set +a; fi
: "${TELEGRAM_TOKEN:?missing TELEGRAM_TOKEN in .env}"
API="https://api.telegram.org/bot${TELEGRAM_TOKEN}/setMyCommands"

json='{
  "commands": [
    {"command":"hard_on","description":"Hard start with .env defaults"},
    {"command":"hard_off","description":"Hard stop — kill all schedulers"},
    {"command":"bot_status","description":"Show current bot status"},
    {"command":"help","description":"Show available commands"}
  ]
}'
curl -s -H 'Content-Type: application/json' -d "$json" "$API" >/dev/null 2>&1 && echo true || echo false
