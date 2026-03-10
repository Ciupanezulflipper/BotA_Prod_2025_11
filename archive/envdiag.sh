#!/usr/bin/env bash
set -Eeuo pipefail

REPO="${REPO:-$HOME/BotA}"
cd "$REPO"

load_env_file() {
  local f="$1"
  if [ -f "$f" ]; then
    while IFS= read -r line; do
      line="$(printf '%s\n' "$line" | sed 's/[[:space:]]*#.*$//')"
      [ -z "$line" ] && continue
      if echo "$line" | grep -qE '^[A-Za-z_][A-Za-z0-9_]*='; then
        key="${line%%=*}"
        val="${line#*=}"
        export "$key=$val"
      fi
    done < "$f"
  fi
}

load_env_file "$REPO/config/strategy.env"
load_env_file "$REPO/config/features.env"
load_env_file "$HOME/.env.runtime"

: "${PAIRS:=EURUSD,GBPUSD}"
: "${TF:=M15}"

echo "[envdiag] REPO=$REPO"
echo "[envdiag] TF=$TF"
echo "[envdiag] PAIRS(raw)=$PAIRS"

# Normalize to show what run_signal.sh will iterate:
norm="$(printf '%s\n' "$PAIRS" | tr ' ' ',' | tr -s ',')"
IFS=',' read -r -a _pairs <<< "$norm"
for sym in "${_pairs[@]}"; do
  sym="$(printf '%s' "$sym" | tr -d '[:space:]')"
  [ -z "$sym" ] && continue
  echo "[envdiag] pair -> $sym"
done
