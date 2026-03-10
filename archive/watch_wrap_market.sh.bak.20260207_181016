#!/data/data/com.termux/files/usr/bin/bash
# FILE: tools/watch_wrap_market.sh
# DESC: Market-gated single-instance wrapper around watcher (now using guard)
set -euo pipefail

ROOT="${HOME}/BotA"
TOOLS="${ROOT}/tools"
CACHE="${ROOT}/cache"
LOGS="${ROOT}/logs"
WATCHER="${TOOLS}/signal_watcher_guard.sh"
LOCK="${CACHE}/watch_wrap.lock"
LOGFILE="${LOGS}/watcher_nohup.log"

mkdir -p "${CACHE}" "${LOGS}"

log(){ printf "%s [WRAP] %s\n" "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*" | tee -a "${LOGFILE}" ; }
hb(){ date +%s > "${CACHE}/watcher.heartbeat"; }

# Ensure only one wrapper instance
exec 9>"${LOCK}"
if ! flock -n 9; then
  log "another wrapper already running; exiting"
  exit 0
fi

# Clean any stray watchers/guards at start
pkill -9 -f "tools/signal_watcher_guard\.sh" 2>/dev/null || true
pkill -9 -f "tools/signal_watcher_pro\.sh" 2>/dev/null || true

CHILD_PID=""

cleanup(){
  log "signal caught — shutting down"
  if [[ -n "${CHILD_PID:-}" ]] && kill -0 "${CHILD_PID}" 2>/dev/null; then
    kill -15 "${CHILD_PID}" 2>/dev/null || true
    wait "${CHILD_PID}" 2>/dev/null || true
    log "child ${CHILD_PID} stopped"
  fi
  exit 0
}
trap cleanup INT TERM

log "start pid=$$"

while :; do
  hb
  PHASE="Unknown"
  if [[ -x "${TOOLS}/market_open.sh" ]]; then
    _raw="$("${TOOLS}/market_open.sh" 2>/dev/null || true)"
    _raw="$(printf %s "${_raw}" | head -n1 | tr -d '[:space:]')"
    if [[ "${_raw}" == "Open" || "${_raw}" == "Closed" ]]; then
      PHASE="${_raw}"
    fi
    unset _raw
  fi
  log "phase: ${PHASE}"

  if [[ "${PHASE}" == "Open" ]]; then
    if [[ -n "${CHILD_PID:-}" ]] && kill -0 "${CHILD_PID}" 2>/dev/null; then
      : # already running
    else
      log "starting watcher (guard)…"
      bash "${WATCHER}" &
      CHILD_PID=$!
      log "guard pid=${CHILD_PID}"
    fi
    sleep 60
  else
    if [[ -n "${CHILD_PID:-}" ]] && kill -0 "${CHILD_PID}" 2>/dev/null; then
      log "market closed — stopping guard ${CHILD_PID}"
      kill -15 "${CHILD_PID}" 2>/dev/null || true
      wait "${CHILD_PID}" 2>/dev/null || true
      log "guard stopped"
      CHILD_PID=""
    fi
    sleep 300
  fi
done
