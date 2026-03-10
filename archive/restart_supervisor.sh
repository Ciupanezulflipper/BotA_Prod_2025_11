#!/usr/bin/env bash
set -euo pipefail
APP="$HOME/bot-a"

# kill any existing supervisor
pids=$(ps -o pid,cmd | awk '/bot-a\/tools\/supervisor\.sh/ && !/awk/ {print $1}')
[[ -n "$pids" ]] && echo "$pids" | xargs -r kill || true
sleep 1

# start fresh
nohup "$APP/tools/supervisor.sh" >/dev/null 2>&1 &
echo "supervisor restarted. pid: $!"
