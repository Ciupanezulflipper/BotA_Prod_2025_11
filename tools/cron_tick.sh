#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
export PATH="$PREFIX/bin:$PATH"
export $(grep -v '^#' "$HOME/.env" | xargs) 2>/dev/null || true
WATCHLIST="${WATCHLIST:-EURUSD,XAUUSD}"
BASE_TF="${BASE_TF:-5min}"
CADENCE_MIN="${CADENCE_MIN:-30}"
REPOST_MIN="${REPOST_MIN:-90}"
OPEN_UTC="${OPEN_UTC:-06}"
CLOSE_UTC="${CLOSE_UTC:-21}"
LOG="$HOME/bot-a/auto_run.log"
mkdir -p "$HOME/bot-a"
hour=$(date -u +%H)
if [ "$hour" -ge "$OPEN_UTC" ] && [ "$hour" -lt "$CLOSE_UTC" ] && ping -c1 -W2 8.8.8.8 >/dev/null 2>&1; then
  echo "[cron] tick $(date -u +%FT%TZ) wl=[$WATCHLIST]" >> "$LOG"
  WATCHLIST="$WATCHLIST" BASE_TF="$BASE_TF" CADENCE_MIN="$CADENCE_MIN" REPOST_MIN="$REPOST_MIN" \
  PYTHONPATH="$HOME/bot-a" python "$HOME/bot-a/tools/autorun.py" --once || true
else
  echo "[cron] skipped (off-hours or offline) $(date -u +%FT%TZ)" >> "$LOG"
fi
