#!/data/data/com.termux/files/usr/bin/bash
# FILE: tools/data_fetch_candles.sh
# USAGE: tools/data_fetch_candles.sh EURUSD H1

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

set -a
[ -f config/strategy.env ] && source config/strategy.env || true
[ -f .env ] && source .env || true
set +a

PAIR="${1:-}"; TF="${2:-H1}"
[[ -z "$PAIR" ]] && { echo "ERROR: PAIR required" >&2; exit 1; }

mkdir -p cache
CACHE_JSON="cache/${PAIR}.json"
CACHE_TXT="cache/${PAIR}.txt"
PROV_TAG="cache/${PAIR}_provider.txt"
TIMEOUT=10
UA='Mozilla/5.0'

fetch_yahoo(){
  local symbol="${PAIR}=X"
  local url="https://query1.finance.yahoo.com/v8/finance/chart/${symbol}?interval=1h&range=2d"
  local resp price
  resp="$(curl -sSL --max-time "$TIMEOUT" -H "User-Agent: $UA" "$url" 2>/dev/null || true)"
  [[ -z "$resp" ]] && return 1
  echo "$resp" | jq -e '.chart.result[0].indicators.quote[0]' >/dev/null 2>&1 || return 1
  price="$(echo "$resp" | jq -r '.chart.result[0].meta.regularMarketPrice // 0')"
  [[ -z "$price" || "$price" == "0" || "$price" == "null" ]] && return 1
  echo "$resp" >"$CACHE_JSON"; echo "$price" >"$CACHE_TXT"; echo "yahoo" >"$PROV_TAG"; return 0
}

fetch_stooq(){
  local symbol="${PAIR,,}"
  local url="https://stooq.com/q/d/l/?s=${symbol}&i=h"
  local csv price
  csv="$(curl -sSL --max-time "$TIMEOUT" -H "User-Agent: $UA" "$url" 2>/dev/null || true)"
  [[ -z "$csv" ]] && return 1
  price="$(echo "$csv" | awk -F, 'END{print $6}')" ; [[ -z "$price" || "$price" == "0" ]] && return 1
  printf '{"pair":"%s","price":%s,"source":"stooq"}\n' "$PAIR" "$price" >"$CACHE_JSON"
  echo "$price" >"$CACHE_TXT"; echo "stooq" >"$PROV_TAG"; return 0
}

fetch_finnhub(){
  [[ -z "${FINNHUB_TOKEN:-}" ]] && return 1
  local symbol="OANDA:${PAIR}_USD"
  local url="https://finnhub.io/api/v1/quote?symbol=${symbol}&token=${FINNHUB_TOKEN}"
  local resp price
  resp="$(curl -sSL --max-time "$TIMEOUT" -H "User-Agent: $UA" "$url" 2>/dev/null || true)"
  [[ -z "$resp" ]] && return 1
  price="$(echo "$resp" | jq -r '.c // 0')" ; [[ -z "$price" || "$price" == "0" || "$price" == "null" ]] && return 1
  echo "$resp" >"$CACHE_JSON"; echo "$price" >"$CACHE_TXT"; echo "finnhub" >"$PROV_TAG"; return 0
}

echo "[SANITY] data_fetch_candles.sh: PAIR=$PAIR TF=$TF CACHE_JSON=$CACHE_JSON"

if fetch_yahoo;   then echo "[SUCCESS] $PAIR via yahoo price=$(cat "$CACHE_TXT")"; exit 0; fi
sleep 1
if fetch_stooq;   then echo "[SUCCESS] $PAIR via stooq price=$(cat "$CACHE_TXT")"; exit 0; fi
sleep 1
if fetch_finnhub; then echo "[SUCCESS] $PAIR via finnhub price=$(cat "$CACHE_TXT")"; exit 0; fi

echo "ERROR: providers exhausted for $PAIR" >&2
exit 3
