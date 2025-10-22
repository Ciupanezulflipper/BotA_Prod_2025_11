#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
# load env for cron context
if [ -f "$HOME/.env.runtime" ]; then
  export $(grep -E '^[A-Z0-9_]+=' "$HOME/.env.runtime" | xargs)
fi
cd "$HOME/BotA"

# dry-run and log
out=$(python -m BotA.tools.runner_confluence --pair EURUSD --tf M15 --dry-run 2>/dev/null)
echo "$out" >> "$HOME/BotA/run.log" 2>&1

# send for BUY/SELL
if echo "$out" | grep -q "Action: BUY\|Action: SELL"; then
  python -m BotA.tools.runner_confluence --pair EURUSD --tf M15 --force >> "$HOME/BotA/run.log" 2>&1
fi
