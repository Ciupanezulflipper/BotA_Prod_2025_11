#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG="$BASE/logs/loop.log"
: > "$LOG" || true
PAIR1="${PAIR1:-EURUSD}"
PAIR2="${PAIR2:-GBPUSD}"
echo "== 1) HARD STOP =="
bash "$BASE/tools/hard_stop.sh"
sleep 1
if pgrep -f 'BotA/tools/run_loop\.sh' >/dev/null 2>&1; then
  echo "[FAIL] run_loop still present after hard_stop"; exit 1
else
  echo "[OK] run_loop gone"
fi
echo "== 2) HARD START =="
DRY_RUN_MODE=false PROVIDER_ORDER="twelve_data" PAIRS="$PAIR1,$PAIR2" TF15_SLEEP_PAD=120 \
  bash "$BASE/tools/hard_start.sh"
if ! pgrep -f 'BotA/tools/run_loop\.sh' >/dev/null 2>&1; then
  echo "[FAIL] run_loop not observed after hard_start"; exit 2
else
  echo "[OK] run_loop observed"
fi
echo "== 3) FORCE one tick per pair (proof; consumes 2 credits) =="
out1="$(DRY_RUN_MODE=false PROVIDER_ORDER="twelve_data" "$BASE/tools/run_signal_once.py" "$PAIR1" 2>&1 | tee /dev/stderr)"
echo "$out1" | grep -q "^\[run\] $PAIR1 " && echo "[OK] $PAIR1 run" || { echo "[FAIL] $PAIR1 run not seen"; exit 3; }
out2="$(DRY_RUN_MODE=false PROVIDER_ORDER="twelve_data" "$BASE/tools/run_signal_once.py" "$PAIR2" 2>&1 | tee /dev/stderr)"
echo "$out2" | grep -q "^\[run\] $PAIR2 " && echo "[OK] $PAIR2 run" || { echo "[FAIL] $PAIR2 run not seen"; exit 4; }
echo "== 4) Summary =="
echo "[ACCEPT] HARD stop/start smoke test passed."
