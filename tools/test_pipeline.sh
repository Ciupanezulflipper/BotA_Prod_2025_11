#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

ROOT="$HOME/BotA"
TOOLS="$ROOT/tools"
LOG="$ROOT/run.log"

assert_file () {
  local p="$1"
  if [ ! -f "$p" ]; then
    echo "[FAIL] missing file: $p" >&2
    exit 2
  fi
}

assert_exec () {
  local p="$1"
  if [ ! -x "$p" ]; then
    echo "[FAIL] not executable: $p" >&2
    exit 2
  fi
}

assert_exec "$TOOLS/run_pair.sh"
assert_file "$TOOLS/emit_snapshot.py"
assert_exec "/data/data/com.termux/files/usr/bin/bash"

SYM_LIST=("EURUSD" "GBPUSD")
PASS=0
FAIL=0

run_one () {
  local sym="$1"
  echo "---- pipeline: $sym ----"
  "$TOOLS/run_pair.sh" "$sym" >/dev/null

  # Verify latest snapshot block exists in run.log
  if ! grep -Eq "^=== ${sym} snapshot ===$" "$LOG"; then
    echo "[FAIL] no snapshot header found in run.log for $sym"
    ((FAIL++)) || true
    return
  fi
  # Grab last 12 relevant lines for this symbol and count TF lines
  local tfcount
  tfcount="$(grep -nE "^=== ${sym} snapshot ===$|^(H1|H4|D1): " "$LOG" | tail -n 12 | grep -Ec '^(H1|H4|D1): ' || true)"
  if [ "${tfcount:-0}" -lt 3 ]; then
    echo "[FAIL] run.log has fewer than 3 TF lines for $sym (got $tfcount)"
    ((FAIL++)) || true
  else
    echo "[OK] run.log contains header + 3 TF lines for $sym"
    ((PASS++)) || true
  fi
}

for s in "${SYM_LIST[@]}"; do
  run_one "$s"
done

echo "---- readers ----"
# data_fetch should find a block for EURUSD; treat "No snapshot block found" as a failure
if python3 "$TOOLS/data_fetch.py" "EURUSD" 2>/dev/null | grep -q "No snapshot block found"; then
  echo "[FAIL] data_fetch did not find EURUSD snapshot block"
  ((FAIL++)) || true
else
  echo "[OK] data_fetch found EURUSD snapshot block"
  ((PASS++)) || true
fi

# cache_dump and early_watch should execute without error (non-zero exit would break set -e)
python3 "$TOOLS/cache_dump.py" "EURUSD" "GBPUSD" >/dev/null || { echo "[FAIL] cache_dump error"; ((FAIL++)) || true; }
python3 "$TOOLS/early_watch.py" --ignore-session >/dev/null || { echo "[FAIL] early_watch error"; ((FAIL++)) || true; }

echo "---- summary ----"
echo "pass=$PASS fail=$FAIL"
if [ "$FAIL" -gt 0 ]; then
  exit 1
fi
exit 0
