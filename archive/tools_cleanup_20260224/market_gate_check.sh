#!/data/data/com.termux/files/usr/bin/bash
# FILE: tools/market_gate_check.sh
# DESC: Safe check of FX market gate (tools/market_open.sh) + next open time (Sunday 17:00 NY).
# SAFETY GOAL:
#   - MUST NOT kill / exit / infect your interactive shell if accidentally sourced OR pasted.
#   - MUST be safe even if the caller shell has `set -e` enabled.
#
# KEY SAFETY DESIGN:
#   - NO top-level `set -euo pipefail` (would leak if sourced/pasted).
#   - NO top-level `exit` (would close your terminal if pasted).
#   - All strict logic runs only inside a subshell main.

# Bash-only: if somehow run under sh, fail-safe (do nothing harmful).
if [[ -z "${BASH_VERSION:-}" ]]; then
  echo "ERROR: bash required. Run: bash tools/market_gate_check.sh" >&2
  # no exit (paste-safe); just stop.
  true
  return 0 2>/dev/null || true
fi

# Sourcing guard MUST be first. If sourced, return 0 so `set -e` in caller won't terminate the shell.
_bs0="${BASH_SOURCE[0]:-}"
_0="${0:-}"
if [[ -n "${_bs0}" && -n "${_0}" && "${_bs0}" != "${_0}" ]]; then
  echo "ERROR: Do not source this script. Run: bash tools/market_gate_check.sh" >&2
  return 0 2>/dev/null || true
fi

_bota_market_gate_main() {
  set -euo pipefail

  # Resolve BotA root robustly (works when executed, and also when the file content is pasted).
  local self script_dir root
  self="${BASH_SOURCE[0]:-${0:-}}"
  script_dir="$(cd "$(dirname "${self}")" 2>/dev/null && pwd -P || true)"
  root=""

  local -a candidates=()

  # Prefer script location (tools/)
  if [[ -n "${script_dir}" ]]; then
    candidates+=("${script_dir}/.." "${script_dir}")
  fi

  # PWD + standard locations
  candidates+=("$(pwd -P 2>/dev/null || true)")
  candidates+=("${HOME}/BotA" "/data/data/com.termux/files/home/BotA")

  # Walk upwards from PWD (up to 7 levels) to find tools/market_open.sh
  local walk parent i
  walk="$(pwd -P 2>/dev/null || true)"
  i=0
  while [[ -n "${walk}" && "${walk}" != "/" && "${i}" -lt 7 ]]; do
    candidates+=("${walk}")
    parent="$(cd "${walk}/.." 2>/dev/null && pwd -P || true)"
    [[ -z "${parent}" || "${parent}" == "${walk}" ]] && break
    walk="${parent}"
    i=$((i+1))
  done

  local c
  for c in "${candidates[@]}"; do
    c="$(cd "${c}" 2>/dev/null && pwd -P || true)"
    [[ -z "${c}" ]] && continue
    if [[ -x "${c}/tools/market_open.sh" ]]; then
      root="${c}"
      break
    fi
  done

  if [[ -z "${root}" ]]; then
    echo "ERROR: Could not locate BotA root (tools/market_open.sh not found)." >&2
    echo "Hint: cd /data/data/com.termux/files/home/BotA && bash tools/market_gate_check.sh" >&2
    return 0
  fi

  cd "${root}" 2>/dev/null || { echo "ERROR: cannot cd to BotA root: ${root}" >&2; return 0; }

  echo "BOTA_ROOT: ${root}"
  echo "NY_time :  $(TZ=America/New_York date)"
  echo "UTC_time:  $(date -u)"
  echo

  # Gate output + exit code (NO pipes while capturing rc)
  local phase rc
  phase=""
  rc=0
  set +e
  phase="$(bash tools/market_open.sh 2>/dev/null)"
  rc=$?
  set -e
  phase="$(printf '%s\n' "${phase}" | head -n1 | tr -d '[:space:]')"
  [[ -z "${phase}" ]] && phase="ERROR"

  echo "market_open.sh: ${phase} (exit=${rc})"
  if [[ "${rc}" -eq 0 && "${phase}" == "Open" ]]; then
    echo "status: OPEN"
    return 0
  fi

  echo "status: CLOSED"
  echo

  # Compute next open per YOUR active gate rule: Sunday 17:00 NY time.
  # Uses GNU date -d; if unsupported, prints UNKNOWN and returns 0.
  local dow hm_raw now_epoch hm open_epoch open_ny open_utc mins_left
  dow=""
  hm_raw=""
  now_epoch=""

  set +e
  dow="$(TZ=America/New_York date +%u 2>/dev/null)"        # 1=Mon .. 7=Sun
  hm_raw="$(TZ=America/New_York date +%H%M 2>/dev/null)"   # HHMM (zero-padded)
  now_epoch="$(TZ=America/New_York date +%s 2>/dev/null)"
  set -e

  dow="${dow:-0}"
  hm_raw="${hm_raw:-0000}"
  hm="$((10#${hm_raw}))"

  open_epoch=""
  open_ny=""

  set +e
  if [[ "${dow}" == "7" ]] && (( hm < 1700 )); then
    open_epoch="$(TZ=America/New_York date -d "today 17:00" +%s 2>/dev/null)"
    open_ny="$(TZ=America/New_York date -d "today 17:00" 2>/dev/null)"
  else
    open_epoch="$(TZ=America/New_York date -d "next sunday 17:00" +%s 2>/dev/null)"
    open_ny="$(TZ=America/New_York date -d "next sunday 17:00" 2>/dev/null)"
  fi
  set -e

  if [[ -z "${open_epoch}" ]]; then
    echo "next_open_NY : UNKNOWN (date -d unsupported?)"
    echo "next_open_UTC: UNKNOWN"
    echo "minutes_until_open: UNKNOWN"
    return 0
  fi

  open_utc="$(TZ=UTC date -d "@${open_epoch}" 2>/dev/null || true)"

  mins_left="UNKNOWN"
  if [[ "${now_epoch}" =~ ^[0-9]+$ && "${open_epoch}" =~ ^[0-9]+$ ]]; then
    mins_left="$(( (open_epoch - now_epoch) / 60 ))"
  fi

  echo "next_open_NY : ${open_ny:-UNKNOWN}"
  echo "next_open_UTC: ${open_utc:-UNKNOWN}"
  echo "minutes_until_open: ${mins_left}"
  return 0
}

# Run main in a subshell so strict-mode cannot leak into any parent shell (even if pasted).
( _bota_market_gate_main "$@" ) || true

# No exit here (paste-safe). Ensure success rc.
true
