#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

LOG="$HOME/bot-a/logs/status_watch.log"
mkdir -p "$(dirname "$LOG")"

if ! pgrep -f "status_cmd.py.*--daemon" >/dev/null 2>&1; then
  echo "[$(date -u +'%F %T UTC')] WARN: statusd down; restarting" >>"$LOG"
  "$HOME/bot-a/tools/run_statusd.sh" >>"$LOG" 2>&1
else
  echo "[$(date -u +'%F %T UTC')] OK: statusd alive" >>"$LOG"
fi
