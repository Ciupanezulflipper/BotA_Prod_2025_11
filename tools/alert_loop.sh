#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

ROOT="$HOME/BotA"
TOOLS="$ROOT/tools"

# Config
PAIRS_DEFAULT=("EURUSD" "GBPUSD")
PAIRS=(${PAIRS_OVERRIDE:-"${PAIRS_DEFAULT[@]}"})
INTERVAL_SEC="${INTERVAL_SEC:-900}"           # 15 minutes
ONCE="${ONCE:-0}"                             # set to 1 to run one cycle
MIN_WEIGHT="${MIN_WEIGHT:-2}"                 # abs(weighted) threshold

# Telegram availability
if [ -z "${TELEGRAM_BOT_TOKEN:-}" ] || [ -z "${TELEGRAM_CHAT_ID:-}" ]; then
  echo "[alert_loop] ⚠️ TELEGRAM creds not set — will run but skip pushes."
  PUSH=0
else
  PUSH=1
fi

run_cycle () {
  # 1) Update snapshots & cache
  for s in "${PAIRS[@]}"; do
    "$TOOLS/run_pair.sh" "$s" >/dev/null || true
    python3 "$TOOLS/data_fetch.py" "$s" >/dev/null || true
  done

  # 2) Run watcher (ignore session gates)
  local out actionable json msg
  out="$(python3 "$TOOLS/early_watch.py" --ignore-session 2>/dev/null || true)"
  printf "%s\n" "$out"

  # 3) Apply rules (threshold / WATCH keyword)
  json="$(printf "%s\n" "$out" | MIN_WEIGHT="$MIN_WEIGHT" python3 "$TOOLS/alert_rules.py" || true)"
  actionable="$(printf "%s" "$json" | python3 - <<'PY'
import sys, json
try:
    arr=json.loads(sys.stdin.read())
    print(len(arr))
except Exception:
    print(0)
PY
)"
  if [ "${actionable:-0}" -gt 0 ]; then
    msg="$(printf "%s" "$json" | python3 "$TOOLS/format_alert.py")"
    if [ "${DRY:-0}" = "1" ]; then
      echo "---- ALERT_PREVIEW ----"
      printf "%s\n" "$msg"
    elif [ "$PUSH" -eq 1 ]; then
      python3 "$TOOLS/telegram_push.py" "$msg" >/dev/null || echo "[alert_loop] ⚠️ telegram push failed" >&2
    fi
  else
    echo "[alert_loop] no actionable alerts (MIN_WEIGHT=$MIN_WEIGHT)"
  fi
}

if [ "$ONCE" = "1" ]; then
  run_cycle
  exit 0
fi

while :; do
  run_cycle
  sleep "$INTERVAL_SEC"
done
