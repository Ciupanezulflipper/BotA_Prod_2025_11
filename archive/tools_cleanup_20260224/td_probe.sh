#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

SYMBOL="${1:-EURUSD}"
BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)"
STATE_DIR="$BASE/state"
TMP_DIR="${TMPDIR:-$HOME/tmp}"
mkdir -p "$STATE_DIR" "$TMP_DIR"

# load env (expects TWELVEDATA_API_KEY set in $BASE/.env)
set -a; . "$BASE/.env"; set +a
: "${TWELVEDATA_API_KEY:?TWELVEDATA_API_KEY missing in $BASE/.env}"

# map "EURUSD" -> "EUR/USD" for TwelveData
td_symbol="${SYMBOL:0:3}/${SYMBOL:3:3}"

resp="$TMP_DIR/td_${SYMBOL}_last.json"
curl -s "https://api.twelvedata.com/time_series?symbol=${td_symbol}&interval=15min&outputsize=1&apikey=${TWELVEDATA_API_KEY}" >"$resp"

status=$(jq -r '.status // empty' "$resp" 2>/dev/null || true)
if [[ "$status" != "ok" ]]; then
  msg="$(jq -r '.message // empty' "$resp" 2>/dev/null || true)"
  echo "[td_probe] error status=${status:-unknown} msg=${msg:-none}" >&2
  exit 1
fi

dt="$(jq -r '.values[0].datetime' "$resp")"
close="$(jq -r '.values[0].close' "$resp")"
echo "[td] ${SYMBOL} 15min ${dt} ${close}"

# --- local quota bookkeeping ---
now_utc="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "${now_utc} ${SYMBOL}" >> "$STATE_DIR/td_hits.log"
day_tag="$(date -u +%Y%m%d)"
echo "${now_utc} ${SYMBOL}" >> "$STATE_DIR/td_hits.${day_tag}.log"
