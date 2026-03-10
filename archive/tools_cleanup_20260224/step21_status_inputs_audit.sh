#!/usr/bin/env bash
set -euo pipefail

echo "STATUS: ok"
echo "SCOPE: Analysis only (NO edits to existing files)."
echo "GOAL: Audit inputs + call sites for replacing tools/status_pretty.py with real-data output."
echo

echo "===== 21A) Call sites (who runs status_pretty.py and with what args) ====="
grep -RIn --line-number "status_pretty\.py" . 2>/dev/null | head -n 200 || true
echo

echo "===== 21B) Current tools/status_pretty.py (read-only peek: header + __main__) ====="
if [[ -f tools/status_pretty.py ]]; then
  echo "--- FILE STAT ---"
  ls -la tools/status_pretty.py || true
  echo
  echo "--- HEAD (first 160 lines) ---"
  sed -n '1,160p' tools/status_pretty.py || true
  echo
  echo "--- TAIL (last 220 lines) ---"
  tail -n 220 tools/status_pretty.py || true
else
  echo "MISSING: tools/status_pretty.py"
fi
echo

echo "===== 21C) Indicators cache schema + mtimes (this is what scoring_engine actually uses) ====="
python3 - <<'PY'
import json, pathlib, time
from datetime import datetime, timezone

pairs = ["EURUSD","GBPUSD","USDJPY"]
tfs   = ["H1","M15"]

def fmt_utc(ts:int)->str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

def load(p: pathlib.Path):
    try:
        return json.loads(p.read_text("utf-8", errors="ignore"))
    except Exception:
        return None

def show_candidates(d: dict):
    # Common field name guesses across our codebase
    want = [
        "pair","symbol","tf","timeframe",
        "price","close","last","last_price",
        "rsi","rsi14","RSI",
        "ema9","ema21","ema_9","ema_21",
        "ema_fast","ema_slow",
        "adx","atr","atr_pips","atr_points",
        "trend","trend_dir","direction","vote","score",
        "provider","source","data_provider","meta",
    ]
    present = []
    for k in want:
        if k in d:
            present.append((k, d.get(k)))
    # Also include any keys that look indicator-ish
    extra = []
    for k,v in d.items():
        kl = str(k).lower()
        if any(s in kl for s in ["rsi","ema","adx","atr","trend","vote","score","provider"]):
            if k not in dict(present):
                extra.append((k,v))
    return present, extra

now = int(time.time())
print("now_utc:", fmt_utc(now), "| epoch", now)
print()

for pair in pairs:
    print("========================================================")
    print("PAIR:", pair)
    for tf in tfs:
        p = pathlib.Path(f"cache/indicators_{pair}_{tf}.json")
        if not p.exists():
            print(f"[{tf}] MISSING:", p)
            continue
        st = p.stat()
        mtime = int(st.st_mtime)
        age = now - mtime
        size = st.st_size
        j = load(p)
        print(f"[{tf}] file={p} size={size}B mtime={fmt_utc(mtime)} age_sec={age}")
        if not isinstance(j, dict):
            print(f"[{tf}] JSON_LOAD_FAIL_OR_NOT_DICT")
            continue
        keys = list(j.keys())
        print(f"[{tf}] top_level_keys({len(keys)}):", ", ".join(keys[:40]) + (" ..." if len(keys) > 40 else ""))
        present, extra = show_candidates(j)
        print(f"[{tf}] present_candidate_fields={len(present)} (show up to 16)")
        for k,v in present[:16]:
            vv = v
            if isinstance(vv, (dict, list)):
                vv = f"<{type(vv).__name__}>"
            print("  -", k, "=", vv)
        print(f"[{tf}] extra_indicatorish_fields={len(extra)} (show up to 16)")
        for k,v in extra[:16]:
            vv = v
            if isinstance(vv, (dict, list)):
                vv = f"<{type(vv).__name__}>"
            print("  -", k, "=", vv)
    print()

print("========================================================")
print("STEP 21 Acceptance criteria")
print("A) We see exactly how status_pretty is invoked (args + scripts).")
print("B) We see the current status_pretty __main__ demo runner and CLI shape (read-only).")
print("C) We see what fields exist inside indicators_* JSON to print RSI/EMA/ADX/ATR and provider.")
PY
echo
echo "Paste this entire output back here."
