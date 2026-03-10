#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
LOG="$HOME/bot-a/logs/auto_h5.log"
PID="$HOME/bot-a/logs/auto_h5.pid"
mkdir -p "$HOME/bot-a/logs"
echo $$ > "$PID"
while true; do
  PYTHONPATH="$HOME/bot-a" python3 "$HOME/bot-a/tools/signal_h5_sent.py" || true
  sleep 60
done >>"$LOG" 2>&1
