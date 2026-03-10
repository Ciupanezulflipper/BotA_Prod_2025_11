#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
cd "$HOME/BotA"

# Rotate run.log -> run-YYYYmmdd.log and truncate current
if [ -s run.log ]; then
  stamp="$(date -u +%Y%m%d)"
  mv run.log "logs/run-$stamp.log" 2>/dev/null || {
    mkdir -p logs
    mv run.log "logs/run-$stamp.log"
  }
fi
: > run.log

# Fresh heartbeat file (not tracked)
date -u +%s > heartbeat.txt
echo "[rotate_logs] done at $(date -u +'%F %T')"
