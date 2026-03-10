#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

LOG="$HOME/BotA/logs/loop.log"
: > "$LOG" || true

PAIR1="${1:-EURUSD}"

echo "== 1) Pause then tick (expect [skip]) =="
bash "$HOME/BotA/tools/bot_state.sh" pause >/dev/null
out1="$("$HOME/BotA/tools/run_signal_routed.sh" "$PAIR1" 2>&1 | tee /dev/stderr)"
echo "$out1" | grep -q "^\[skip\] " && echo "[OK] skip observed" || { echo "[FAIL] skip not observed"; exit 1; }

echo "== 2) Resume then tick (expect [run]) =="
bash "$HOME/BotA/tools/bot_state.sh" resume >/dev/null
out2="$("$HOME/BotA/tools/run_signal_routed.sh" "$PAIR1" 2>&1 | tee /dev/stderr)"
echo "$out2" | grep -q "^\[run\] " && echo "[OK] run observed" || { echo "[FAIL] run not observed"; exit 1; }

echo "== 3) Summary =="
echo "[ACCEPT] ON/OFF switch smoke test passed."
