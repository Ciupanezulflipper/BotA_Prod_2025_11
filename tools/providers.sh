#!/usr/bin/env bash
set -euo pipefail

# Paths (derived from this file location)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
CONFIG_DIR="${ROOT_DIR}/config"
LOG_DIR="${ROOT_DIR}/logs"
CACHE_DIR="${ROOT_DIR}/cache"

# Load config exports if present
set -a
[ -f "${CONFIG_DIR}/strategy.env" ] && . "${CONFIG_DIR}/strategy.env" || true
set +a

# Defaults if not set in strategy.env
: "${ENABLE_YAHOO:=true}"
: "${ENABLE_STOOQ:=true}"
: "${ENABLE_FINNHUB:=false}"
: "${FETCH_TIMEOUT_SEC:=12}"

is_true() {
  case "${1:-false}" in
    true|TRUE|1|yes|YES) return 0 ;;
    *) return 1 ;;
  esac
}

map_pair_yahoo() {
  # EURUSD -> EURUSD=X
  local p="${1^^}"
  echo "${p}=X"
}

map_pair_stooq() {
  # EURUSD -> eurusd
  local p="${1,,}"
  echo "${p}"
}

map_pair_finnhub() {
  # EURUSD -> OANDA:EUR_USD
  local p="${1^^}"
  local base="${p:0:3}"
  local quote="${p:3:3}"
  echo "OANDA:${base}_${quote}"
}

fetch_yahoo() {
  local pair="$1"
  local sym; sym="$(map_pair_yahoo "$pair")"
  local url="https://query1.finance.yahoo.com/v7/finance/quote?symbols=${sym}"
  local body
  body="$(curl -m "${FETCH_TIMEOUT_SEC}" -sL "$url" || true)"
  # Parse without jq
  local price timeu
  price="$(printf '%s' "$body" | grep -o '"regularMarketPrice":[0-9.]\+' | head -n1 | cut -d: -f2)"
  timeu="$(printf '%s' "$body" | grep -o '"regularMarketTime":[0-9]\+' | head -n1 | cut -d: -f2)"
  if [ -n "${price:-}" ] && [ -n "${timeu:-}" ] && awk "BEGIN{exit !($price>0)}"; then
    echo "price=${price} ts=${timeu} provider=yahoo"
    return 0
  fi
  return 1
}

fetch_stooq() {
  local pair="$1"
  local code; code="$(map_pair_stooq "$pair")"
  # Daily CSV (latest close); if intraday CSV not available, use now as timestamp
  local url="https://stooq.com/q/l/?s=${code}&f=sd2t2ohlcv&h&e=csv"
  local csv
  csv="$(curl -m "${FETCH_TIMEOUT_SEC}" -sL "$url" || true)"
  # Expect two lines (header + data). Close is field 7.
  local line
  line="$(printf '%s\n' "$csv" | sed -n '2p')"
  [ -n "${line:-}" ] || return 1
  # Symbol,Date,Time,Open,High,Low,Close,Volume
  local close; close="$(printf '%s' "$line" | awk -F',' '{print $7}')" || true
  if [ -n "${close:-}" ] && awk "BEGIN{exit !($close>0)}"; then
    local ts_now; ts_now="$(date -u +%s)"
    echo "price=${close} ts=${ts_now} provider=stooq"
    return 0
  fi
  return 1
}

fetch_finnhub() {
  local pair="$1"
  local token="${FINNHUB_TOKEN:-}"
  [ -n "$token" ] || return 1
  local sym; sym="$(map_pair_finnhub "$pair")"
  local url="https://finnhub.io/api/v1/quote?symbol=${sym}&token=${token}"
  local body
  body="$(curl -m "${FETCH_TIMEOUT_SEC}" -sL "$url" || true)"
  local price timeu
  price="$(printf '%s' "$body" | grep -o '"c":[0-9.]\+' | head -n1 | cut -d: -f2)"
  timeu="$(printf '%s' "$body" | grep -o '"t":[0-9]\+' | head -n1 | cut -d: -f2)"
  if [ -n "${price:-}" ] && [ -n "${timeu:-}" ] && awk "BEGIN{exit !($price>0)}"; then
    echo "price=${price} ts=${timeu} provider=finnhub"
    return 0
  fi
  return 1
}

get_price() {
  local pair="$1"
  local res=""
  if is_true "$ENABLE_YAHOO"; then
    if res="$(fetch_yahoo "$pair")"; then echo "$res"; return 0; fi
  fi
  if is_true "$ENABLE_STOOQ"; then
    if res="$(fetch_stooq "$pair")"; then echo "$res"; return 0; fi
  fi
  if is_true "$ENABLE_FINNHUB"; then
    if res="$(fetch_finnhub "$pair")"; then echo "$res"; return 0; fi
  fi
  return 1
}
