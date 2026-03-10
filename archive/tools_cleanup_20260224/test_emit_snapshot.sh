#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

ROOT="$HOME/BotA"
TOOLS="$ROOT/tools"
PY="$TOOLS/emit_snapshot.py"

if [ ! -x "$PY" ]; then
  echo "[FAIL] emit_snapshot.py not found or not executable at: $PY" >&2
  exit 2
fi

SYM_LIST=("EURUSD" "GBPUSD")
PASS=0
FAIL=0

run_one () {
  local sym="$1"
  echo "---- smoke: $sym ----"
  local tmp
  tmp="$(mktemp)"
  if ! python3 "$PY" "$sym" | tee "$tmp" >/dev/null; then
    echo "[FAIL] emit_snapshot.py exited non-zero for $sym"
    ((FAIL++)) || true
    rm -f "$tmp"
    return
  fi
  local header_re="^=== ${sym} snapshot ===$"
  if ! grep -Eq "$header_re" "$tmp"; then
    echo "[FAIL] missing header for $sym"
    ((FAIL++)) || true
    rm -f "$tmp"
    return
  fi
  # Count TF lines (accept provider_error as valid line; the goal here is "no crash + 3 TF lines")
  local tfcount
  tfcount="$(grep -Ec '^(H1|H4|D1): ' "$tmp" || true)"
  if [ "${tfcount:-0}" -lt 3 ]; then
    echo "[FAIL] expected 3 TF lines (H1/H4/D1) for $sym; got $tfcount"
    ((FAIL++)) || true
  else
    echo "[OK] header + 3 TF lines present for $sym"
    ((PASS++)) || true
  fi
  rm -f "$tmp"
}

for s in "${SYM_LIST[@]}"; do
  run_one "$s"
done

echo "---- summary ----"
echo "pass=$PASS fail=$FAIL"
if [ "$FAIL" -gt 0 ]; then
  exit 1
fi
exit 0
