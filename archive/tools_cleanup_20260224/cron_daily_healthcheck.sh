#!/data/data/com.termux/files/usr/bin/bash
# BotA — Daily Health Check Wrapper for Cron
# Runs health_check_signals.sh once per day and logs the outcome.
# Emits NOTHING to stdout (cron-safe). All output goes to stderr + log file.

set -euo pipefail

ROOT="${BOTA_ROOT:-$HOME/BotA}"
TOOLS="$ROOT/tools"
LOGS="$ROOT/logs"
mkdir -p "$LOGS"

LOGFILE="$LOGS/cron_daily_healthcheck.log"

ts() {
  date +%Y-%m-%dT%H:%M:%S%z
}

log() {
  printf '[CRON %s] %s\n' "$(ts)" "$*" >&2
}

log "starting daily BotA health check"

if DRY_RUN_MODE=true TELEGRAM_ENABLED=0 \
     bash "$TOOLS/health_check_signals.sh" 1>/dev/null 2>>"$LOGFILE"
then
    log "OK: daily health check passed"
else
    log "FAIL: daily health check FAILED — inspect $LOGFILE"
fi

log "health check run complete"
