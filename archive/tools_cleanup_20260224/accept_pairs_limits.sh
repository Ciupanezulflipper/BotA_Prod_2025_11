#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ ! -f "$BASE/limits/pairs.allow" ]]; then
  echo "[accept] ❌ Missing whitelist: $BASE/limits/pairs.allow"
  exit 1
fi

# Load env for keys and PAIRS
if [[ -f "$BASE/.env" ]]; then
  set -a
  # shellcheck source=/dev/null
  . "$BASE/.env"
  set +a
fi

PAIRS_STR="${PAIRS:-EURUSD,GBPUSD,XAUUSD}"
IFS=',' read -r -a REQ_PAIRS <<< "$(echo "$PAIRS_STR" | tr -d ' ' | tr '[:lower:]' '[:upper:]')"

# Build whitelist set
mapfile -t ALLOWED < <(grep -E '^[A-Za-z]+' "$BASE/limits/pairs.allow" | tr '[:lower:]' '[:upper:]')
is_allowed() {
  local s="$1"
  for a in "${ALLOWED[@]}"; do [[ "$a" == "$s" ]] && return 0; done
  return 1
}

echo "[accept] Whitelist: ${ALLOWED[*]}"
echo "[accept] Requested PAIRS: ${REQ_PAIRS[*]}"

# Validate requested pairs against whitelist
for p in "${REQ_PAIRS[@]}"; do
  if ! is_allowed "$p"; then
    echo "[accept] ❌ '$p' is NOT in whitelist ($BASE/limits/pairs.allow)"
    exit 1
  fi
done
echo "[accept] ✅ All requested pairs are within whitelist."

# Show safe provider chain per symbol
for p in "${REQ_PAIRS[@]}"; do
  CHAIN="$(bash "$BASE/tools/provider_chain.sh" "$p")"
  echo "[accept] $p provider_chain = $CHAIN"
done

# Single safe probe per symbol (TD only; consumes ≤ |PAIRS| credits)
fail=0
for p in "${REQ_PAIRS[@]}"; do
  if bash "$BASE/tools/td_probe.sh" "$p"; then
    : # ok
  else
    echo "[accept] ❌ probe failed for $p"
    fail=1
  fi
done
if [[ $fail -ne 0 ]]; then
  exit 2
fi
echo "[accept] ✅ Probes OK."

# Quota snapshot (minute must be ≤ 8 while idle; day under free-plan cap)
if [[ -x "$BASE/tools/status_quota.sh" ]]; then
  bash "$BASE/tools/status_quota.sh"
fi

echo "[ACCEPT] pairs/limits OK"
