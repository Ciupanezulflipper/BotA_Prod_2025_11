#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
LOG="$HOME/bot-a/logs/auto_conf.log"
PIDF="$HOME/bot-a/logs/auto_conf.pid"

if [[ -f "$PIDF" ]] && ps -p "$(cat "$PIDF")" >/dev/null 2>&1; then
  echo "auto_conf: RUNNING (pid $(cat "$PIDF"))"
else
  echo "auto_conf: NOT running"
fi

echo "---- last 25 log lines ----"
tail -n 25 "$LOG" 2>/dev/null || echo "(no log yet)"
