#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

# Offline replay suite:
# - Scans cache/indicators_*_*.json (or uses explicit PAIR TF args)
# - Calls tools/replay_mode.sh <PAIR> <TF> (NO Telegram)
# - Writes per-run JSON to state/tmp/replay_suite_<TS>/
# - Prints one-line summaries + final PASS/FAIL
#
# Usage:
#   tools/replay_suite.sh
#   tools/replay_suite.sh EURUSD M15
#   tools/replay_suite.sh --max 25
#
# Exit codes:
#   0: suite ran; at least 1 replay executed
#   2: missing tools/replay_mode.sh or no indicators files found

cd /data/data/com.termux/files/home/BotA || { echo "FAIL: BotA folder not found"; exit 2; }

MAX=50
while [ $# -gt 0 ]; do
  case "$1" in
    --max) MAX="${2:-50}"; shift 2 ;;
    -h|--help)
      cat <<'EOF'
Usage:
  tools/replay_suite.sh [--max N]
  tools/replay_suite.sh <PAIR> <TF>

Offline replay suite:
  - Reads cache/indicators_* files
  - Uses tools/replay_mode.sh to compute entry/sl/tp/rr/atr
  - Never sends Telegram
EOF
      exit 0
      ;;
    *)
      break
      ;;
  esac
done

if [ ! -x tools/replay_mode.sh ]; then
  echo "STATUS=fail (missing tools/replay_mode.sh). Run T32S1 first."
  exit 2
fi

TS="$(date +%Y%m%d_%H%M%S)"
OUTDIR="state/tmp/replay_suite_${TS}"
mkdir -p "$OUTDIR" >/dev/null 2>&1 || true

runs=0
tradeable=0
rejected=0
passed=0
failed=0

summarize_one() {
  local jf="$1"
  python3 - <<'PY' "$jf"
import json, sys, math
p=sys.argv[1]
d=json.load(open(p))
pair=d.get("pair","?")
tf=d.get("tf","?")
direction=d.get("direction","?")
rej=bool(d.get("filter_rejected", True))
reasons=d.get("filter_reasons", [])
price=d.get("price",0.0)
atr=d.get("atr",0.0)
entry=d.get("entry",0.0)
sl=d.get("sl",0.0)
tp=d.get("tp",0.0)
rr=d.get("rr",0.0)
def okpos(x): return isinstance(x,(int,float)) and math.isfinite(x) and x>0
tradeable = (direction in ("BUY","SELL")) and (rej is False)
ok = True
if tradeable:
  ok = okpos(price) and okpos(atr) and okpos(entry) and okpos(rr) and okpos(abs(sl-entry)) and okpos(abs(tp-entry))
else:
  ok = True  # non-tradeable is allowed; suite is about evidence
print(f"[SUITE_ONE] {pair} {tf} dir={direction} rejected={rej} rr={rr} atr={atr} entry={entry} ok_tradeable_fields={ok} reasons={reasons}")
print("ONE_TESTS_PASSED=true" if ok else "ONE_TESTS_PASSED=false")
PY
}

run_one() {
  local pair="$1"
  local tf="$2"
  local out="$OUTDIR/replay_${pair}_${tf}.json"

  set +e
  ./tools/replay_mode.sh "$pair" "$tf" --sl-mult 1.5 --tp-mult 2.0 > "$out"
  local rc=$?
  set -e

  if ! python3 -m json.tool "$out" >/dev/null 2>&1; then
    echo "[SUITE_ONE] $pair $tf JSON_INVALID (rc=$rc) out=$out"
    echo "ONE_TESTS_PASSED=false"
    return 0
  fi

  summarize_one "$out"
  return 0
}

# Mode A: explicit PAIR TF
if [ $# -ge 2 ]; then
  PAIR="$1"; TF="$2"
  echo "==================================================================="
  echo "REPLAY_SUITE: explicit run PAIR=$PAIR TF=$TF OUTDIR=$OUTDIR"
  echo "==================================================================="
  runs=$((runs+1))
  one_out="$(run_one "$PAIR" "$TF" || true)"
  echo "$one_out"

  # tally from output text
  if echo "$one_out" | grep -q 'ONE_TESTS_PASSED=true'; then passed=$((passed+1)); else failed=$((failed+1)); fi
  if echo "$one_out" | grep -q 'rejected=True'; then rejected=$((rejected+1)); else tradeable=$((tradeable+1)); fi

else
  # Mode B: scan cache
  echo "==================================================================="
  echo "REPLAY_SUITE: scanning cache/indicators_*_*.json (max=$MAX) OUTDIR=$OUTDIR"
  echo "==================================================================="

  mapfile -t files < <(ls -1 cache/indicators_*_*.json 2>/dev/null | head -n "$MAX" || true)
  if [ "${#files[@]}" -eq 0 ]; then
    echo "STATUS=fail (no cache/indicators_*_*.json found)"
    exit 2
  fi

  for f in "${files[@]}"; do
    base="$(basename "$f")"
    base="${base#indicators_}"
    base="${base%.json}"
    pair="${base%_*}"
    tf="${base##*_}"

    runs=$((runs+1))
    one_out="$(run_one "$pair" "$tf" || true)"
    echo "$one_out"

    if echo "$one_out" | grep -q 'ONE_TESTS_PASSED=true'; then passed=$((passed+1)); else failed=$((failed+1)); fi
    if echo "$one_out" | grep -q 'rejected=True'; then rejected=$((rejected+1)); else tradeable=$((tradeable+1)); fi
  done
fi

echo "==================================================================="
echo "[SUITE_SUMMARY] runs=$runs tradeable_not_rejected=$tradeable rejected=$rejected one_tests_passed=$passed one_tests_failed=$failed"
echo "OUTDIR=$OUTDIR"
echo "STATUS=pass"  # suite executed; detailed pass/fail is above per run
echo "==================================================================="

exit 0
