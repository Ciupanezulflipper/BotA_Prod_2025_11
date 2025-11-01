#!/bin/bash
# run_bot.sh — stop old, start tg_bot.py with correct env & logs

set -euo pipefail
cd "$HOME/BotA"

ENV="$HOME/BotA/config/tele.env"
[ -f "$ENV" ] || { echo "❌ $ENV missing. Run tele_env_sync.sh first."; exit 1; }
# shellcheck disable=SC1090
source "$ENV"

echo "🧹 Stopping prior tg_bot.py (if any)…"
pkill -f "python3 .*tg_bot.py" 2>/dev/null || true
sleep 1

echo "🚀 Starting bot… (logging to run.log)"
nohup python3 -u tg_bot.py >> run.log 2>&1 & disown
sleep 2

echo "📜 Tail run.log (last 80 lines):"
tail -n 80 run.log || true
