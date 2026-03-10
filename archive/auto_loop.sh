#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

APP="$HOME/bot-a"
LOG="$APP/auto_run.log"
CADENCE_MIN="${CADENCE_MIN:-30}"

echo "[auto_loop] starting (cadence=${CADENCE_MIN}m) $(date -u +%FT%TZ)" | tee -a "$LOG"

while true; do
  echo "[auto_loop] tick $(date -u +%FT%TZ)" | tee -a "$LOG"
  # Load env
  if [ -f "$HOME/.env" ]; then
    # shellcheck disable=SC2046
    export $(grep -v '^#' "$HOME/.env" | xargs) || true
  fi
  # One run (respecting OPEN/CLOSE in autorun.py)
  PYTHONPATH="$APP" python "$APP/tools/autorun.py" --once || true

  # Small random jitter (10–60s) to avoid exact cadence alignment
  JITTER=$(( (RANDOM % 51) + 10 ))
  SLEEP=$(( CADENCE_MIN*60 + JITTER ))
  sleep "$SLEEP"
done
