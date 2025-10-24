#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
LOG="$HOME/BotA/run.log"

check_pair () {
  local sym="$1"
  local block
  block="$(grep -nE "^=== ${sym} snapshot ===$|^(H1|H4|D1): " "$LOG" | tail -n 12)"
  echo "---- ${sym} ----"
  echo "$block"
  if ! echo "$block" | grep -q "^.*=== ${sym} snapshot ===$"; then
    echo "[FAIL] ${sym}: header missing"; return 1
  fi
  local tfc
  tfc="$(echo "$block" | grep -Ec '^(H1|H4|D1): ')"
  if [ "${tfc:-0}" -lt 3 ]; then
    echo "[FAIL] ${sym}: expected 3 TF lines, got $tfc"; return 1
  fi
  if echo "$block" | grep -q 'provider_error='; then
    echo "[FAIL] ${sym}: provider_error present"; return 1
  fi
  echo "[OK] ${sym}: header + 3 numeric TF lines"
}

ok=0; fail=0
for s in EURUSD GBPUSD; do
  if check_pair "$s"; then ok=$((ok+1)); else fail=$((fail+1)); fi
done

echo "summary: pass=$ok fail=$fail"
[ "$fail" -eq 0 ] && exit 0 || exit 1
