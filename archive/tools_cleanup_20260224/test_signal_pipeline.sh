#!/data/data/com.termux/files/usr/bin/bash
# BotA JSON contract health check for scoring_engine.sh | quality_filter.py
# File: tools/test_signal_pipeline.sh
#
# Purpose:
#   Run the A2 scoring pipeline for one PAIR/TF and assert that:
#     • It exits successfully (status 0)
#     • It emits EXACTLY ONE valid JSON object to stdout
#   On success → prints JSON to stdout and exits 0
#   On failure → logs error, shows raw payload, exits 1
#
# Usage:
#   DRY_RUN_MODE=true TELEGRAM_ENABLED=0 bash tools/test_signal_pipeline.sh EURUSD M15
#   (PAIR default: EURUSD, TF default: M15)

set -euo pipefail

# --------- core paths --------- #

ROOT="${BOTA_ROOT:-$HOME/BotA}"
TOOLS="$ROOT/tools"
LOGS="$ROOT/logs"
TMPDIR="$ROOT/tmp"

mkdir -p "$LOGS" "$TMPDIR"

PAIR="${1:-EURUSD}"
TF="${2:-M15}"

TS() {
  date +%Y-%m-%dT%H:%M:%S%z
}

log() {
  # level (INFO/OK/WARN/ERROR), message...
  local level="$1"; shift
  printf '[TEST %s %s] %s\n' "$level" "$(TS)" "$*" 1>&2
}

JSON_OUT="$TMPDIR/test_signal_${PAIR}_${TF}.json"
PIPE_LOG="$LOGS/pipeline_test.log"

# --------- main test --------- #

main() {
  log INFO "starting JSON contract test for PAIR=${PAIR} TF=${TF}"
  log INFO "ROOT=${ROOT} TOOLS=${TOOLS}"
  log INFO "DRY_RUN_MODE=${DRY_RUN_MODE:-true} TELEGRAM_ENABLED=${TELEGRAM_ENABLED:-0}"

  # Run scoring_engine.sh | quality_filter.py
  # Capture stdout in 'output', send stderr to PIPE_LOG
  local output
  if ! output="$(
    DRY_RUN_MODE="${DRY_RUN_MODE:-true}" TELEGRAM_ENABLED="${TELEGRAM_ENABLED:-0}" \
      bash "$TOOLS/scoring_engine.sh" "$PAIR" "$TF" 2>>"$PIPE_LOG" \
      | python3 "$TOOLS/quality_filter.py" 2>>"$PIPE_LOG"
  )"; then
    log ERROR "pipeline command failed (non-zero exit). See ${PIPE_LOG}"
    exit 1
  fi

  # Empty stdout is a hard failure for the JSON contract
  if [ -z "${output}" ]; then
    log ERROR "pipeline emitted EMPTY stdout — JSON contract violated"
    exit 1
  fi

  printf '%s\n' "${output}" > "${JSON_OUT}"

  # Validate JSON using python -m json.tool
  if python3 -m json.tool "${JSON_OUT}" >/dev/null 2>&1; then
    log OK "valid JSON emitted. File=${JSON_OUT}"
    # Echo the JSON so callers (or you) can inspect it directly
    printf '%s\n' "${output}"
    exit 0
  else
    log ERROR "INVALID JSON emitted. See ${JSON_OUT} and ${PIPE_LOG}"
    log ERROR "Raw payload below:"
    cat "${JSON_OUT}" 1>&2
    exit 1
  fi
}

main "$@"
```0
