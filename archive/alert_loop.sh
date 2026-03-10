#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

ROOT="$HOME/BotA"
TOOLS="$ROOT/tools"

PAIRS_DEFAULT=("EURUSD" "GBPUSD")
PAIRS=(${PAIRS_OVERRIDE:-"${PAIRS_DEFAULT[@]}"})

# 15 minutes default loop
INTERVAL_SEC="${INTERVAL_SEC:-900}"
ONCE="${ONCE:-0}"

# New hybrid thresholds (Rulebook v2.2)
MIN_WEIGHT_TRADE="${MIN_WEIGHT_TRADE:-3}"
MIN_WEIGHT_WATCH="${MIN_WEIGHT_WATCH:-1}"

# Cooldown in minutes for trade-tier alerts
COOL_DOWN_MIN="${COOL_DOWN_MIN:-30}"

# Volatility filter (uses run.log only, still STD-based for now)
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
  # 1) Refresh data for each pair
  for s in "${PAIRS[@]}"; do
    "$TOOLS/run_pair.sh" "$s" >/dev/null 2>&1 || true
    python3 "$TOOLS/data_fetch.py" "$s" >/dev/null 2>&1 || true
  done

  # 2) Early watch: HTF + scalper merge
  local out json enriched vol_ok filtered cnt msg
  out="$(python3 "$TOOLS/early_watch.py" --ignore-session 2>/dev/null || true)"
  printf "%s\n" "$out"

  # 3) Threshold + HYBRID policy (alert_rules decides tier)
  json="$(printf "%s\n" "$out" | python3 "$TOOLS/alert_rules.py" || true)"
  cnt="$(printf "%s" "$json" | python3 - <<'PY'
import sys, json
try: print(len(json.loads(sys.stdin.read())))
except Exception: print(0)
PY
)"
  if [ "${cnt:-0}" -le 0 ]; then
    echo "[alert_loop] no actionable alerts (MIN_WEIGHT_TRADE=${MIN_WEIGHT_TRADE})"
    return 0
  fi

  # 4) Analytics + session tagging
  enriched="$(printf "%s" "$json" | python3 "$TOOLS/analytics.py" || true)"
  enriched="$(printf "%s" "$enriched" | python3 "$TOOLS/session_enrich.py" || true)"

  # 5) Volatility filter (still global; ATR-style later)
  vol_ok="$(printf "%s" "$enriched" | VOL_MIN_STD="$VOL_MIN_STD" VOL_MIN_COUNT="$VOL_MIN_COUNT" python3 "$TOOLS/vol_filter.py" || true)"
  cnt="$(printf "%s" "$vol_ok" | python3 - <<'PY'
import sys, json
try: print(len(json.loads(sys.stdin.read())))
except Exception: print(0)
PY
)"
  if [ "${cnt:-0}" -le 0 ]; then
    echo "[alert_loop] alerts filtered by low volatility (std<$VOL_MIN_STD over $VOL_MIN_COUNT H1 steps)"
    return 0
  fi

  # 6) Cooldown / stateful suppression (trade-tier only)
  filtered="$(printf "%s" "$vol_ok" | COOL_DOWN_MIN="$COOL_DOWN_MIN" UPDATE_STATE=0 python3 "$TOOLS/alert_filter.py" || true)"
  cnt="$(printf "%s" "$filtered" | python3 - <<'PY'
import sys, json
try: print(len(json.loads(sys.stdin.read())))
except Exception: print(0)
PY
)"
  if [ "${cnt:-0}" -le 0 ]; then
    echo "[alert_loop] alerts suppressed by cooldown (${COOL_DOWN_MIN}m)"
    return 0
  fi

  # 7) Format + (optionally) push to Telegram
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
