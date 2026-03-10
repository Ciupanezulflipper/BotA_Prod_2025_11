#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

###############################################################################
# FILE: tools/run_updater_prod.sh
#
# PURPOSE
# - Production "indicator updater loop" daemon target started by:
#     tools/prod_updaterctl.sh -> nohup bash tools/run_updater_prod.sh ...
# - Calls tools/indicators_updater.sh repeatedly to keep cache/indicators_* fresh.
#
# BUG FIX (2026-02-12)
# - Removed hard-forced defaults:
#     : "${PAIRS:=GBPUSD}"
#     : "${TIMEFRAMES:=M15}"
#
# PRECEDENCE (PAIRS)
#  1) UPDATER_PAIRS (env)
#  2) PAIRS (env)
#  3) state/analyze_pairs.txt   (first line: CSV -> space-separated)
#  4) config/strategy.env       (PAIRS=...)
#  5) config/pairs.txt          (one symbol per line)
#  6) fallback: "EURUSD GBPUSD"
#
# PRECEDENCE (TIMEFRAMES)
#  1) UPDATER_TIMEFRAMES (env)
#  2) TIMEFRAMES (env)
#  3) config/strategy.env       (TIMEFRAMES=...)
#  4) fallback: "M15"
#
# NOTES
# - Does NOT source .env files (avoids executing arbitrary code). Only parses safe keys.
# - Supports:
#     --dry-run  (compute/print PAIRS/TIMEFRAMES, then exit)
#     --once     (run one updater cycle, then exit)
#
# tests_passed=false (run your smoke test after install)
###############################################################################

ROOT="/data/data/com.termux/files/home/BotA"
cd "${ROOT}" || exit 1

STATE_PAIRS_FILE="${ROOT}/state/analyze_pairs.txt"
CFG_PAIRS_FILE="${ROOT}/config/pairs.txt"
STRATEGY_ENV="${ROOT}/config/strategy.env"

trim() {
  local s="${1:-}"
  s="$(printf '%s' "${s}" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
  printf '%s' "${s}"
}

normalize_list() {
  # commas -> spaces, squeeze whitespace, trim
  local s="${1:-}"
  s="$(printf '%s' "${s}" | tr ',' ' ' | tr -s ' ')"
  trim "${s}"
}

