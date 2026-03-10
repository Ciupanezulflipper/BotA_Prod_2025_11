#!/usr/bin/env bash
set -euo pipefail
LOG="$HOME/bot-a/logs/smart_eurusd.log"
: > "$LOG" || true
echo "=== smart_eurusd loop start (UTC $(date -u +"%Y-%m-%d %H:%M")) ===" >> "$LOG"
while true; do
  TS=$(date -u +"%Y-%m-%d %H:%M:%S")
  echo "[$TS] tick" >> "$LOG"
  PYTHONPATH="$HOME/bot-a" python "$HOME/bot-a/tools/smart_signal.py" --symbol EURUSD --threshold 0.80 --cooldown 20 >> "$LOG" 2>&1 || true
  sleep 300
done
