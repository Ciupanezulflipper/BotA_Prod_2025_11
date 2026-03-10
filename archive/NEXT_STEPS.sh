#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$HOME/BotA"
ENV="$ROOT/.env"
LOGS="$ROOT/logs"
STATE="$ROOT/state"

echo "[1/5] Load .env"
set -a
. "$ENV"
set +a

echo "[2/5] Ensure provider order prefers TwelveData"
# Insert or update PROVIDER_ORDER in .env (idempotent, plain ASCII)
if grep -q '^PROVIDER_ORDER=' "$ENV"; then
  sed -i 's/^PROVIDER_ORDER=.*/PROVIDER_ORDER=twelve_data,yahoo,alpha_vantage/' "$ENV"
else
  printf '\nPROVIDER_ORDER=twelve_data,yahoo,alpha_vantage\n' >> "$ENV"
fi
echo "PROVIDER_ORDER now set to: $(grep '^PROVIDER_ORDER=' "$ENV" | cut -d= -f2-)"

echo "[3/5] Prove TwelveData returns data (no secrets printed)"
if [ -z "${TWELVEDATA_API_KEY:-}" ]; then
  echo "[FAIL] TWELVEDATA_API_KEY missing in .env"; exit 1
fi
TD_URL="https://api.twelvedata.com/time_series?symbol=EURUSD&interval=15min&outputsize=5&apikey=${TWELVEDATA_API_KEY}"
# Fetch last 5 candles; print only top lines to avoid noise
curl -s "$TD_URL" | head -n 5

echo "[4/5] Restart loop cleanly with env order applied"
crontab -l 2>/dev/null | grep -v 'BotA/tools/watchdog.sh' | crontab - || true
pkill -f "BotA/tools/run_loop\.sh" 2>/dev/null || true
rm -f "$STATE/loop.lock" "$STATE/loop.pid"
: > "$LOGS/loop.log"

env DRY_RUN_MODE=false \
    PAIRS="EURUSD" \
    "$(grep '^PROVIDER_ORDER=' "$ENV" | cut -d= -f1)"="$(grep '^PROVIDER_ORDER=' "$ENV" | cut -d= -f2-)" \
    bash "$ROOT/tools/loop_guard.sh" daemon

sleep 3
echo "[5/5] Show quick proofs"
echo "- process:"
ps -ef | awk '/BotA\/tools\/run_loop\.sh/ && !/awk/ && !/grep/ {print $0}'
echo "- loop.log tail:"
tail -n 12 "$LOGS/loop.log"
