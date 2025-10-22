#!/usr/bin/env bash
set -euo pipefail

# -------- settings (no changes to ~/.env) --------
SYMBOL="EURUSD"
LOG_DIR="$HOME/bot-a/logs"
LOG_FILE="$LOG_DIR/auto_eurusd.log"
PYTHONPATH="$HOME/bot-a"
RUN_EVERY_SEC=60             # run once per minute (rotator will skip if capped)
LOCKFILE="$LOG_DIR/auto_eurusd.lock"

# Provider order & soft rate caps (session-only; does NOT touch .env)
export ROTATOR_ORDER="${ROTATOR_ORDER:-twelvedata,alphavantage,finnhub,eodhd,yahoo}"
export TWELVEDATA_RATE_PER_MIN="${TWELVEDATA_RATE_PER_MIN:-1}"
export ALPHAVANTAGE_RATE_PER_MIN="${ALPHAVANTAGE_RATE_PER_MIN:-4}"
export FINNHUB_RATE_PER_MIN="${FINNHUB_RATE_PER_MIN:-2}"
export EODHD_RATE_PER_MIN="${EODHD_RATE_PER_MIN:-2}"
export NEWSAPI_RATE_PER_MIN="${NEWSAPI_RATE_PER_MIN:-2}"
export MARKETEAUX_RATE_PER_MIN="${MARKETEAUX_RATE_PER_MIN:-3}"

mkdir -p "$LOG_DIR"

log(){ printf "%s | %s\n" "$(date -u '+UTC %F %T')" "$*" | tee -a "$LOG_FILE"; }

log "=== auto_eurusd: START ==="

# Prevent overlapping runs
exec 9>"$LOCKFILE"
if ! flock -n 9; then
  log "Another auto_eurusd instance is running; exiting."
  exit 0
fi

# Main loop
while true; do
  START_TS=$(date +%s)
  log "tick -> running final_runner for ${SYMBOL}"

  # One full pass (1h / 4h / 1d) + Telegram handled inside final_runner
  if ! PYTHONPATH="$PYTHONPATH" python "$HOME/bot-a/tools/final_runner.py" --symbol "$SYMBOL" --send >>"$LOG_FILE" 2>&1; then
     log "[WARN] final_runner returned non-zero (likely rate/temporary provider error)."
  fi

  # Optional: write a tiny provider-usage snapshot line if present
  if ls "$LOG_DIR"/provider_usage-*.csv >/dev/null 2>&1; then
    last_csv=$(ls -1 "$LOG_DIR"/provider_usage-*.csv | tail -n1)
    log "[usage] $(tail -n1 "$last_csv")"
  fi

  # Sleep aligned to ~1 minute
  END_TS=$(date +%s)
  ELAPSED=$(( END_TS - START_TS ))
  SLEEP=$(( RUN_EVERY_SEC - ELAPSED ))
  (( SLEEP < 5 )) && SLEEP=5
  sleep "$SLEEP"
done
