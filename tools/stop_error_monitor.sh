#!/usr/bin/env bash
# tools/stop_error_monitor.sh
# Stop the background error monitor.

set -euo pipefail
PIDFILE="${HOME}/.bot-a/run/error_monitor.pid"

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
