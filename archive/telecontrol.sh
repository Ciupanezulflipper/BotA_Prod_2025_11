#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATE_DIR="$BASE/state"
LOG_DIR="$BASE/logs"
mkdir -p "$STATE_DIR" "$LOG_DIR"

# Load env
if [[ -f "$BASE/.env" ]]; then
  set -a; . "$BASE/.env"; set +a
fi

: "${TELEGRAM_TOKEN:?missing TELEGRAM_TOKEN in .env}"
: "${TELEGRAM_CHAT_ID:?missing TELEGRAM_CHAT_ID in .env}"
API="https://api.telegram.org/bot${TELEGRAM_TOKEN}"
OFFSET_FILE="$STATE_DIR/telecontrol.offset"

send_msg() {
  local text="$1"
  curl -s "${API}/sendMessage" \
    -d chat_id="$TELEGRAM_CHAT_ID" \
    -d parse_mode="HTML" \
    --data-urlencode "text=${text}" >/dev/null 2>&1 || true
}

status_line() {
  if pgrep -f 'BotA/tools/run_loop\.sh' >/dev/null 2>&1; then
    echo "running"
  else
    echo "stopped"
  fi
}

handle_cmd() {
  case "$1" in
    "/hard_off" | "/hard_off@${BOT_USERNAME:-}")
      bash "$BASE/tools/hard_stop.sh" || true
      send_msg "⏹️ BotA HARD-STOP executed — all schedulers terminated"
      ;;
    "/hard_on" | "/hard_on@${BOT_USERNAME:-}")
      bash "$BASE/tools/hard_start.sh" || true
      send_msg "▶️ BotA HARD-START — running with ${PAIRS:-EURUSD,GBPUSD} (pad=${TF15_SLEEP_PAD:-120}s, provider=${PROVIDER_ORDER:-twelve_data})"
      ;;
    "/bot_status" | "/status" | "/status@${BOT_USERNAME:-}" | "/bot_status@${BOT_USERNAME:-}")
      send_msg "ℹ️ BotA status: $(status_line)"
      ;;
    "/help" | "/help@${BOT_USERNAME:-}")
      send_msg "Commands:\n• /hard_on — hard start with .env defaults\n• /hard_off — hard stop (kill all schedulers)\n• /bot_status — show current status"
      ;;
    *)
      ;;
  esac
}

poll() {
  local offset resp count update_id text
  offset="$(cat "$OFFSET_FILE" 2>/dev/null || echo 0)"
  while :; do
    resp="$(curl -s "${API}/getUpdates" -d timeout=25 -d offset="$offset")" || { sleep 2; continue; }

    if command -v jq >/dev/null 2>&1; then
      count="$(printf '%s' "$resp" | jq '.result | length')"
      if [[ "$count" -gt 0 ]]; then
        for row in $(printf '%s' "$resp" | jq -c '.result[]'); do
          update_id="$(printf '%s' "$row" | jq -r '.update_id')"
          text="$(printf '%s' "$row" | jq -r '.message.text // empty')"
          [[ -n "$text" ]] && handle_cmd "$text"
          offset=$((update_id+1))
          printf '%s' "$offset" >"$OFFSET_FILE"
        done
      fi
    else
      # Simple fallback without jq (single-user chat assumption)
      while read -r line; do
        case "$line" in
          *\"update_id\"*) update_id="$(printf '%s' "$line" | sed -n 's/.*"update_id":[ ]*\([0-9]\+\).*/\1/p')" ;;
          *\"text\"*)      text="$(printf '%s' "$line" | sed -n 's/.*"text":"\([^"]*\)".*/\1/p')"
                           [[ -n "${text:-}" ]] && handle_cmd "$text"
                           [[ -n "${update_id:-}" ]] && { offset=$((update_id+1)); printf '%s' "$offset" >"$OFFSET_FILE"; } ;;
        esac
      done < <(printf '%s' "$resp" | tr ',' '\n')
    fi
  done
}

case "${1:-}" in
  start)
    echo $$ > "$STATE_DIR/telecontrol.pid"
    send_msg "🤖 Telecontrol started (hard_on/off, status ready)"
    poll
    ;;
  stop)
    pkill -f 'BotA/tools/telecontrol\.sh' || true
    rm -f "$STATE_DIR/telecontrol.pid"
    ;;
  *)
    echo "usage: $0 {start|stop}"
    exit 2
    ;;
esac
