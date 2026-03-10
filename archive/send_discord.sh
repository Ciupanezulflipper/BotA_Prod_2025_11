#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
source "$HOME/bot-a/.env" 2>/dev/null || true
if [ -z "${DISCORD_WEBHOOK:-}" ]; then
  echo "DISCORD_WEBHOOK not set in .env" >&2
  exit 0
fi

MSG="${1:-}"
if [ -z "$MSG" ]; then
  MSG=$(cat)
fi

# Trim to Discord's JSON payload (simple content)
printf '%s' "$MSG" | curl -sS -m 10 -H "Content-Type: application/json" \
  -d @- "$DISCORD_WEBHOOK" \
  --data-urlencode "content=$(printf %s "$MSG")" >/dev/null 2>&1 || true
