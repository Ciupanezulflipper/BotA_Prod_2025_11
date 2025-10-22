#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
cd ~/BotA
# Load env if present
[ -f .env ] && export $(grep -v ^# .env | xargs) || true
reason="${1:-manual}"
python3 ~/bot-a/tools/status_cmd.py --heartbeat "reason=${reason}"
