#!/usr/bin/env bash
# tools/digest_loop.sh
# Send Bot-A daily recap once per day at 00:01 UTC. No cron needed.

set -euo pipefail

PY_HOME="${HOME}/bot-a"
PYTHONPATH="${PY_HOME}"
DIGEST="${PY_HOME}/tools/nightly_digest.py"

LOG_DIR="${HOME}/.bot-a/logs"
RUN_DIR="${HOME}/.bot-a/run"
mkdir -p "${LOG_DIR}" "${RUN_DIR}"

PIDFILE="${RUN_DIR}/digest_loop.pid"

# Keep device awake during loop (Termux only; ignore if missing)
if command -v termux-wake-lock >/dev/null 2>&1; then
  termux-wake-lock || true
fi

# single-instance guard
if [[ -f "${PIDFILE}" ]] && kill -0 "$(cat "${PIDFILE}")" 2>/dev/null; then
  echo "[digest_loop] already running: PID $(cat "${PIDFILE}")"
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

# Sleep to next 00:01 UTC
sleep_to_0001() {
  local now next target sleep_s
  now=$(date -u +%s)
  # compute next 00:01:00 UTC
  target=$(date -u -d "@$now" +'%Y-%m-%d 00:01:00')
  next=$(date -u -d "$target" +%s)
  if [[ $now -ge $next ]]; then
    # move to tomorrow 00:01
    next=$(( next + 24*3600 ))
  fi
  sleep_s=$(( next - now ))
  [[ $sleep_s -gt 0 ]] && sleep "$sleep_s"
}

run_once() {
  local day log rc
  day=$(date -u +%Y%m%d)
  log="${LOG_DIR}/digest-${day}.log"

  {
    echo "========== $(date -u '+%Y-%m-%d %H:%M:%S UTC') =========="
    echo "[digest_loop] running nightly_digest.py --yesterday --send"
  } >> "${log}"

  PYTHONPATH="${PYTHONPATH}" \
  python "${DIGEST}" --yesterday --send >> "${log}" 2>&1 || rc=$?

  rc=${rc:-0}
  echo "[digest_loop] exit code: ${rc}" >> "${log}"
  echo "" >> "${log}"
}

# align then loop forever
sleep_to_0001
while true; do
  run_once || true
  sleep_to_0001
done
