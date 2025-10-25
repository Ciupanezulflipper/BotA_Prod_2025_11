#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

ROOT="$HOME/BotA"
TOOLS="$ROOT/tools"

PAIRS_DEFAULT=("EURUSD" "GBPUSD")
PAIRS=(${PAIRS_OVERRIDE:-"${PAIRS_DEFAULT[@]}"})
INTERVAL_SEC="${INTERVAL_SEC:-900}"
ONCE="${ONCE:-0}"
MIN_WEIGHT="${MIN_WEIGHT:-2}"
COOL_DOWN_MIN="${COOL_DOWN_MIN:-30}"

# Volatility filter (uses run.log only)
VOL_MIN_STD="${VOL_MIN_STD:-0.00015}"
VOL_MIN_COUNT="${VOL_MIN_COUNT:-20}"

# Quiet hours (UTC), e.g. "22-06" to silence pushes 22:00..05:59
QUIET_HOURS="${QUIET_HOURS:-}"

if [ -z "${TELEGRAM_BOT_TOKEN:-}" ] || [ -z "${TELEGRAM_CHAT_ID:-}" ]; then
  echo "[alert_loop] ⚠️ TELEGRAM creds not set — will run but skip pushes."
  PUSH=0
else
  PUSH=1
fi

in_quiet_hours () {
  [ -z "$QUIET_HOURS" ] && return 1
  local h now start end
  now="$(date -u '+%H')"
  start="${QUIET_HOURS%-*}"
  end="${QUIET_HOURS#*-}"
  # pad
  start=$(printf "%02d" "$start") || start="$start"
  end=$(printf "%02d" "$end") || end="$end"
  h="$now"
  if [ "$start" -le "$end" ]; then
    [ "$h" -ge "$start" ] && [ "$h" -lt "$end" ]
  else
    # wraps midnight
    [ "$h" -ge "$start" ] || [ "$h" -lt "$end" ]
  fi
}

run_cycle () {
  for s in "${PAIRS[@]}"; do
    "$TOOLS/run_pair.sh" "$s" >/dev/null || true
    python3 "$TOOLS/data_fetch.py" "$s" >/dev/null || true
  done

  local out json actionable enriched vol_ok filtered cnt msg
  out="$(python3 "$TOOLS/early_watch.py" --ignore-session 2>/dev/null || true)"
  printf "%s\n" "$out"

  json="$(printf "%s\n" "$out" | MIN_WEIGHT="$MIN_WEIGHT" python3 "$TOOLS/alert_rules.py" || true)"
  cnt="$(printf "%s" "$json" | python3 - <<'PY'
import sys, json
try: print(len(json.loads(sys.stdin.read())))
except: print(0)
PY
)"
  if [ "${cnt:-0}" -le 0 ]; then
    echo "[alert_loop] no actionable alerts (MIN_WEIGHT=$MIN_WEIGHT)"
    return 0
  fi

  enriched="$(printf "%s" "$json" | python3 "$TOOLS/analytics.py" || true)"
  vol_ok="$(printf "%s" "$enriched" | VOL_MIN_STD="$VOL_MIN_STD" VOL_MIN_COUNT="$VOL_MIN_COUNT" python3 "$TOOLS/vol_filter.py" || true)"
  cnt="$(printf "%s" "$vol_ok" | python3 - <<'PY'
import sys, json
try: print(len(json.loads(sys.stdin.read())))
except: print(0)
PY
)"
  if [ "${cnt:-0}" -le 0 ]; then
    echo "[alert_loop] alerts filtered by low volatility (std<$VOL_MIN_STD over $VOL_MIN_COUNT H1 steps)"
    return 0
  fi

  filtered="$(printf "%s" "$vol_ok" | COOL_DOWN_MIN="$COOL_DOWN_MIN" UPDATE_STATE=0 python3 "$TOOLS/alert_filter.py" || true)"
  cnt="$(printf "%s" "$filtered" | python3 - <<'PY'
import sys, json
try: print(len(json.loads(sys.stdin.read())))
except: print(0)
PY
)"
  if [ "${cnt:-0}" -le 0 ]; then
    echo "[alert_loop] alerts suppressed by cooldown (${COOL_DOWN_MIN}m)"
    return 0
  fi

  msg="$(printf "%s" "$filtered" | python3 "$TOOLS/format_alert.py")"
  if [ "${DRY:-0}" = "1" ]; then
    echo "---- ALERT_PREVIEW ----"
    printf "%s\n" "$msg"
  elif in_quiet_hours; then
    echo "[alert_loop] quiet hours active ($QUIET_HOURS UTC): push suppressed"
  elif [ "$PUSH" -eq 1 ]; then
    if python3 "$TOOLS/telegram_push.py" "$msg" >/dev/null; then
      printf "%s" "$filtered" | COOL_DOWN_MIN="$COOL_DOWN_MIN" UPDATE_STATE=1 python3 "$TOOLS/alert_filter.py" >/dev/null || true
    else
      echo "[alert_loop] ⚠️ telegram push failed" >&2
    fi
  fi
}

if [ "${ONCE:-0}" = "1" ]; then
  run_cycle
  exit 0
fi

while :; do
  run_cycle
  sleep "$INTERVAL_SEC"
done
