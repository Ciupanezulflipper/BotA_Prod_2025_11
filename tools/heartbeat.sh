#!/bin/bash
# heartbeat.sh — quiet hourly heartbeat (cron: minute 0)
set -euo pipefail

ROOT="$HOME/BotA"
TMPDIR="$ROOT/tmp"
LOGDIR="$ROOT/logs"
TELE="$ROOT/config/tele.env"

mkdir -p "$TMPDIR" "$LOGDIR"

log(){ echo "[$(date -u +'%Y-%m-%d %H:%M:%S UTC')] $*" >> "$LOGDIR/cron.heartbeat.log"; }

# --- Load Telegram creds ---
if [ -f "$TELE" ]; then
  . "$TELE"
else
  log "❌ tele.env missing"
  exit 0
fi

if [ -z "${TELEGRAM_BOT_TOKEN:-}" ] || [ -z "${TELEGRAM_CHAT_ID:-}" ]; then
  log "❌ TELEGRAM_* vars missing"
  exit 0
fi

# --- Send heartbeat ---
API="https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage"
TEXT="💓 <b>Heartbeat</b> — BotA alive at $(date -u +'%Y-%m-%d %H:%M:%S UTC')"

RESP="$(curl -sS -X POST "$API" \
  -d "chat_id=${TELEGRAM_CHAT_ID}" \
  -d "parse_mode=HTML" \
  --data-urlencode "disable_web_page_preview=true" \
  --data-urlencode "text=$TEXT" || true)"

if echo "$RESP" | grep -q '"ok":true'; then
  log "✅ Heartbeat sent"
else
  log "❌ Heartbeat failed resp=$(echo "$RESP" | tr '\n' ' ')"
fi

exit 0
