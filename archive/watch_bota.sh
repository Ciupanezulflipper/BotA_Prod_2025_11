#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
SESSION="${1:-bota15}"
PAIR="${2:-EURUSD}"
TF="${3:-M15}"
INTERVAL="${4:-900}"   # seconds (15 min)

cmd="cd ~/BotA && export \$(grep -v ^# .env | xargs); \
while true; do \
  python -m BotA.tools.runner_confluence --pair $PAIR --tf $TF --dry-run=false --force || true; \
  sleep $INTERVAL; \
done"

tmux new -s "$SESSION" -d "$cmd"
echo "Started tmux session: $SESSION ($PAIR $TF every $((INTERVAL/60))m)"
