#!/usr/bin/env bash
# tools/runloop.sh
# Run signal_runner.py every 15 minutes with simple logging and a PID guard.
# Works in Termux. No extra deps.

set -euo pipefail

# --- Config (override via env if you want) -----------------------------------
INTERVAL_MIN="${BOT_A_INTERVAL_MIN:-15}"          # schedule interval (minutes)
PY_HOME="${HOME}/bot-a"                           # project root
PYTHONPATH="${PY_HOME}"                           # module path for children
RUNNER="${PY_HOME}/tools/signal_runner.py"        # orchestrator
LOG_DIR="${BOT_A_LOG_DIR:-${HOME}/.bot-a/logs}"   # logs location
RUN_DIR="${HOME}/.bot-a/run"                      # pid location
SUMMARY="--summary-send"                          # add a compact summary each cycle
SESSIONS="${BOT_A_SESSIONS:-london_ny}"           # session gate stays active

# --- Setup -------------------------------------------------------------------
mkdir -p "${LOG_DIR}" "${RUN_DIR}"
PIDFILE="${RUN_DIR}/signal_runner.pid"

# Optional: hold wakelock if available (keeps device awake while running loop)
if command -v termux-wake-lock >/dev/null 2>&1; then
  termux-wake-lock || true
fi

# Guard: refuse to start if already running
if [[ -f "${PIDFILE}" ]] && kill -0 "$(cat "${PIDFILE}")" 2>/dev/null; then
  echo "[runloop] already running with PID $(cat "${PIDFILE}")"
  exit 0
fi

echo $$ > "${PIDFILE}"

cleanup() {
  rm -f "${PIDFILE}"
  if command -v termux-wake-unlock >/dev/null 2>&1; then
    termux-wake-unlock || true
  fi
}
trap cleanup EXIT INT TERM

# Align sleep to the next N-minute boundary (UTC)
sleep_to_next_slot() {
  local n="${INTERVAL_MIN}"
  local now next slot sleep_s
  now=$(date -u +%s)
  # minutes since epoch, rounded up to next slot
  slot=$(( ( (now/60)/n*n + n ) * 60 ))
  sleep_s=$(( slot - now ))
  [[ "${sleep_s}" -gt 0 ]] && sleep "${sleep_s}"
}

run_once() {
  # daily log file (UTC)
  local day log rc
  day=$(date -u +%Y%m%d)
  log="${LOG_DIR}/runner-${day}.log"

  # banner
  {
    echo "========== $(date -u '+%Y-%m-%d %H:%M:%S UTC') =========="
    echo "[runloop] calling signal_runner.py"
  } >> "${log}"

  # call runner (both pairs); keep its own internal summary
  PYTHONPATH="${PYTHONPATH}" \
  python "${RUNNER}" --send ${SUMMARY} --sessions "${SESSIONS}" >> "${log}" 2>&1 || rc=$?

  rc=${rc:-0}
  echo "[runloop] exit code: ${rc}" >> "${log}"
  echo "" >> "${log}"
  return "${rc}"
}

# First align, then run forever
sleep_to_next_slot
while true; do
  run_once || true
  sleep_to_next_slot
done
