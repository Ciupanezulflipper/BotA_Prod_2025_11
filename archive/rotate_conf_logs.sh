#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
LOG="$HOME/bot-a/logs/auto_conf.log"

[[ -f "$LOG.5" ]] && rm -f "$LOG.5"
for i in 4 3 2 1; do
  [[ -f "$LOG.$i" ]] && mv "$LOG.$i" "$LOG.$((i+1))"
done
[[ -f "$LOG" ]] && mv "$LOG" "$LOG.1"
: > "$LOG"
echo "rotated: $LOG"
