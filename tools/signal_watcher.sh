#!/bin/bash
# signal_watcher.sh — realtime BUY/SELL alerts (poll every 5m via cron)
# Rules:
# - Reads latest H1 signals by parsing tools/status_pretty.py output
# - Sends a Telegram alert ONLY when the H1 signal for a pair CHANGES
# - Dedup state persisted to $ROOT/cache/signal_state.json
# - Default pairs: EURUSD,GBPUSD (override with env PAIRS)

set -euo pipefail
ROOT="${HOME}/BotA"
LOG="${ROOT}/logs/signal_watcher.log"
STATE="${ROOT}/cache/signal_state.json"
PAIRS_DEFAULT="EURUSD,GBPUSD"
PAIRS="${PAIRS:-$PAIRS_DEFAULT}"

# Load Telegram env
if [ -f "${ROOT}/config/tele.env" ]; then
  # shellcheck disable=SC1091
  . "${ROOT}/config/tele.env"
fi

ts() { date -u +"%Y-%m-%d %H:%M:%S UTC"; }

send_html() {
  local chat_id="$TELEGRAM_CHAT_ID" html="$1"
  [ -n "${TELEGRAM_BOT_TOKEN:-}" ] || { echo "[warn] TELEGRAM_BOT_TOKEN missing"; return 0; }
  [ -n "${chat_id:-}" ] || { echo "[warn] TELEGRAM_CHAT_ID missing"; return 0; }
  curl -sS -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
       -d "chat_id=${chat_id}" \
       -d "parse_mode=HTML" \
       --data-urlencode "text=${html}" >/dev/null
}

init_state() {
  if [ ! -f "$STATE" ]; then
    echo "{}" > "$STATE"
  fi
}

read_state() {
  # jq might not exist; keep pure sh: grep the pair key from a simple lines file alternative
  # We’ll store as simple KEY=VALUE lines in a .kv sidecar to avoid jq dependency.
  if [ ! -f "${STATE}.kv" ]; then : > "${STATE}.kv"; fi
}

get_prev() {
  local key="$1"
  awk -F= -v k="$key" '$1==k{print $2}' "${STATE}.kv" | tail -n1
}

set_prev() {
  local key="$1" val="$2"
  # delete existing
  if grep -q "^${key}=" "${STATE}.kv" 2>/dev/null; then
    sed -i "s|^${key}=.*|${key}=${val}|" "${STATE}.kv"
  else
    echo "${key}=${val}" >> "${STATE}.kv"
  fi
}

# Parse H1 signal for "EUR/USD" section from status_pretty.py output
extract_signal_for_pair() {
  local pair="$1" text="$2"
  # Map EURUSD -> EUR/USD, GBPUSD -> GBP/USD, XAUUSD -> XAU/USD etc.
  local disp="$(echo "$pair" | sed -E 's/^([A-Z]{3})([A-Z]{3})/\1\/\2/')"
  # Find the header line, then read the immediate next non-empty line for BUY/SELL summary
  # Example lines:
  # "📊 EUR/USD H1 — 2025-10-28 09:00 UTC"
  # "🟢 BUY | RSI 61 | ⬆️ +3 | ..."
  # "🔴 SELL | RSI 38 | ⬇️ -2 | ..."
  awk -v sym="$disp" '
    BEGIN{found=0}
    $0 ~ sym" H1" {found=1; next}
    found==1 && $0 !~ /^[[:space:]]*$/ {print $0; exit}
  ' <<< "$text" \
  | sed -E 's/^[^A-Z]*//; s/\|.*$//' \
  | awk '{print toupper($1)}' \
  | sed -E 's/[^A-Z]//g'
}

main() {
  mkdir -p "$(dirname "$LOG")" "$(dirname "$STATE")"
  init_state; read_state

  # Get fresh status (advanced includes trend/vote lines)
  local raw
  if ! raw="$(python3 "${ROOT}/tools/status_pretty.py" advanced 2>/dev/null)"; then
    echo "[$(ts)] error: status_pretty.py failed" >> "$LOG"
    exit 0
  fi

  IFS=',' read -r -a arr <<< "$PAIRS"
  for p in "${arr[@]}"; do
    local sig prev key
    key="H1_${p}_SIG"
    sig="$(extract_signal_for_pair "$p" "$raw" || true)"
    if [ -z "$sig" ]; then
      echo "[$(ts)] warn: no H1 signal parsed for $p" >> "$LOG"
      continue
    fi
    prev="$(get_prev "$key")"
    if [ "$sig" != "$prev" ]; then
      # Signal changed — alert
      local disp="$(echo "$p" | sed -E 's/^([A-Z]{3})([A-Z]{3})/\1\/\2/')"
      local html="🚨 <b>${disp} — ${sig}</b>\nH1 signal changed at $(ts)\n(source: status_pretty)"
      send_html "$html"
      echo "[$(ts)] alert: $p $prev -> $sig" >> "$LOG"
      set_prev "$key" "$sig"
    else
      echo "[$(ts)] steady: $p remains $sig" >> "$LOG"
    fi
  done
  echo "[$(ts)] tick ok" >> "$LOG"
}

main
