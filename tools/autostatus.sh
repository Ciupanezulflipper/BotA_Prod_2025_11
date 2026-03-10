#!/bin/bash
# autostatus.sh — build & push the ADVANCED status once (used by cron at minute 4)
# Option A: PLAIN TEXT Telegram send (no parse_mode, no HTML) to avoid entity parse failures.
set -euo pipefail

ROOT="$HOME/BotA"
TMPDIR="$ROOT/tmp"
LOGDIR="$ROOT/logs"
TELE="$ROOT/config/tele.env"

mkdir -p "$TMPDIR" "$LOGDIR"

log(){ echo "[$(date -u +'%Y-%m-%d %H:%M:%S UTC')] $*" >> "$LOGDIR/cron.autostatus.log"; }

# --- Load Telegram creds ---
if [ -f "$TELE" ]; then
  # shellcheck disable=SC1090
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
{

  python3 "$ROOT/tools/format_status.py" 2>/dev/null

} >"$OUT" 2>"$ERR"
if [ ! -s "$OUT" ]; then
  log "❌ emit_snapshot failed: $(tr '\n' '|' <"$ERR")"
  exit 0
fi

STATUS_RAW="$(cat "$OUT")"
if [ -z "$STATUS_RAW" ]; then
  log "❌ empty status output"
  exit 0
fi

# --- Telegram send (PLAIN TEXT) ---
API="https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage"

TEXT="${STATUS_RAW}"

# Send as plain text; do NOT set parse_mode; do NOT wrap in <pre> or <b>
RESP="$(curl -sS -w $'\nHTTP_STATUS:%{http_code}\n' -X POST "$API" \
  -d "chat_id=${TELEGRAM_CHAT_ID}" \
  -d "disable_web_page_preview=true" \
  --data-urlencode "text=${TEXT}" || true)"

HTTP_CODE="$(printf '%s' "$RESP" | sed -n 's/^HTTP_STATUS:\([0-9][0-9][0-9]\)$/\1/p' | tail -n 1)"
BODY="$(printf '%s' "$RESP" | sed '/^HTTP_STATUS:[0-9][0-9][0-9]$/d')"

if printf '%s' "$BODY" | grep -q '"ok":true'; then
  log "✅ sendMessage OK (plain) http=${HTTP_CODE:-unknown}"
else
  log "❌ sendMessage failed http=${HTTP_CODE:-unknown} resp=$(printf '%s' "$BODY" | tr '\n' ' ')"
fi

exit 0
