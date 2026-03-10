#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
cd /data/data/com.termux/files/home/BotA || exit 1

ROOT="/data/data/com.termux/files/home/BotA"
PIDFILE="${ROOT}/logs/state/prod_updater.pid"
OUTLOG="${ROOT}/logs/prod_updater.out"

cmd="${1:-status}"

is_running() {
  local pid=""
  [[ -f "${PIDFILE}" ]] && pid="$(cat "${PIDFILE}" 2>/dev/null || true)"
  [[ -n "${pid}" ]] || return 1
  kill -0 "${pid}" >/dev/null 2>&1
}

start_updater() {
  mkdir -p "${ROOT}/logs/state" >/dev/null 2>&1 || true
  touch "${OUTLOG}" >/dev/null 2>&1 || true
  if is_running; then
    echo "status=ALREADY_RUNNING pid=$(cat "${PIDFILE}" 2>/dev/null || true)"
    exit 0
  fi

  # Optional wake lock
  if command -v termux-wake-lock >/dev/null 2>&1; then
    termux-wake-lock >/dev/null 2>&1 || true
  fi

  nohup bash tools/run_updater_prod.sh >> "${OUTLOG}" 2>&1 </dev/null &
  pid="$!"
  echo "${pid}" > "${PIDFILE}"
  echo "status=STARTED pid=${pid} outlog=${OUTLOG}"
}

stop_updater() {
  if ! [[ -f "${PIDFILE}" ]]; then
    echo "status=NOT_RUNNING (no pidfile)"
    exit 0
  fi
  pid="$(cat "${PIDFILE}" 2>/dev/null || true)"
  if [[ -z "${pid}" ]]; then
    rm -f "${PIDFILE}" >/dev/null 2>&1 || true
    echo "status=NOT_RUNNING (empty pidfile cleared)"
    exit 0
  fi
  if kill -0 "${pid}" >/dev/null 2>&1; then
    kill "${pid}" >/dev/null 2>&1 || true
    for _ in 1 2 3 4 5; do
      sleep 1
      kill -0 "${pid}" >/dev/null 2>&1 || break
    done
    if kill -0 "${pid}" >/dev/null 2>&1; then
      kill -9 "${pid}" >/dev/null 2>&1 || true
    fi
    rm -f "${PIDFILE}" >/dev/null 2>&1 || true
    echo "status=STOPPED pid=${pid}"
  else
    rm -f "${PIDFILE}" >/dev/null 2>&1 || true
    echo "status=NOT_RUNNING (stale pidfile cleared pid=${pid})"
  fi
}

status_updater() {
  if is_running; then
    echo "status=RUNNING pid=$(cat "${PIDFILE}" 2>/dev/null || true)"
    echo "outlog=${OUTLOG}"
  else
    echo "status=NOT_RUNNING"
    [[ -f "${PIDFILE}" ]] && echo "note=pidfile_present_but_not_alive pid=$(cat "${PIDFILE}" 2>/dev/null || true)" || true
  fi
}

logs_updater() {
  touch "${OUTLOG}" >/dev/null 2>&1 || true
  echo "tail=80 ${OUTLOG}"
  tail -n 80 "${OUTLOG}" 2>/dev/null || true
}

case "${cmd}" in
  start) start_updater ;;
  stop)  stop_updater ;;
  restart) stop_updater; start_updater ;;
  status) status_updater ;;
  logs) logs_updater ;;
  *)
    echo "Usage: bash tools/prod_updaterctl.sh {start|stop|restart|status|logs}"
    exit 2
    ;;
esac
