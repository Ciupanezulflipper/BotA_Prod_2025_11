#!/usr/bin/env bash
set -euo pipefail
ROOT="${BOTA_ROOT:-$HOME/BotA}"
LOG="${ROOT}/logs/ops_smoke_accuracy.log"
ALERTS="${ROOT}/logs/alerts.csv"
ACCUR="${ROOT}/logs/accuracy.csv"
CONF="${ROOT}/config/signal.env"
mkdir -p "${ROOT}/logs" "${ROOT}/tmp"

ts(){ date -u +'%Y-%m-%d %H:%M:%S UTC'; }

echo "===== BotA Accuracy Smoke @ $(ts) =====" | tee "$LOG"

# 1) Files present
[[ -f "$ROOT/tools/signal_accuracy.py" && -f "$ROOT/tools/run_accuracy_once.sh" ]] || { echo "[FAIL] missing core files"; exit 1; }
chmod +x "$ROOT/tools/signal_accuracy.py" "$ROOT/tools/run_accuracy_once.sh" 2>/dev/null || true
echo "[PASS] Files present & executable" | tee -a "$LOG"

# 2) Truth sources
ENABLE_YAHOO="$(grep -E '^ENABLE_YAHOO=' "$CONF" 2>/dev/null | cut -d= -f2 || echo true)"
ENABLE_FINNHUB="$(grep -E '^ENABLE_FINNHUB=' "$CONF" 2>/dev/null | cut -d= -f2 || echo false)"
echo "[INFO] Truth sources -> Yahoo:${ENABLE_YAHOO} Finnhub:${ENABLE_FINNHUB}" | tee -a "$LOG"

# 3) CSV surfaces
[[ -f "$ALERTS" ]] || echo "ts_utc,pair,dir_h1,rsi_h1,m5,news,source,entry_price" > "$ALERTS"
python3 "$ROOT/tools/signal_accuracy.py" >/dev/null 2>&1 || true
[[ -f "$ACCUR"  ]] || { echo "[FAIL] could not initialize accuracy.csv"; exit 1; }
echo "[PASS] CSV surfaces ready" | tee -a "$LOG"

# 4) Synthetic alert 31m ago (so 30m window elapsed)
if date -u -d '31 minutes ago' +'%Y-%m-%d %H:%M:%S UTC' >/dev/null 2>&1; then
  AT="$(date -u -d '31 minutes ago' +'%Y-%m-%d %H:%M:%S UTC')"
else
  AT="$(date -u -v-31M +'%Y-%m-%d %H:%M:%S UTC')"
fi
PAIR="EURUSD"; DIR="BUY"; ENTRY="${ENTRY_OVERRIDE:-1.16500}"
echo "$AT,$PAIR,$DIR,55,,pos,smoke,$ENTRY" >> "$ALERTS"
echo "[PASS] Synthetic alert appended ($PAIR $DIR @ $ENTRY, ts=$AT)" | tee -a "$LOG"

# 5) Tick once
bash "$ROOT/tools/run_accuracy_once.sh" >/dev/null 2>&1 || true

# 6) Show matched rows or guidance
MATCH="$(grep -F "$AT" "$ACCUR" || true)"
if [ -n "$MATCH" ]; then
  echo "----- matched accuracy rows -----" | tee -a "$LOG"
  echo "$MATCH" | tee -a "$LOG"
  echo "---------------------------------" | tee -a "$LOG"
else
  echo "[WARN] No match yet. If you see PENDING:STALE on next run:" | tee -a "$LOG"
  echo "      • Ensure internet is available in Termux (try: curl https://query1.finance.yahoo.com )" | tee -a "$LOG"
  echo "      • Or reduce strictness: set MAX_LOCAL_AGE_SEC=1200 in config/signal.env" | tee -a "$LOG"
  echo "      • Or enable Finnhub by setting ENABLE_FINNHUB=true and FINNHUB_TOKEN=..." | tee -a "$LOG"
fi

echo "===== SMOKE COMPLETE @ $(ts) =====" | tee -a "$LOG"
