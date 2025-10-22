#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
cd "$HOME/bot-a/tools"

LOG="$HOME/bot-a/logs/runner_loop.log"
echo "==== RUNNER LOOP START $(date -Is) ====" | tee -a "$LOG"

while true; do
  date -Is | tee -a "$LOG"
  python3 runner_confluence.py --pair EURUSD --tf M15 --force --dry-run >>"$LOG" 2>&1 || true
  sleep 300   # wait 5 minutes
done
