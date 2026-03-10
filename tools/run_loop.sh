#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

# Load environment
if [ -f "$HOME/BotA/.env" ]; then
  set -a; . "$HOME/BotA/.env"; set +a
fi

LOG_DIR="$HOME/BotA/logs"
STATE_DIR="${STATE_DIR:-$HOME/BotA/state}"
mkdir -p "$LOG_DIR" "$STATE_DIR"

PAIRS_CSV="${PAIRS:-EURUSD}"
PROVIDER_ORDER="${PROVIDER_ORDER:-twelve_data,yahoo,alpha_vantage}"
DRY_RUN_MODE="${DRY_RUN_MODE:-false}"
TF15_SLEEP_PAD="${TF15_SLEEP_PAD:-90}"

LOOP_LOG="$LOG_DIR/loop.log"
LOCK_FILE="$STATE_DIR/loop.lock"
PID_FILE="$STATE_DIR/loop.pid"

ts() { date -u +"%Y-%m-%dT%H:%M:%SZ"; }

# Simple lock to avoid double schedulers (loop_guard/daemonctl also protect)
if [ -f "$LOCK_FILE" ] && kill -0 "$(cat "$PID_FILE" 2>/dev/null)" 2>/dev/null; then
  echo "[INFO] $(ts) another scheduler active; exiting." | tee -a "$LOOP_LOG"
  exit 0
fi
echo $$ > "$PID_FILE"
trap 'rm -f "$LOCK_FILE" "$PID_FILE"' EXIT
: > "$LOCK_FILE"

echo "[INFO] $(ts) Scheduler start (PAIRS=${PAIRS_CSV})"           | tee -a "$LOOP_LOG"
echo "[INFO] $(ts) Runtime: order=${PROVIDER_ORDER} dry_run=${DRY_RUN_MODE}" | tee -a "$LOOP_LOG"
echo "[INFO] $(ts) Version: routed-pauses-v1"                      | tee -a "$LOOP_LOG"

IFS=',' read -r -a PAIRS_ARR <<< "$PAIRS_CSV"

while true; do
  for pair in "${PAIRS_ARR[@]}"; do
    pair="$(echo "$pair" | xargs)"  # trim
    [ -z "$pair" ] && continue
    echo "[INFO] $(ts) cycle: dry_run=${DRY_RUN_MODE} provider_order=${PROVIDER_ORDER}" | tee -a "$LOOP_LOG"

    if bash "$HOME/BotA/tools/bot_state.sh" is_paused; then
      echo "[INFO] $(ts) Starting cycle for pair=${pair} (PAUSED)" | tee -a "$LOOP_LOG"
    else
      echo "[INFO] $(ts) Starting cycle for pair=${pair} (LIVE)"   | tee -a "$LOOP_LOG"
    fi

    # Routed call (will [skip] if paused, or [run] if live)
    if out="$("$HOME/BotA/tools/run_signal_routed.sh" "$pair" 2>&1)"; then
      echo "$out" | tee -a "$LOOP_LOG"
      echo "[INFO] $(ts) routed tick OK for ${pair}"              | tee -a "$LOOP_LOG"
    else
      rc=$?
      echo "$out" | tee -a "$LOOP_LOG"
      echo "[INFO] $(ts) routed tick FAIL for ${pair} rc=${rc}"   | tee -a "$LOOP_LOG"
    fi

    sleep "${TF15_SLEEP_PAD}"
  done
done
