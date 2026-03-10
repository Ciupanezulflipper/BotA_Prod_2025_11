#!/data/data/com.termux/files/usr/bin/bash
# BotA Signals Health Check
# File: tools/health_check_signals.sh
#
# PURPOSE
#   Quick end-to-end sanity test for the M15 signal pipeline:
#     data_fetch_candles.sh → scoring_engine.sh → quality_filter.py → signal_watcher_pro.sh
#   Runs the watcher in DRY_RUN mode with a dedicated CSV and verifies:
#     - Exit code is 0
#     - Health-check CSV exists
#     - Header + one row per pair (EURUSD, GBPUSD, USDJPY, EURJPY)
#
# ACCEPTANCE CRITERIA
#   PASS if:
#     • signal_watcher_pro.sh exits 0
#     • $LOGS/alerts_healthcheck.csv exists
#     • alerts_healthcheck.csv has ≥ 5 lines (1 header + 4 rows)
#     • Each pair in PAIRS has at least one row (column 2) in the healthcheck CSV
#
# USAGE
#   DRY_RUN_MODE=true TELEGRAM_ENABLED=0 bash tools/health_check_signals.sh
#
# NOTES
#   - Does NOT touch your main logs/alerts.csv file.
#   - Writes diagnostic info to logs/health_check_signals.log.

set -euo pipefail

# --------- core paths --------- #
ROOT="${BOTA_ROOT:-$HOME/BotA}"
TOOLS="$ROOT/tools"
LOGS="$ROOT/logs"

mkdir -p "$LOGS"

# --------- pairs / timeframes --------- #
PAIRS_DEFAULT="EURUSD GBPUSD USDJPY EURJPY"
TIMEFRAMES_DEFAULT="M15"

PAIRS="${PAIRS:-$PAIRS_DEFAULT}"
TIMEFRAMES="${TIMEFRAMES:-$TIMEFRAMES_DEFAULT}"

# Dedicated health-check artifacts
HC_CSV="${LOGS}/alerts_healthcheck.csv"
HC_LOG="${LOGS}/health_check_signals.log"

# --------- helpers --------- #
ts() {
  date +%Y-%m-%dT%H:%M:%S%z
}

say() {
  printf '[HEALTH %s] %s\n' "$(ts)" "$*"
}

fail() {
  say "FAIL: $*"
  exit 1
}

# --------- main --------- #
main() {
  # Ensure we are in repo root
  cd "$ROOT" 2>/dev/null || fail "cannot cd to ROOT=${ROOT}"

  # Reset health-check artifacts
  : >"$HC_LOG" 2>/dev/null || fail "cannot write to ${HC_LOG}"
  rm -f "$HC_CSV"

  say "starting BotA signals health check"
  say "PAIRS=\"${PAIRS}\" TIMEFRAMES=\"${TIMEFRAMES}\""

  # Run watcher in dry-run mode with dedicated CSV
  say "running signal_watcher_pro.sh --once (DRY_RUN_MODE=true, TELEGRAM_ENABLED=0)"
  if ! DRY_RUN_MODE=true TELEGRAM_ENABLED=0 ALERTS_CSV="$HC_CSV" \
      bash "$TOOLS/signal_watcher_pro.sh" --once >>"$HC_LOG" 2>&1; then
    fail "signal_watcher_pro.sh exited non-zero (see ${HC_LOG})"
  fi

  # Check CSV exists
  if [ ! -f "$HC_CSV" ]; then
    fail "health-check CSV ${HC_CSV} was not created"
  fi

  # Check line count: expect at least 1 header + 4 rows
  local lines
  lines="$(wc -l <"$HC_CSV" 2>/dev/null || echo 0)"
  if [ "$lines" -lt 5 ]; then
    fail "expected at least 5 lines in ${HC_CSV} (header + 4 rows), got ${lines}"
  fi

  # Verify each pair appears at least once (column 2 of CSV, skipping header)
  local missing=0
  local pair
  for pair in $PAIRS; do
    if ! awk -F',' -v p="$pair" 'NR>1 && $2==p {found=1} END{exit found?0:1}' "$HC_CSV"; then
      say "WARN: no row for pair ${pair} in ${HC_CSV}"
      missing=1
    fi
  done

  if [ "$missing" -ne 0 ]; then
    fail "one or more pairs missing rows in ${HC_CSV} (see ${HC_CSV} and ${HC_LOG})"
  fi

  say "OK: signals health check passed for PAIRS=\"${PAIRS}\" TIMEFRAMES=\"${TIMEFRAMES}\""
  say "CSV=${HC_CSV} LOG=${HC_LOG}"
}

main "$@"
