#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "== 1) Hard stop =="
bash "$BASE/tools/hard_stop.sh"

echo "== 2) Verify stopped =="
if pgrep -f 'BotA/tools/run_loop\.sh' >/dev/null 2>&1; then
  echo "[FAIL] scheduler still running"; exit 1
fi
echo "[OK] no scheduler"

echo "== 3) Hard start (.env defaults) =="
bash "$BASE/tools/hard_start.sh"

echo "== 4) Verify running =="
pid="$(pgrep -f 'BotA/tools/run_loop\.sh' || true)"
[[ -n "$pid" ]] || { echo "[FAIL] scheduler not started"; exit 2; }
echo "[OK] scheduler PID=$pid"

echo "== 5) Proof tick (consumes 2 TD credits) =="
out1="$(DRY_RUN_MODE=false "$BASE/tools/run_signal_once.py" EURUSD 2>&1)"
echo "$out1" | grep -q '^\[run\] EURUSD ' && echo "[OK] EURUSD run" || { echo "[FAIL] EURUSD run not seen"; exit 3; }
out2="$(DRY_RUN_MODE=false "$BASE/tools/run_signal_once.py" GBPUSD 2>&1)"
echo "$out2" | grep -q '^\[run\] GBPUSD ' && echo "[OK] GBPUSD run" || { echo "[FAIL] GBPUSD run not seen"; exit 4; }

echo "== 6) Commands menu refresh =="
bash "$BASE/tools/set_bot_commands.sh" >/dev/null && echo "[OK] Telegram menu updated"

echo "[ACCEPT] HARD-ONLY control installed and working."
