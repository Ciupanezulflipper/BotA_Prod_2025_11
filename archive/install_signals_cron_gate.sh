#!/data/data/com.termux/files/usr/bin/bash
# FILE: tools/install_signals_cron_gate.sh
# DESC: Option A cron installer — run watcher only when market_open.sh == Open (exit 0).
#       Removes any existing "signal_watcher_pro.sh --once" lines (and old cron.signals.log lines),
#       then installs ONE clean gated cron line.
#
# SAFETY:
# - Creates timestamped backups in ~/BotA/tmp/
# - Does not modify other cron entries beyond removing old watcher/cron.signals lines.

set -euo pipefail

ROOT="/data/data/com.termux/files/home/BotA"
TOOLS="${ROOT}/tools"
LOGS="${ROOT}/logs"
TMP="${ROOT}/tmp"

GATE="${TOOLS}/market_open.sh"
WATCHER="${TOOLS}/signal_watcher_pro.sh"
CRON_LOG="${LOGS}/cron.signals.log"

mkdir -p "${LOGS}" "${TMP}"

TS="$(date -u +%Y%m%d_%H%M%S)"
BACKUP="${TMP}/crontab.backup.${TS}"
NEW="${TMP}/crontab.new.${TS}"

echo "== install_signals_cron_gate =="
echo "TS=${TS}"
echo "BACKUP=${BACKUP}"
echo "NEW=${NEW}"
echo

if [ ! -x "${GATE}" ]; then
  echo "ERROR: gate not executable: ${GATE}"
  echo "Fix: chmod +x ${GATE}"
  exit 2
fi
if [ ! -x "${WATCHER}" ]; then
  echo "ERROR: watcher not executable: ${WATCHER}"
  echo "Fix: chmod +x ${WATCHER}"
  exit 2
fi

if crontab -l > "${BACKUP}" 2>/dev/null; then
  :
else
  : > "${BACKUP}"
fi

grep -vE 'tools/signal_watcher_pro\.sh --once' "${BACKUP}" | \
  grep -vE 'cron\.signals\.log' > "${NEW}" || true

cat >> "${NEW}" <<'CRON'
*/5 * * * * bash -lc '. "/data/data/com.termux/files/home/BotA/.env"; "/data/data/com.termux/files/home/BotA/tools/market_open.sh" >/dev/null 2>&1 && DRY_RUN_MODE="false" TELEGRAM_ENABLED="1" PAIRS="EURUSD GBPUSD USDJPY" TIMEFRAMES="M15" bash "/data/data/com.termux/files/home/BotA/tools/signal_watcher_pro.sh" --once' >> /data/data/com.termux/files/home/BotA/logs/cron.signals.log 2>&1
CRON

crontab "${NEW}"

echo "== Installed cron line (grep) =="
crontab -l | nl -ba | grep -n 'cron.signals.log' || true

echo
echo "== Quick gate check (NY now) =="
TZ=America/New_York date "+%a %Y-%m-%d %H:%M:%S %Z %z" || true
OUT="$("${GATE}" 2>&1 || true)"; EC=$?
printf "market_open stdout: %s\n" "${OUT}"
printf "market_open exit  : %s\n" "${EC}"

echo
echo "DONE"
