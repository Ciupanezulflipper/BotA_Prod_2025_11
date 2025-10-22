#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
LOG="$HOME/BotA/run.log"
MAX=10000
[ -f "$LOG" ] || exit 0
LINES=$(wc -l < "$LOG")
if [ "$LINES" -gt "$MAX" ]; then
  tail -n "$MAX" "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"
  echo "[rotate_logs] truncated to $MAX lines at $(date -u +"%F %T")" >> "$LOG"
fi
