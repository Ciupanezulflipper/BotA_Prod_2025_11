#!/usr/bin/env bash
set -euo pipefail

# --- Config (reads your existing .env) ---
ROOT="${HOME}/bot-a"
TOOLS="${ROOT}/tools"
LOGS="${ROOT}/logs"
ENV_FILE="${HOME}/TomaMobileForexBot/.env"   # adjust if your .env lives elsewhere
[[ -f "${ENV_FILE}" ]] && set -a && . "${ENV_FILE}" && set +a

: "${TELEGRAM_BOT_TOKEN:?Missing TELEGRAM_BOT_TOKEN in .env}"
: "${TELEGRAM_CHAT_ID:?Missing TELEGRAM_CHAT_ID in .env}"

# What to watch (add/remove pidfiles as you wish)
WATCH_LIST=(
  "${LOGS}/runner_full_institutional.pid"
  "${LOGS}/runner_full_aggressive.pid"
)

# Behavior
SLEEP_SEC=60                 # check cadence
ALIVE_EVERY_HOURS=0          # 0 = no periodic alive pings; e.g. set to 6 for 6-hour heartbeat
STATE_DIR="${LOGS}/guard_state"
mkdir -p "${STATE_DIR}"

tg() {
  local text="$1"
  curl -sS -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
    -H 'Content-Type: application/json' \
    -d "{\"chat_id\":\"${TELEGRAM_CHAT_ID}\",\"text\":\"${text}\"}" >/dev/null || true
}

one_line_tail() {
  local file="$1"
  [[ -f "$file" ]] && tail -n 1 "$file" || echo "(no log)"
}

last_lines() {
  local file="$1"
  [[ -f "$file" ]] && tail -n 5 "$file" || echo "(no log)"
}

check_pidfile() {
  local pidfile="$1"
  local name="$(basename "$pidfile" .pid)"             # e.g. runner_full_institutional
  local state_file="${STATE_DIR}/${name}.state"
  local alive_file="${STATE_DIR}/${name}.alive_at"

  # Determine RUNNING?
  local running="no" pid=""

  if [[ -f "$pidfile" ]]; then
    pid="$(cat "$pidfile" 2>/dev/null || true)"
    if [[ -n "$pid" && -d "/proc/$pid" ]]; then
      running="yes"
    fi
  fi

  # First time? seed state
  [[ -f "$state_file" ]] || echo "UNKNOWN" > "$state_file"
  local prev_state
  prev_state="$(cat "$state_file" 2>/dev/null || echo UNKNOWN)"

  if [[ "$running" == "yes" ]]; then
    # Optional low-noise alive ping
    if (( ALIVE_EVERY_HOURS > 0 )); then
      local now=$(date +%s)
      local next_due=0
      [[ -f "$alive_file" ]] && next_due="$(cat "$alive_file" 2>/dev/null || echo 0)"
      if (( now >= next_due )); then
        tg "✅ ${name} is UP (pid ${pid}). Last log: $(one_line_tail "${LOGS}/${name}.log")"
        echo $(( now + ALIVE_EVERY_HOURS*3600 )) > "$alive_file"
      fi
    fi

    if [[ "$prev_state" != "UP" ]]; then
      tg "🟢 RECOVERY: ${name} is UP (pid ${pid})."
      echo "UP" > "$state_file"
    fi
  else
    # DOWN
    if [[ "$prev_state" != "DOWN" ]]; then
      tg "🔴 CRASH: ${name} is DOWN. Recent log:\n$(last_lines "${LOGS}/${name}.log")"
      echo "DOWN" > "$state_file"
    fi
  fi
}

echo "[guard] starting… watching: ${WATCH_LIST[*]}"
while true; do
  for pf in "${WATCH_LIST[@]}"; do
    check_pidfile "$pf"
  done
  sleep "${SLEEP_SEC}"
done
