#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
export PATH="$PREFIX/bin:$PATH"
export $(grep -v '^#' "$HOME/.env" | xargs) 2>/dev/null || true

WATCHLIST="${WATCHLIST:-EURUSD,XAUUSD}"
BASE_TF="${BASE_TF:-5min}"
CADENCE_MIN="${CADENCE_MIN:-30}"     # set 45 in ~/.env if you prefer
REPOST_MIN="${REPOST_MIN:-90}"
OPEN_UTC="${OPEN_UTC:-06}"           # active window (UTC)
CLOSE_UTC="${CLOSE_UTC:-21}"
LOG="$HOME/bot-a/auto_run.log"
mkdir -p "$HOME/bot-a"

while true; do
  hour=$(date -u +%H)
  if [ "$hour" -lt "$OPEN_UTC" ] || [ "$hour" -ge "$CLOSE_UTC" ]; then
    echo "[watchdog] off-hours ${hour}Z -> sleep ${CADENCE_MIN}m" >> "$LOG"
    sleep ${CADENCE_MIN}m; continue
  fi
  if ! ping -c1 -W2 8.8.8.8 >/dev/null 2>&1; then
    echo "[watchdog] offline -> sleep 2m" >> "$LOG"
    sleep 2m; continue
  fi
  echo "[watchdog] tick $(date -u +%FT%TZ) wl=[$WATCHLIST] cadence=${CADENCE_MIN}m" >> "$LOG"
  WATCHLIST="$WATCHLIST" BASE_TF="$BASE_TF" CADENCE_MIN="$CADENCE_MIN" REPOST_MIN="$REPOST_MIN" \
  PYTHONPATH="$HOME/bot-a" python "$HOME/bot-a/tools/autorun.py" --once || true
  sleep ${CADENCE_MIN}m
done
