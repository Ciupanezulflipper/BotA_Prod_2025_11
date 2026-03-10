#!/usr/bin/env bash
# tools/stop_supervisor.sh
# Stop the Bot-A supervisor.

set -euo pipefail
PIDFILE="${HOME}/.bot-a/run/supervisor.pid"

# For backward compatibility if we ever add a pidfile in the future:
if [[ -f "$PIDFILE" ]]; then
  pid=$(cat "$PIDFILE")
  if kill -0 "$pid" 2>/dev/null; then
    kill "$pid" || true
    echo "[stop] sent SIGTERM to supervisor ($pid)"
    exit 0
  fi
fi

# If no pidfile, kill by command name (safe: only our exact script)
pids=$(ps -o pid,cmd | awk '/bot-a\/tools\/supervisor\.sh/ && !/awk/ {print $1}')
if [[ -n "$pids" ]]; then
  echo "$pids" | xargs -r kill || true
  echo "[stop] killed supervisor pids: $pids"
else
  echo "[stop] supervisor not found"
fi
