#!/data/data/com.termux/files/usr/bin/bash
# FILE: tools/signal_watcher_guard.sh
# DESC: Single-instance guard for signal_watcher_pro.sh (prevents dupes, handles stale)
set -euo pipefail

ROOT="${HOME}/BotA"
TOOLS="${ROOT}/tools"
CACHE="${ROOT}/cache"
LOGS="${ROOT}/logs"
LOCK="${CACHE}/signal_watcher.lock"
PIDF="${CACHE}/signal_watcher.pid"
LOGF="${LOGS}/signal_watcher_guard.log"

mkdir -p "${CACHE}" "${LOGS}"

log(){ printf "%s [GUARD] %s\n" "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*" | tee -a "${LOGF}" ; }

# Acquire non-blocking file lock (fd 9). If locked, see if it's stale.
exec 9>"${LOCK}"
if ! flock -n 9; then
  if [[ -s "${PIDF}" ]]; then
    read -r opid < "${PIDF}" || opid=""
    if [[ -n "${opid:-}" ]] && kill -0 "${opid}" 2>/dev/null; then
      log "another watcher is active (pid=${opid}); exiting"
      exit 0
    else
      log "stale lock detected (pid=${opid:-?}); proceeding"
    fi
  else
    log "lock busy but no pid recorded; exiting to be safe"
    exit 0
  fi
fi

echo $$ > "${PIDF}"

cleanup(){
  rm -f "${PIDF}" 2>/dev/null || true
  log "shutdown"
}
trap cleanup INT TERM EXIT

# Extra safety: nuke any stray *older* pro watchers before we exec ours
# (If ours is first, there won't be any; if not, this cleans the mess.)
pkill -9 -f "tools/signal_watcher_pro\.sh" 2>/dev/null || true

log "exec pro watcher…"
exec bash "${TOOLS}/signal_watcher_pro.sh"
