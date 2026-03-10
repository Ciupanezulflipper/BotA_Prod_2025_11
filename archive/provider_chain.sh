#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

SYM="${1:-}"
ALLOWED_FILE="$BASE/limits/pairs.allow"

# read whitelist (ignore comments/blank)
mapfile -t ALLOWED < <( [ -f "$ALLOWED_FILE" ] && grep -E '^[A-Za-z]+' "$ALLOWED_FILE" | tr '[:lower:]' '[:upper:]' || printf "" )

allowed() {
  local s="${1^^}"
  for a in "${ALLOWED[@]}"; do
    [[ "$a" == "$s" ]] && return 0
  done
  return 1
}

PRIMARY="${PRIMARY_PROVIDER:-twelve_data}"
FALLBACK="${FALLBACK_PROVIDER:-yahoo}"
YF_EN="${YF_ENABLE:-1}"

chain="$PRIMARY"

# allow Yahoo only if toggled on AND symbol is whitelisted (or no symbol provided)
if [[ "$YF_EN" == "1" ]]; then
  if [[ -z "${SYM}" ]]; then
    chain="$PRIMARY,$FALLBACK"
  else
    if allowed "$SYM"; then
      chain="$PRIMARY,$FALLBACK"
    fi
  fi
fi

printf '%s\n' "$chain"
