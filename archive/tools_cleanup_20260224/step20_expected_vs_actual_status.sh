#!/usr/bin/env bash
set -euo pipefail

echo "STATUS: ok"
echo "SCOPE: Analysis only (NO code edits)."
echo "GOAL: Expected timestamps (indicators mtimes) vs ACTUAL tools/status_pretty.py output."
echo

python3 - <<'PY'
import pathlib, time
from datetime import datetime, timezone

pairs = ["EURUSD","GBPUSD","USDJPY"]
tfs   = ["H1","M15"]

def fmt_utc(ts:int)->str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

now = int(time.time())
print("now_utc:", fmt_utc(now), "| epoch", now)
print()

print("===== EXPECTED (real) timestamps based on indicators file mtimes =====")
for pair in pairs:
    print("\nPAIR:", pair)
    for tf in tfs:
        p = pathlib.Path(f"cache/indicators_{pair}_{tf}.json")
        if not p.exists():
            print(f"  [{tf}] MISSING:", p)
            continue
        mtime = int(p.stat().st_mtime)
        age = now - mtime
        print(f"  [{tf}] indicators_mtime_utc={fmt_utc(mtime)} age_sec={age}")
print()

print("===== ACTUAL tools/status_pretty.py output (advanced) =====")
print("(If this prints 2025-10-28 or other static/demo timestamps, it is still running demo mode.)")
PY

echo
echo "----- RUN: python3 tools/status_pretty.py advanced -----"
python3 tools/status_pretty.py advanced 2>&1 | sed -n '1,120p'

echo
echo "===== STEP 20 Acceptance criteria ====="
echo "A) EXPECTED timestamps are near-now (minutes old), because indicators_* mtimes are fresh."
echo "B) ACTUAL status_pretty output is demo/incorrect if it shows 2025-10-28 (or any static snapshots)."
echo "C) This proves: status_pretty replacement should use indicators_* mtimes for timestamp/freshness (NOT Yahoo *_H1.json)."
echo
echo "Paste this entire output back here."
