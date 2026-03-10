#!/data/data/com.termux/files/usr/bin/bash
###############################################################################
# FILE: tools/pause_guard.sh
# GEM-60 2026-03-09: Daily R-based trading pause
#
# USAGE:
#   pause_guard.sh EURUSD        — pause EURUSD (manual -3R trigger)
#   pause_guard.sh EURUSD clear  — clear EURUSD pause
#   pause_guard.sh status        — show current pause state
#   pause_guard.sh reset         — clear ALL pauses (midnight reset)
#
# HOOK: signal_watcher_pro.sh line 713 reads state/pause automatically
# FORMAT: export PAUSE_<PAIR>=1
###############################################################################

ROOT="${HOME}/BotA"
PAUSE_FILE="${ROOT}/state/pause"
LOG="${ROOT}/logs/pause_guard.log"

log() { printf '[PAUSE_GUARD %s] %s\n' "$(date -u +%H:%MZ)" "$*" | tee -a "${LOG}" >&2; }

mkdir -p "${ROOT}/state" "${ROOT}/logs"

CMD="${1:-status}"
PAIR="$(printf '%s' "${2:-${1:-}}" | tr '[:lower:]' '[:upper:]' | tr -d '/ ')"

case "${CMD}" in

  status)
    if [[ ! -f "${PAUSE_FILE}" ]]; then
      log "No pause file — all pairs active"
      exit 0
    fi
    log "Current pause state:"
    cat "${PAUSE_FILE}"
    exit 0
    ;;

  reset)
    rm -f "${PAUSE_FILE}"
    log "All pauses cleared (midnight reset)"
    exit 0
    ;;

  clear)
    if [[ -z "${PAIR}" ]]; then
      log "ERROR: clear requires PAIR — e.g. pause_guard.sh EURUSD clear"
      exit 1
    fi
    if [[ ! -f "${PAUSE_FILE}" ]]; then
      log "${PAIR} — no pause file, nothing to clear"
      exit 0
    fi
    # Remove the line for this pair
    grep -v "export PAUSE_${PAIR}=1" "${PAUSE_FILE}" > "${PAUSE_FILE}.tmp" || true
    mv -f "${PAUSE_FILE}.tmp" "${PAUSE_FILE}"
    # If file is now empty, remove it
    [[ ! -s "${PAUSE_FILE}" ]] && rm -f "${PAUSE_FILE}"
    log "${PAIR} pause CLEARED — trading resumed"
    exit 0
    ;;

  EURUSD|GBPUSD|USDJPY|AUDUSD|USDCAD|USDCHF|NZDUSD)
    # Support both: "EURUSD clear" and "clear EURUSD"
    if [[ "${2:-}" == "clear" ]]; then
      PAIR="${CMD}"
      grep -v "export PAUSE_${PAIR}=1" "${PAUSE_FILE}" > "${PAUSE_FILE}.tmp" 2>/dev/null || true
      mv -f "${PAUSE_FILE}.tmp" "${PAUSE_FILE}" 2>/dev/null || true
      [[ ! -s "${PAUSE_FILE}" ]] && rm -f "${PAUSE_FILE}"
      log "${PAIR} pause CLEARED — trading resumed"
      exit 0
    fi
    # Pause this pair
    PAIR="${CMD}"
    # Remove existing entry if any, then append fresh
    if [[ -f "${PAUSE_FILE}" ]]; then
      grep -v "export PAUSE_${PAIR}=1" "${PAUSE_FILE}" > "${PAUSE_FILE}.tmp" || true
      mv -f "${PAUSE_FILE}.tmp" "${PAUSE_FILE}"
    fi
    echo "export PAUSE_${PAIR}=1" >> "${PAUSE_FILE}"
    log "${PAIR} PAUSED — daily -3R circuit breaker active (auto-clears at midnight UTC)"
    # Send Telegram notification
    if [[ -f "${ROOT}/.env" ]]; then
      set -a; source "${ROOT}/.env"; set +a
    fi
    if [[ -n "${TELEGRAM_BOT_TOKEN:-}" && -n "${TELEGRAM_CHAT_ID:-}" ]]; then
      MSG="⛔ BotA PAUSE: ${PAIR} paused — daily -3R circuit breaker triggered. Auto-clears midnight UTC."
      MSG="${MSG}" TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN}" TELEGRAM_CHAT_ID="${TELEGRAM_CHAT_ID}" \
      python3 -c '
import os,urllib.parse,urllib.request
token=os.environ["TELEGRAM_BOT_TOKEN"]; chat=os.environ["TELEGRAM_CHAT_ID"]; msg=os.environ["MSG"]
url=f"https://api.telegram.org/bot{token}/sendMessage"
data=urllib.parse.urlencode({"chat_id":chat,"text":msg}).encode()
urllib.request.urlopen(urllib.request.Request(url,data),timeout=10)
' 2>/dev/null || true
    fi
    exit 0
    ;;

  *)
    cat >&2 << 'USAGE'
Usage:
  pause_guard.sh EURUSD          — pause pair (manual -3R trigger)
  pause_guard.sh EURUSD clear    — clear pair pause
  pause_guard.sh status          — show all pauses
  pause_guard.sh reset           — clear all pauses
USAGE
    exit 1
    ;;
esac
