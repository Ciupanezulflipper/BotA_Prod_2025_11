#!/bin/bash
set -euo pipefail
ROOT="${HOME}/BotA"
LOGDIR="$ROOT/logs"
CFGDIR="$ROOT/config"
ALERTS="$LOGDIR/alerts.csv"

echo "== sanity =="
python3 -V
[ -x "$ROOT/tools/signal_accuracy.py" ] || { echo "missing signal_accuracy.py"; exit 1; }
mkdir -p "$LOGDIR" "$CFGDIR"

echo "== sample alerts.csv (kept if already present) =="
if [ ! -s "$ALERTS" ]; then
  printf "ts_utc,pair,dir_h1,rsi_h1,m5,news,source\n" > "$ALERTS"
  # harmless placeholder using current UTC so it registers pending
  printf "%s,EURUSD,BUY,60,NA,no,manual\n" "$(date -u +'%Y-%m-%d %H:%M:%S')" >> "$ALERTS"
fi
cat "$ALERTS"

echo "== run one accuracy tick =="
bash "$ROOT/tools/run_accuracy_once.sh"

echo "== outputs =="
ls -l "$LOGDIR"/accuracy*.json "$LOGDIR"/accuracy*.csv 2>/dev/null || true
tail -n 20 "$LOGDIR/accuracy.csv" 2>/dev/null || true
