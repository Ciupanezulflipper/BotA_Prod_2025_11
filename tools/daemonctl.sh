#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="${HOME}/BotA"
TOOLS="${ROOT}/tools"
STATE="${ROOT}/state"
LOGS="${ROOT}/logs"
mkdir -p "${STATE}" "${LOGS}"

# Load env if present (expects KEY=VALUE lines, no 'export' required)
if [[ -f "${ROOT}/.env" ]]; then
  set -a
  # shellcheck disable=SC1090
  . "${ROOT}/.env"
  set +a
fi

SYMBOLS="${SYMBOLS:-EURUSD,GBPUSD}"
TF="${TF:-15}"
LIMIT="${LIMIT:-150}"
ALIGN_BOUNDARY="${ALIGN_BOUNDARY:-true}"
DRY_RUN_MODE="${DRY_RUN_MODE:-false}"
WEAK_SIGNAL_MODE="${WEAK_SIGNAL_MODE:-false}"
WEAK_SIGNAL_THRESHOLD="${WEAK_SIGNAL_THRESHOLD:-60}"

pidfile="${STATE}/loop.pid"
logfile="${LOGS}/loop.log"

start() {
  if [[ -f "${pidfile}" ]] && ps -p "$(cat "${pidfile}" 2>/dev/null)" >/dev/null 2>&1; then
    echo "already running: PID $(cat "${pidfile}")"
    return 0
  fi

  nohup env \
    SYMBOLS="${SYMBOLS}" \
    TF="${TF}" \
    LIMIT="${LIMIT}" \
    ALIGN_BOUNDARY="${ALIGN_BOUNDARY}" \
    DRY_RUN_MODE="${DRY_RUN_MODE}" \
    WEAK_SIGNAL_MODE="${WEAK_SIGNAL_MODE}" \
    WEAK_SIGNAL_THRESHOLD="${WEAK_SIGNAL_THRESHOLD}" \
    bash "${TOOLS}/run_loop.sh" daemon >> "${logfile}" 2>&1 &

  echo $! > "${pidfile}"
  echo "started: PID $(cat "${pidfile}")"
}

stop() {
  if [[ -f "${pidfile}" ]]; then
    pkill -TERM -P "$(cat "${pidfile}" 2>/dev/null)" 2>/dev/null || true
    kill "$(cat "${pidfile}" 2>/dev/null)" 2>/dev/null || true
    rm -f "${pidfile}"
    echo "stopped"
  else
    echo "not running"
    return 1
  fi
}

restart() { stop || true; sleep 1; start; }

status() {
  if [[ -f "${pidfile}" ]] && ps -fp "$(cat "${pidfile}" 2>/dev/null)" >/dev/null 2>&1; then
    echo "STATUS OK — PID $(cat "${pidfile}")"
  else
    echo "STATUS DOWN"
    return 1
  fi
}

tail_log() { tail -n 120 "${logfile}" || true; }

case "${1:-}" in
  start)   start ;;
  stop)    stop ;;
  restart) restart ;;
  status)  status ;;
  tail)    tail_log ;;
  *) echo "usage: $0 {start|stop|restart|status|tail}"; exit 2 ;;
esac
