#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${HOME}/BotA"
TOOLS="${ROOT}/tools"
LOGS="${ROOT}/logs"
mkdir -p "${LOGS}"

chmod +x "${TOOLS}/daemonctl.sh" \
         "${TOOLS}/watchdog.sh" \
         "${TOOLS}/install_cron.sh" || true

# Install/refresh cron
bash "${TOOLS}/install_cron.sh"

# Start aligned loop now (LIVE alerts mode by default)
ALIGN_BOUNDARY="${ALIGN_BOUNDARY:-true}" \
DRY_RUN_MODE="${DRY_RUN_MODE:-false}" \
WEAK_SIGNAL_MODE="${WEAK_SIGNAL_MODE:-false}" \
WEAK_SIGNAL_THRESHOLD="${WEAK_SIGNAL_THRESHOLD:-60}" \
bash "${TOOLS}/daemonctl.sh" start

echo "---- tail loop.log (last 40) ----"
tail -n 40 "${LOGS}/loop.log" || true

echo "---- status ----"
bash "${TOOLS}/daemonctl.sh" status
