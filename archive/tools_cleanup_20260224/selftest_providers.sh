#!/usr/bin/env bash
set -Eeuo pipefail
umask 022

# BotA — Provider Self-Test
# Purpose:
#   • Verify env keys for all providers are visible (TwelveData, AlphaVantage, Finnhub, Yahoo toggle)
#   • Smoke-test each Python provider helper
#   • Call provider_mux.py with POSITIONAL args (EURUSD 15 150) to avoid CLI mismatch
#   • Emit a PASS/FAIL summary based on mux result
#
# Usage:
#   bash tools/selftest_providers.sh                # default: EURUSD, TF=15, LIMIT=150
#   bash tools/selftest_providers.sh GBPUSD 15 150  # custom
#
# Exit codes:
#   0 = mux PASS (rows >= MIN_BARS_REQUIRED & age <= MAX_DATA_AGE_MINUTES)
#   1 = mux error (exception, no JSON)
#   2 = mux FAIL (insufficient rows or too old)

ROOT="$HOME/BotA"
LOGS="$ROOT/logs"
mkdir -p "$LOGS"
chmod -R u+rwX "$LOGS" || true

SYMBOL="${1:-EURUSD}"
TF="${2:-15}"
LIMIT="${3:-150}"

# ---------------------------
# Env loading
# ---------------------------
# 1) Global runtime env (if you use it)
if [ -f "$HOME/.env.runtime" ]; then
  set -a
  . "$HOME/.env.runtime"
  set +a
fi

# 2) BotA local .env (canonical keys live here)
if [ -f "$ROOT/.env" ]; then
  set -a
  . "$ROOT/.env"
  set +a
fi

MIN_BARS_REQUIRED="${MIN_BARS_REQUIRED:-120}"
MAX_DATA_AGE_MINUTES="${MAX_DATA_AGE_MINUTES:-30}"

echo "=== Provider self-test: SYMBOL=$SYMBOL TF=$TF LIMIT=$LIMIT ==="
echo "Thresholds: rows>=$MIN_BARS_REQUIRED && age<=$MAX_DATA_AGE_MINUTES m"
echo

# Env summary (no secrets printed)
echo "ENV TWELVEDATA_API_KEY=${TWELVEDATA_API_KEY:+SET}"
echo "ENV TWELVE_DATA_API_KEY=${TWELVE_DATA_API_KEY:+SET}"
echo "ENV ALPHAVANTAGE_API_KEY=${ALPHAVANTAGE_API_KEY:+SET}"
echo "ENV ALPHA_VANTAGE_API_KEY=${ALPHA_VANTAGE_API_KEY:+SET}"
echo "ENV FINNHUB_API_KEY=${FINNHUB_API_KEY:+SET}"
echo "ENV YF_ENABLE=${YF_ENABLE:+SET}"
echo

YJ="$LOGS/yahoo_${SYMBOL}_${TF}.json"
AJ="$LOGS/alphav_${SYMBOL}_${TF}.json"
TJ="$LOGS/twelved_${SYMBOL}_${TF}.json"
MJ="$LOGS/mux_${SYMBOL}_${TF}.json"

rm -f "$YJ" "$YJ.err" "$AJ" "$AJ.err" "$TJ" "$TJ.err" "$MJ" "$MJ.err" 2>/dev/null || true

summ() {
  local prov="$1" file="$2"
  if [ -s "$file" ]; then
    local rows age last ok
    rows=$(jq -r '.rows // 0' "$file" 2>/dev/null || echo 0)
    age=$(jq -r '.age_min // 1e9' "$file" 2>/dev/null || echo 1e9)
    last=$(jq -r '.last_ts // .last // empty' "$file" 2>/dev/null || true)
    ok=$(jq -r '.ok // false' "$file" 2>/dev/null || echo false)
    printf "%14s | rows=%-5s | age_min=%-8s | last=%s | ok=%s\n" "$prov" "$rows" "$age" "$last" "$ok"
  else
    printf "%14s | %s\n" "$prov" "no output"
  fi
}

# ---------------------------
# Direct provider tests
# ---------------------------

# Yahoo (keyless, but may 429)
if python3 "$ROOT/tools/data_provider_yahoo.py" --symbol "$SYMBOL" --tf "$TF" --limit "$LIMIT" >"$YJ" 2>"$YJ.err"; then
  :
else
  echo "      yahoo | ERROR: $(tail -n1 "$YJ.err" 2>/dev/null || echo 'unknown')" >&2
fi

# Alpha Vantage (may complain about premium endpoint)
if python3 "$ROOT/tools/data_provider_alphavantage.py" --symbol "$SYMBOL" --tf "$TF" --limit "$LIMIT" >"$AJ" 2>"$AJ.err"; then
  :
else
  echo "alpha_vantage | ERROR: $(tail -n1 "$AJ.err" 2>/dev/null || echo 'unknown')" >&2
fi

# TwelveData
if python3 "$ROOT/tools/data_provider_twelvedata.py" --symbol "$SYMBOL" --tf "$TF" --limit "$LIMIT" >"$TJ" 2>"$TJ.err"; then
  :
else
  echo "   twelve_data | ERROR: $(tail -n1 "$TJ.err" 2>/dev/null || echo 'unknown')" >&2
fi

summ "yahoo"         "$YJ"
summ "alpha_vantage" "$AJ"
summ "twelve_data"   "$TJ"

echo
echo "--- provider_mux ---"

# ---------------------------
# Mux test (POSitional args)
# ---------------------------
# provider_mux.py expects: provider_mux.py SYMBOL TF [rows]
if python3 "$ROOT/tools/provider_mux.py" "$SYMBOL" "$TF" "$LIMIT" >"$MJ" 2>"$MJ.err"; then
  summ "mux" "$MJ"
  rows=$(jq -r '.rows // 0' "$MJ" 2>/dev/null || echo 0)
  age=$(jq -r '.age_min // 1e9' "$MJ" 2>/dev/null || echo 1e9)

  # Clamp negative age to zero for gate
  if awk -v r="$rows" -v m="$MIN_BARS_REQUIRED" 'BEGIN{exit !(r>=m)}' \
     && awk -v a="$age" -v t="$MAX_DATA_AGE_MINUTES" 'BEGIN{if(a<0)a=0; exit !(a<=t)}'
  then
    echo "mux_result: PASS (rows >= $MIN_BARS_REQUIRED and age <= $MAX_DATA_AGE_MINUTES)"
    exit 0
  else
    echo "mux_result: FAIL (rows=$rows, age_min=$age, need rows>=$MIN_BARS_REQUIRED & age<=$MAX_DATA_AGE_MINUTES)" >&2
    exit 2
  fi
else
  echo "mux_result: ERROR: $(tail -n1 "$MJ.err" 2>/dev/null || echo 'unknown')" >&2
  exit 1
fi
