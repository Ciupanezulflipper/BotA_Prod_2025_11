#!/usr/bin/env bash
set -euo pipefail
APP="$HOME/bot-a"
PIDFILE="$HOME/.bot-a/run/signal_runner.pid"

stop_it() {
  if [[ -f "$PIDFILE" ]]; then
    pid=$(cat "$PIDFILE" 2>/dev/null || true)
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid" || true
      sleep 1
    fi
    rm -f "$PIDFILE"
  else
    # fallback by name
    pids=$(ps -o pid,cmd | awk '/bot-a\/tools\/runloop\.sh/ && !/awk/ {print $1}')
    [[ -n "$pids" ]] && echo "$pids" | xargs -r kill || true
  fi
}

stop_it
nohup "$APP/tools/runloop.sh" >/dev/null 2>&1 &
echo "runloop restarted. pid: $!"
