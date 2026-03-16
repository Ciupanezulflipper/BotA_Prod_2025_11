#!/data/data/com.termux/files/usr/bin/bash
###############################################################################
# FILE: tools/indicators_updater.sh
# PURPOSE (Step 16N fix):
#   Keep the Step 16K "fetch-before-build" wiring, but add resilience against:
#     - Yahoo HTTP 429 rate limiting
#     - Transient DNS/connectivity failures
#
# DESIGN:
#   For each PAIR + TF:
#     1) Fetch fresh raw candles FIRST:
#          tools/data_fetch_candles.sh <PAIR> <TF>
#        Writes: cache/<PAIR>_<TF>.json
#     2) Build indicators from that cache:
#          python3 tools/build_indicators.py ...
#        Writes: cache/indicators_<PAIR>_<TF>.json
#
# FAIL-CLOSED (important):
#   - If fetch fails AFTER retries => skip build (do NOT touch indicators output).
#   - This preserves true staleness; watcher uses indicators FILE MTIME as proven.
#
# RATE LIMIT / NETWORK CONTROL:
#   - FETCH_RETRIES (default 5): retry count per pair/tf
#   - FETCH_BACKOFF_BASE (default 10s): exponential backoff base
#   - FETCH_BACKOFF_MAX (default 180s): cap backoff
#   - FETCH_MIN_GAP_SECS (default 3s): min sleep between fetches to reduce 429
###############################################################################
set -euo pipefail
shopt -s inherit_errexit 2>/dev/null || true

ROOT="${HOME}/BotA"
TOOLS="${ROOT}/tools"
CACHE="${ROOT}/cache"
LOGS="${ROOT}/logs"

PAIRS="${PAIRS:-"EURUSD GBPUSD XAUUSD USDJPY EURJPY"}"
TIMEFRAMES="${TIMEFRAMES:-"M15 H4 D1"}"

FETCH_RETRIES="${FETCH_RETRIES:-5}"
FETCH_BACKOFF_BASE="${FETCH_BACKOFF_BASE:-10}"
FETCH_BACKOFF_MAX="${FETCH_BACKOFF_MAX:-180}"
FETCH_MIN_GAP_SECS="${FETCH_MIN_GAP_SECS:-3}"

log() { printf '%s\n' "$*" >&2; }

need_file() {
  local f="$1"
  if [[ ! -f "$f" ]]; then
    log "[UPDATER] ERROR: missing file: $f"
    return 1
  fi
  return 0
}

need_exec() {
  local f="$1"
  if [[ ! -x "$f" ]]; then
    log "[UPDATER] ERROR: not executable: $f"
    return 1
  fi
  return 0
}

# Best-effort: determine supported CLI flags from build_indicators.py --help output.
# If help is empty/unavailable, return "no_cli" so caller can fail closed or fallback.
build_indicators_cli_args() {
  local pair="$1" tf="$2" in_path="$3" out_path="$4"
  local help=""
  help="$(python3 "${TOOLS}/build_indicators.py" --help 2>&1 || python3 "${TOOLS}/build_indicators.py" -h 2>&1 || true)"
  if [[ -z "${help}" ]]; then
    echo "no_cli"
    return 0
  fi
  supports() { grep -qF -- "$1" <<<"${help}"; }

  # one arg per line
  if supports "--pair"; then
    printf '%s\n' "--pair" "${pair}"
  elif supports "--symbol"; then
    printf '%s\n' "--symbol" "${pair}"
  fi

  if supports "--tf"; then
    printf '%s\n' "--tf" "${tf}"
  elif supports "--timeframe"; then
    printf '%s\n' "--timeframe" "${tf}"
  elif supports "--interval"; then
    printf '%s\n' "--interval" "${tf}"
  fi

  if supports "--in"; then
    printf '%s\n' "--in" "${in_path}"
  elif supports "--input"; then
    printf '%s\n' "--input" "${in_path}"
  elif supports "--json"; then
    printf '%s\n' "--json" "${in_path}"
  fi

  if supports "--out"; then
    printf '%s\n' "--out" "${out_path}"
  elif supports "-o"; then
    printf '%s\n' "-o" "${out_path}"
  fi
  return 0
}

find_latest_backup_updater() {
  local latest=""
  latest="$(ls -1t "${TOOLS}/indicators_updater.sh.bak_pre16k_"* 2>/dev/null | head -n 1 || true)"
  printf '%s' "${latest}"
}

