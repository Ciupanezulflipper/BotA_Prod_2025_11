#!/data/data/com.termux/files/usr/bin/bash
# ======================================================================
# BotA - X.py Regression Test Suite
# Author: Tomai Assistant
# Purpose:
#   Run a fixed set of deterministic tests against X.py to ensure that:
#     - fail-closed behavior still works
#     - market_closed logic works
#     - valid BUY signal produces correct output
#     - output remains EXACTLY one JSON line
# ======================================================================

set -euo pipefail

ENGINE="X.py"

if [[ ! -f "$ENGINE" ]]; then
  echo "[ERROR] $ENGINE not found in current directory."
  exit 1
fi

echo "--------------------------------------------------"
echo "[TEST 1] Empty stdin → fail-closed"
echo "--------------------------------------------------"
echo "" | python3 "$ENGINE"

echo ""
echo "--------------------------------------------------"
echo "[TEST 2] Market closed + empty indicators"
echo "--------------------------------------------------"
echo '{"symbol":"EURUSD","tf":"M15","provider":"mux","age_min":1,"market_open":false,"indicators":{}}' \
  | python3 "$ENGINE"

echo ""
echo "--------------------------------------------------"
echo "[TEST 3] Strong BUY example"
echo "--------------------------------------------------"
echo '{"symbol":"EURUSD","tf":"M15","provider":"mux","age_min":1,
"market_open":true,"score":50,
"indicators":{
"price":1.0850,
"ema_fast":1.0854,"ema_slow":1.0849,
"ema_fast_slope":0.0003,"ema_slow_slope":0.0002,
"rsi":30,
"adx":25,"di_plus":30,"di_minus":10,
"macd":0.002,"macd_signal":0.001,
"macd_histogram":0.001,"macd_histogram_prev":0.0005,"macd_cross_age":1,
"fib_retracement":0.5,"atr_percentile":50,
"open":1.0848,"high":1.0855,"low":1.0845,"close":1.0854
}}' | python3 "$ENGINE"

echo ""
echo "--------------------------------------------------"
echo "[DONE] All tests executed."
echo "If output matches: FLAT / FLAT / BUY with score=72 → PASS"
echo "--------------------------------------------------"
