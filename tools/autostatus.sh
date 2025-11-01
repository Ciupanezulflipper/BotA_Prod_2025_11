#!/bin/bash
# autostatus.sh — build & push the ADVANCED status once (used by cron at minute 4)
set -euo pipefail

ROOT="$HOME/BotA"
TMPDIR="$ROOT/tmp"
LOGDIR="$ROOT/logs"
TELE="$ROOT/config/tele.env"

mkdir -p "$TMPDIR" "$LOGDIR"

log(){ echo "[$(date -u +'%Y-%m-%d %H:%M:%S UTC')] $*" >> "$LOGDIR/cron.autostatus.log"; }

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

# --- Build status ---
OUT="$TMPDIR/as.out"
ERR="$TMPDIR/as.err"
: >"$OUT"; : >"$ERR"

log "▶️ Building advanced status…"
if ! python3 "$ROOT/tools/status_pretty.py" advanced >"$OUT" 2>"$ERR"; then
  log "❌ status_pretty.py failed: $(tr '\n' '|' <"$ERR")"
  exit 0
fi

STATUS_RAW="$(cat "$OUT")"
if [ -z "$STATUS_RAW" ]; then
  log "❌ empty status output"
  exit 0
fi

# --- Telegram send ---
API="https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage"
TEXT="🕘 <b>Auto Status</b> — $(date -u +'%Y-%m-%d %H:%M:%S UTC')%0A<pre>$(printf '%s' "$STATUS_RAW" | sed 's/%/%25/g; s/&/%26/g; s/+/%2B/g; s/#/%23/g; s/ /%20/g')</pre>"

RESP="$(curl -sS -X POST "$API" \
  -d "chat_id=${TELEGRAM_CHAT_ID}" \
  -d "parse_mode=HTML" \
  --data-urlencode "disable_web_page_preview=true" \
  --data-urlencode "text=$TEXT" || true)"

if echo "$RESP" | grep -q '"ok":true'; then
  log "✅ sendMessage OK"
else
  log "❌ sendMessage failed resp=$(echo "$RESP" | tr '\n' ' ')"
fi

exit 0
