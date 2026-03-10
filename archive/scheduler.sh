#!/bin/bash
# scheduler.sh — Phase 2 Auto Status + Heartbeat (Termux safe)
set -euo pipefail
ROOT="$HOME/BotA"
ENV="$ROOT/config/tele.env"
LOG="$ROOT/logs/scheduler.log"
mkdir -p "$(dirname "$LOG")"

ts(){ date -u +"%Y-%m-%d %H:%M:%S UTC"; }
log(){ echo "[$(ts)] $*" >> "$LOG"; }

# --- Load Telegram Credentials ---
if [[ ! -f "$ENV" ]]; then log "❌ Missing $ENV"; exit 1; fi
source "$ENV"
: "${TELEGRAM_BOT_TOKEN:?tele.env missing TELEGRAM_BOT_TOKEN}"
: "${TELEGRAM_CHAT_ID:?tele.env missing TELEGRAM_CHAT_ID}"
API="https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}"

# --- Helpers ---
html_escape(){ sed -e 's/&/\&amp;/g' -e 's/</\&lt;/g' -e 's/>/\&gt;/g'; }
tg_send_html(){
  local chat_id="$1" html_text="$2"
  local r h b
  r="$(curl -sS -w $'\n%{http_code}' -X POST "$API/sendMessage" \
     --data-urlencode "chat_id=$chat_id" \
     --data-urlencode "text=$html_text" \
     --data-urlencode "parse_mode=HTML")" || { log "⚠️ curl failed"; return 1; }
  h="${r##*$'\n'}"; b="${r%$'\n'*}"
  [[ "$h" == "200" ]] && log "✅ sendMessage OK" || log "❌ HTTP $h $b"
}

# --- 1️⃣ Auto Status ---
STATUS_RAW="$(python3 "$ROOT/tools/status_pretty.py" advanced 2>&1 || true)"
STATUS_ESCAPED="$(printf "%s" "$STATUS_RAW" | html_escape | head -c 3500)"
tg_send_html "$TELEGRAM_CHAT_ID" "🕐 <b>Auto Status</b> — $(ts)
<pre>${STATUS_ESCAPED}</pre>" || log "📉 Auto-Status failed"

# --- 2️⃣ Heartbeat ---
M="$(date +%M)"
if [[ "$M" -lt 30 ]]; then
  tg_send_html "$TELEGRAM_CHAT_ID" "💓 <b>Heartbeat</b> — BotA alive at $(ts)" || log "📉 Heartbeat failed"
else
  log "⏭️ Skipped heartbeat (minute $M)"
fi

log "✅ scheduler.sh completed"
