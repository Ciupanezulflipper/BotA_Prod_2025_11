#!/bin/bash
# logrotate.sh — simple rotation for Bot A logs
set -euo pipefail
ROOT="$HOME/BotA"
LOG_DIR="$ROOT/logs"
mkdir -p "$LOG_DIR"

rotate(){  # rotate file if > 2MB
  local f="$1"
  [ -f "$f" ] || return 0
  local sz
  sz=$(wc -c <"$f")
  if [ "$sz" -gt $((2*1024*1024)) ]; then
    mv "$f" "${f}.$(date -u +%Y%m%d%H%M%S).bak"
    : > "$f"
  fi
}

rotate "$LOG_DIR/run.log"
rotate "$LOG_DIR/scheduler.log"
rotate "$LOG_DIR/daily_summary.log"

# keep only latest 7 backups per log
find "$LOG_DIR" -type f -name "*.bak" -printf "%T@ %p\n" \
  | sort -nr | awk 'NR>7 {print $2}' | xargs -r rm -f