extract_env_value() {
  # Extract a value portion from an envfile assignment after KEY=...
  # - tolerates inline comments:
  #     PAIRS="EURUSD GBPUSD" # comment
  #     PAIRS=EURUSD # comment
  # - preserves content inside the first quoted string if present
  local raw="${1:-}"
  raw="$(trim "${raw}")"

  # If value begins with double quotes, capture first quoted segment
  if [[ "${raw}" =~ ^\"([^\"]*)\" ]]; then
    printf '%s' "$(trim "${BASH_REMATCH[1]}")"
    return 0
  fi

  # If value begins with single quotes, capture first quoted segment
  if [[ "${raw}" =~ ^\'([^\']*)\' ]]; then
    printf '%s' "$(trim "${BASH_REMATCH[1]}")"
    return 0
  fi

  # Unquoted: strip inline comments after # or ;
  raw="${raw%%#*}"
  raw="${raw%%;*}"
  printf '%s' "$(trim "${raw}")"
}

read_key_from_envfile() {
  # Reads KEY=... from a file (first match), returns value (normalized, comments stripped) or empty.
  local file="${1:?file_required}"
  local key="${2:?key_required}"

  local line=""
  # tolerate whitespace around '=' and leading whitespace
  line="$(sed -n -E "s/^[[:space:]]*${key}[[:space:]]*=[[:space:]]*(.*)\$/\1/p" "${file}" 2>/dev/null | head -n 1 || true)"
  if [[ -z "${line}" ]]; then
    printf ''
    return 0
  fi

  local val=""
  val="$(extract_env_value "${line}")"
  printf '%s' "$(normalize_list "${val}")"
}

read_pairs_from_state_file() {
  # state/analyze_pairs.txt first line: "EURUSD,GBPUSD" -> "EURUSD GBPUSD"
  local file="${1:?file_required}"
  local raw=""
  raw="$(head -n 1 "${file}" 2>/dev/null || true)"
  printf '%s' "$(normalize_list "${raw}")"
}

read_pairs_from_lines_file() {
  # config/pairs.txt: one symbol per line
  # - ignores blank lines
  # - ignores comment lines starting with # or ;
  # - strips inline comments after # or ;
  local file="${1:?file_required}"

  local joined=""
  joined="$(
    awk '
      /^[[:space:]]*($|#|;)/ { next }                      # skip blank/comment lines
      {
        sub(/[[:space:]]*#.*/, "", $0)                    # strip inline # comments
        sub(/[[:space:]]*;.*/, "", $0)                    # strip inline ; comments
        gsub(/[[:space:]]+/, " ", $0)                     # squeeze spaces
        gsub(/^[[:space:]]+|[[:space:]]+$/, "", $0)       # trim
        if ($0 != "") printf "%s ", $0
      }
      END { print "" }
    ' "${file}" 2>/dev/null || true
  )"

  printf '%s' "$(trim "$(normalize_list "${joined}")")"
}

pick_default_pairs() {
  local pairs=""

  # 3) state/analyze_pairs.txt
  if [[ -f "${STATE_PAIRS_FILE}" ]]; then
    pairs="$(read_pairs_from_state_file "${STATE_PAIRS_FILE}")"
  fi
  if [[ -n "${pairs}" ]]; then
    printf '%s' "${pairs}"
    return 0
  fi

  # 4) config/strategy.env
  if [[ -f "${STRATEGY_ENV}" ]]; then
    pairs="$(read_key_from_envfile "${STRATEGY_ENV}" "PAIRS")"
  fi
  if [[ -n "${pairs}" ]]; then
    printf '%s' "${pairs}"
    return 0
  fi

  # 5) config/pairs.txt
  if [[ -f "${CFG_PAIRS_FILE}" ]]; then
    pairs="$(read_pairs_from_lines_file "${CFG_PAIRS_FILE}")"
  fi
  if [[ -n "${pairs}" ]]; then
    printf '%s' "${pairs}"
    return 0
  fi

  # 6) fallback
  printf '%s' "EURUSD GBPUSD"
}

pick_default_timeframes() {
  local tfs=""

  # 3) config/strategy.env
  if [[ -f "${STRATEGY_ENV}" ]]; then
    tfs="$(read_key_from_envfile "${STRATEGY_ENV}" "TIMEFRAMES")"
  fi
  if [[ -n "${tfs}" ]]; then
    printf '%s' "${tfs}"
    return 0
  fi

  # 4) fallback
  printf '%s' "M15"
}

refresh_config() {
  # --- Defaults (only if env not provided) ---
  : "${UPDATER_SLEEP_SECONDS:=300}"    # 5 minutes
  : "${UPDATER_TIMEOUT_SECONDS:=180}"  # per-cycle timeout if `timeout` exists

  # PAIRS: env overrides first
  if [[ -n "${UPDATER_PAIRS:-}" ]]; then
    PAIRS="$(normalize_list "${UPDATER_PAIRS}")"
  elif [[ -n "${PAIRS:-}" ]]; then
    PAIRS="$(normalize_list "${PAIRS}")"
  else
    PAIRS="$(pick_default_pairs)"
  fi

  # TIMEFRAMES: env overrides first
  if [[ -n "${UPDATER_TIMEFRAMES:-}" ]]; then
    TIMEFRAMES="$(normalize_list "${UPDATER_TIMEFRAMES}")"
  elif [[ -n "${TIMEFRAMES:-}" ]]; then
    TIMEFRAMES="$(normalize_list "${TIMEFRAMES}")"
  else
    TIMEFRAMES="$(pick_default_timeframes)"
  fi

  # final safety: ensure non-empty
  if [[ -z "${PAIRS}" ]]; then
    PAIRS="EURUSD GBPUSD"
  fi
  if [[ -z "${TIMEFRAMES}" ]]; then
    TIMEFRAMES="M15"
  fi

  export PAIRS TIMEFRAMES UPDATER_SLEEP_SECONDS UPDATER_TIMEOUT_SECONDS
}

MODE="loop"
for arg in "$@"; do
  case "${arg}" in
    --dry-run) MODE="dry-run" ;;
    --once) MODE="once" ;;
    -h|--help)
      echo "Usage: bash tools/run_updater_prod.sh [--dry-run|--once]"
      exit 0
      ;;
  esac
done

refresh_config

if [[ "${MODE}" == "dry-run" ]]; then
  echo "[UPDATER_DRY_RUN] PAIRS=\"${PAIRS}\" TIMEFRAMES=\"${TIMEFRAMES}\" SLEEP=${UPDATER_SLEEP_SECONDS}s TIMEOUT=${UPDATER_TIMEOUT_SECONDS}s"
  exit 0
fi

trap 'echo "[UPDATER] received signal, exiting"; exit 0' INT TERM

while true; do
  # refresh each loop so state/analyze_pairs.txt (and config files) can change without restart
  refresh_config

  ts="$(date '+%Y-%m-%dT%H:%M:%S%z' 2>/dev/null || true)"
  echo "[UPDATER_LOOP ${ts}] run --once PAIRS=\"${PAIRS}\" TIMEFRAMES=\"${TIMEFRAMES}\""

  if command -v timeout >/dev/null 2>&1; then
    timeout "${UPDATER_TIMEOUT_SECONDS}" bash tools/indicators_updater.sh --once || true
  else
    bash tools/indicators_updater.sh --once || true
  fi

  if [[ "${MODE}" == "once" ]]; then
    exit 0
  fi

  sleep "${UPDATER_SLEEP_SECONDS}" || true
done
