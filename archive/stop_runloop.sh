#!/usr/bin/env bash
# tools/stop_runloop.sh
# Stop the background runloop started by runloop.sh

set -euo pipefail
PIDFILE="${HOME}/.bot-a/run/signal_runner.pid"

if [[ -f "${PIDFILE}" ]]; then
  pid=$(cat "${PIDFILE}")
  if kill -0 "${pid}" 2>/dev/null; then
    kill "${pid}" || true
    echo "[stop] sent SIGTERM to ${pid}"
  else
    echo "[stop] stale pid ${pid}; removing file"
  fi
  rm -f "${PIDFILE}"
else
  echo "[stop] no pidfile found"
fi
