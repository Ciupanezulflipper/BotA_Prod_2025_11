#!/data/data/com.termux/files/usr/bin/bash
# Bot A — Phase 3: Verify cache contains H1/H4/D1 for each pair
set -euo pipefail

TOOLS="$HOME/BotA/tools"
DUMP="$TOOLS/cache_dump.py"

if [ ! -f "$DUMP" ]; then
  echo "[FAIL] missing $DUMP" >&2
  exit 2
fi

PAIRS=("$@")
if [ "${#PAIRS[@]}" -eq 0 ]; then
  PAIRS=("EURUSD" "GBPUSD")
fi

ok=0; fail=0

check_pair () {
  local sym="$1"
  local out
  out="$(python3 "$DUMP" "$sym" 2>/dev/null || true)"
  # Expect lines like:
  # == EURUSD ==
  #   H1: ...
  #   H4: ...
  #   D1: ...
  local h1 h4 d1
  h1="$(printf "%s\n" "$out" | grep -E '^\s*H1:\s*' || true)"
  h4="$(printf "%s\n" "$out" | grep -E '^\s*H4:\s*' || true)"
  d1="$(printf "%s\n" "$out" | grep -E '^\s*D1:\s*' || true)"
  if printf "%s" "$h1" | grep -q "(missing)"; then h1=""; fi
  if printf "%s" "$h4" | grep -q "(missing)"; then h4=""; fi
  if printf "%s" "$d1" | grep -q "(missing)"; then d1=""; fi
  if [ -n "$h1" ] && [ -n "$h4" ] && [ -n "$d1" ]; then
    echo "[OK] $sym: cache has H1/H4/D1"
    return 0
  else
    echo "[FAIL] $sym: cache incomplete"
    printf "%s\n" "$out"
    return 1
  fi
}

for s in "${PAIRS[@]}"; do
  if check_pair "$s"; then ok=$((ok+1)); else fail=$((fail+1)); fi
done

echo "summary: pass=$ok fail=$fail"
[ "$fail" -eq 0 ] && exit 0 || exit 1
