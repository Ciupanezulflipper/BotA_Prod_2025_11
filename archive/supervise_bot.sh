#!/data/data/com.termux/files/usr/bin/bash
# Phase 10: Enhanced supervisor — restart-on-failure, age check, log rotate, health ping.
# Env (optional):
#   INTERVAL_SEC=900
#   RESTART_AGE_SEC=1800     # restart if alert.log not updated within this many seconds
#   MAX_KB=2048 KEEP=5       # passed through to logrotate.sh
#   HEALTH_ON_START=1        # send health ping on (re)start
set -euo pipefail

ROOT="$HOME/BotA"
TOOLS="$ROOT/tools"
LOOP="$TOOLS/alert_loop.sh"
LOG="$ROOT/alert.log"

INTERVAL_SEC="${INTERVAL_SEC:-900}"
RESTART_AGE_SEC="${RESTART_AGE_SEC:-1800}"
HEALTH_ON_START="${HEALTH_ON_START:-1}"

logrotate() {
  MAX_KB="${MAX_KB:-2048}" KEEP="${KEEP:-5}" "$TOOLS/logrotate.sh" >/dev/null 2>&1 || true
}

is_running() {
  pgrep -f "$LOOP" >/dev/null 2>&1
}

log_age_sec() {
  [ -f "$LOG" ] || { echo 999999; return; }
  local mtime now
  mtime="$(stat -c %Y "$LOG" 2>/dev/null || stat -f %m "$LOG")"
  now="$(date +%s)"
  echo $(( now - mtime ))
}

start_loop() {
  nohup "$LOOP" >> "$LOG" 2>&1 &
  sleep 1
  if is_running; then
    echo "[supervise] (re)started alert_loop"
    if [ "${HEALTH_ON_START}" = "1" ]; then
      DRY=0 python3 "$TOOLS/health_ping.py" >/dev/null 2>&1 || true
    fi
  else
    echo "[supervise] FAILED to start alert_loop" >&2
    return 1
  fi
}

main() {
  logrotate
  if ! is_running; then
    echo "[supervise] alert_loop not running — starting"
    start_loop
    exit 0
  fi
  local age
  age="$(log_age_sec)"
  if [ "$age" -ge "$RESTART_AGE_SEC" ]; then
    echo "[supervise] alert.log stale (${age}s >= ${RESTART_AGE_SEC}s) — restarting loop"
    # try to kill old
    pkill -f "$LOOP" >/dev/null 2>&1 || true
    sleep 1
    start_loop
  else
    echo "[supervise] alert_loop healthy (log age ${age}s < ${RESTART_AGE_SEC}s)"
  fi
}
main "$@"