# Retry wrapper around data_fetch_candles.sh
fetch_with_retry() {
  local pair="$1" tf="$2" in_path="$3"
  local attempt=1
  local rc=0

  while (( attempt <= FETCH_RETRIES )); do
    if bash "${TOOLS}/data_fetch_candles.sh" "${pair}" "${tf}" >/dev/null 2>>"${LOGS}/error.log"; then
      # min gap to reduce 429 bursts across many pairs
      sleep "${FETCH_MIN_GAP_SECS}" 2>/dev/null || true
      [[ -s "${in_path}" ]] && return 0
      log "[UPDATER] FETCH  FAIL   ${pair} ${tf} input_missing_or_empty=${in_path} (attempt=${attempt}/${FETCH_RETRIES})"
      rc=1
    else
      rc=$?
      log "[UPDATER] FETCH  FAIL   ${pair} ${tf} rc=${rc} (attempt=${attempt}/${FETCH_RETRIES})"
    fi

    # Backoff + jitter (0-4s)
    # backoff = min(max, base * 2^(attempt-1)) + jitter
    local pow=$(( attempt - 1 ))
    local backoff=$(( FETCH_BACKOFF_BASE * (1 << pow) ))
    if (( backoff > FETCH_BACKOFF_MAX )); then backoff="${FETCH_BACKOFF_MAX}"; fi
    local jitter=$(( RANDOM % 5 ))
    local sleep_s=$(( backoff + jitter ))

    # For last attempt, don't sleep again.
    if (( attempt == FETCH_RETRIES )); then
      break
    fi

    log "[UPDATER] RETRY  SLEEP  ${pair} ${tf} sleep_s=${sleep_s} (backoff=${backoff}+jitter=${jitter})"
    sleep "${sleep_s}" 2>/dev/null || true

    attempt=$(( attempt + 1 ))
  done

  return 1
}

log "------------------------------------------------------------"
log "[UPDATER] indicators_updater.sh start (Step 16N retry/backoff+pacing)"
log "[UPDATER] ROOT=${ROOT}"
log "[UPDATER] PAIRS=${PAIRS}"
log "[UPDATER] TIMEFRAMES=${TIMEFRAMES}"
log "[UPDATER] FETCH_RETRIES=${FETCH_RETRIES} FETCH_BACKOFF_BASE=${FETCH_BACKOFF_BASE} FETCH_BACKOFF_MAX=${FETCH_BACKOFF_MAX} FETCH_MIN_GAP_SECS=${FETCH_MIN_GAP_SECS}"
log "------------------------------------------------------------"

need_file "${TOOLS}/build_indicators.py" || exit 1
need_file "${TOOLS}/data_fetch_candles.sh" || exit 1
need_exec "${TOOLS}/data_fetch_candles.sh" || exit 1

build_fail_count=0
fetch_fail_count=0

for pair in ${PAIRS}; do
  for tf in ${TIMEFRAMES}; do
    in_path="${CACHE}/${pair}_${tf}.json"
    out_path="${CACHE}/indicators_${pair}_${tf}.json"

    log "[UPDATER] ---- ${pair} ${tf} ----"

    # 1) Fetch fresh raw cache first (with retry/backoff)
    if fetch_with_retry "${pair}" "${tf}" "${in_path}"; then
      log "[UPDATER] FETCH  OK     ${pair} ${tf} -> ${in_path}"
      python3 "${TOOLS}/api_credit_tracker.py" increment 1 >>"${LOGS}/error.log" 2>&1 || true
    else
      fetch_fail_count=$((fetch_fail_count+1))
      log "[UPDATER] FETCH  FAIL   ${pair} ${tf} after_retries=${FETCH_RETRIES} (skip build; see ${LOGS}/error.log)"
      continue
    fi

    # 2) Build indicators
    cli_lines="$(build_indicators_cli_args "${pair}" "${tf}" "${in_path}" "${out_path}")"
    if [[ "${cli_lines}" == "no_cli" ]]; then
      build_fail_count=$((build_fail_count+1))
      log "[UPDATER] BUILD  FAIL   ${pair} ${tf} could_not_read_cli_help (will try backup updater later)"
      continue
    fi

    mapfile -t ARGS <<<"${cli_lines}"

    if PAIR="${pair}" TF="${tf}" INPUT_JSON="${in_path}" OUTPUT_JSON="${out_path}" \
      python3 "${TOOLS}/build_indicators.py" "${ARGS[@]}" 2>>"${LOGS}/error.log"; then
      log "[UPDATER] BUILD  OK     ${pair} ${tf} -> ${out_path}"
    else
      build_fail_count=$((build_fail_count+1))
      log "[UPDATER] BUILD  ERROR  ${pair} ${tf} build_indicators.py failed (see ${LOGS}/error.log)"
      continue
    fi

    if [[ ! -s "${out_path}" ]]; then
      build_fail_count=$((build_fail_count+1))
      log "[UPDATER] OUTPUT FAIL   ${pair} ${tf} missing_or_empty=${out_path}"
      continue
    fi
  done
done

# Optional fallback: if any builds failed and a pre16k backup exists, run it once.
if (( build_fail_count > 0 )); then
  backup="$(find_latest_backup_updater)"
  if [[ -n "${backup}" && -f "${backup}" ]]; then
    log "[UPDATER] FALLBACK: build_fail_count=${build_fail_count} -> running backup updater: ${backup}"
    if PAIRS="${PAIRS}" TIMEFRAMES="${TIMEFRAMES}" bash "${backup}" 2>>"${LOGS}/error.log"; then
      log "[UPDATER] FALLBACK OK (backup updater completed)"
    else
      log "[UPDATER] FALLBACK FAIL (backup updater also failed; see ${LOGS}/error.log)"
      exit 1
    fi
  else
    log "[UPDATER] FALLBACK SKIP (no pre16k backup found); build_fail_count=${build_fail_count}"
    exit 1
  fi
fi

log "[UPDATER] DONE fetch_fail_count=${fetch_fail_count} build_fail_count=${build_fail_count}"
exit 0
