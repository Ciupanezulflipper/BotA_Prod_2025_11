#!/usr/bin/env bash
set -euo pipefail
APP="$HOME/bot-a"
PIDFILE="$HOME/.bot-a/run/digest_loop.pid"

stop_it() {
  if [[ -f "$PIDFILE" ]]; then
    pid=$(cat "$PIDFILE" 2>/dev/null || true)
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid" || true
      sleep 1
    fi
    rm -f "$PIDFILE"
  else
    pids=$(ps -o pid,cmd | awk '/bot-a\/tools\/digest_loop\.sh/ && !/awk/ {print $1}')
    [[ -n "$pids" ]] && echo "$pids" | xargs -r kill || true
  fi
}

stop_it
nohup "$APP/tools/digest_loop.sh" >/dev/null 2>&1 &
echo "digest loop restarted. pid: $!"
