#!/usr/bin/env bash
set -euo pipefail

echo "STATUS: ok"
echo "SCOPE: Analysis only (NO edits to existing files)."
echo "GOAL: Locate grounded rules for vote/signal/health so the status_pretty replacement can be implemented without guessing."
echo

echo "===== 23A) What calls / depends on status_pretty output format ====="
echo "--- tools/pretty_bridge.py markers / cut logic ---"
sed -n '1,140p' tools/pretty_bridge.py 2>/dev/null || true
echo
echo "--- tools/signal_watcher.sh parsing logic (H1) ---"
sed -n '1,160p' tools/signal_watcher.sh 2>/dev/null || true
echo
echo "--- tools/probe_signals.py parsing logic ---"
sed -n '1,220p' tools/probe_signals.py 2>/dev/null || true
echo
echo "--- tg_bot.py /status command plumbing ---"
sed -n '1,220p' tg_bot.py 2>/dev/null || true
echo

echo "===== 23B) Locate the source of VOTE / SCORE / SIGNAL rules in repo ====="
echo "(We must NOT invent vote rules. This step tries to find the canonical implementation.)"
echo
echo "--- grep: vote/score/signal/strong rules (top hits) ---"
grep -RIn --line-number -E '\bvote\b|\bscore\b|strong_signal|signal\s*=|signal:|BUY|SELL|NEUTRAL|ema9|ema21|rsi14|tf_ok|tf_actual_min|age_min|weak\b|cache_ok' . 2>/dev/null \
  | head -n 260 || true
echo

echo "===== 23C) If scoring_engine exists, show the exact logic (read-only) ====="
if [[ -f scoring_engine.sh ]]; then
  echo "--- FILE: scoring_engine.sh (first 260 lines) ---"
  sed -n '1,260p' scoring_engine.sh || true
  echo
  echo "--- FILE: scoring_engine.sh (lines containing vote/score/buy/sell/neutral/rsi/ema) ---"
  grep -nE '\bvote\b|\bscore\b|BUY|SELL|NEUTRAL|rsi|ema' scoring_engine.sh | sed -n '1,220p' || true
  echo
else
  echo "MISSING: ./scoring_engine.sh"
fi
echo

if [[ -f tools/scoring_engine.sh ]]; then
  echo "--- FILE: tools/scoring_engine.sh (first 260 lines) ---"
  sed -n '1,260p' tools/scoring_engine.sh || true
  echo
  echo "--- FILE: tools/scoring_engine.sh (lines containing vote/score/buy/sell/neutral/rsi/ema) ---"
  grep -nE '\bvote\b|\bscore\b|BUY|SELL|NEUTRAL|rsi|ema' tools/scoring_engine.sh | sed -n '1,220p' || true
  echo
fi

echo "===== 23D) Inspect indicators_* schema values that can drive health/cache labels ====="
python3 - <<'PY'
import json, pathlib, time
from datetime import datetime, timezone

def fmt_utc(ts:int)->str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

def load(p: pathlib.Path):
    try:
        return json.loads(p.read_text("utf-8", errors="ignore"))
    except Exception:
        return None

root = pathlib.Path("cache")
files = sorted(root.glob("indicators_*.json"))
now = int(time.time())
print("now_utc:", fmt_utc(now), "| epoch", now)
print()

if not files:
    print("NO FILES: cache/indicators_*.json not found")
    raise SystemExit(0)

# Print a compact table of the fields we can legally use without guessing.
fields = ["pair","timeframe","price","age_min","tf_ok","tf_actual_min","weak","error","rsi","ema9","ema21","adx","atr_pips","macd_hist"]
print("Fields we will probe per file:")
print(" - " + ", ".join(fields))
print()

def safe(v):
    if v is None: return "None"
    if isinstance(v, float): return f"{v:.6g}"
    return str(v)

for f in files:
    st = f.stat()
    mtime = int(st.st_mtime)
    age_sec = now - mtime
    j = load(f)
    print("========================================================")
    print("FILE:", f)
    print(f"mtime_utc={fmt_utc(mtime)} age_sec={age_sec} size={st.st_size}B")
    if not isinstance(j, dict):
        print("JSON_LOAD_FAIL_OR_NOT_DICT")
        continue
    # show values
    for k in fields:
        if k in j:
            print(f"- {k} = {safe(j.get(k))}")
    # derived health candidates (report only; DO NOT claim semantics yet)
    tf_ok = j.get("tf_ok")
    weak = j.get("weak")
    err  = j.get("error")
    # normalize possible error forms
    err_s = ""
    if err is None:
        err_s = ""
    elif isinstance(err, str):
        err_s = err.strip()
    else:
        err_s = str(err).strip()
    print()
    print("DERIVED_CANDIDATES (report-only):")
    print(f"- freshness_sec_candidate = now - mtime = {age_sec}")
    print(f"- cache_ok_candidate      = (tf_ok==True) AND (weak==False) AND (error empty) -> {bool(tf_ok is True and weak is False and err_s=='')}")
    print(f"- error_present_candidate = {bool(err_s!='')}")
print("========================================================")
print("NOTE: These are candidates only; Step 23E must find the canonical mapping in code (if any).")
PY
echo

echo "===== 23E) Determine default PAIRS/TFs used for status output (must match existing bot expectations) ====="
echo "--- Search for explicit pair/timeframe lists in scripts/config/state ---"
grep -RIn --line-number -E 'pairs\s*=\s*\[|PAIRS\s*=|SYMBOLS\s*=|WATCHLIST|EURUSD|GBPUSD|USDJPY|EURJPY|H1|M15|H4|D1' \
  ./tools ./state ./core ./*.py 2>/dev/null | head -n 260 || true
echo

echo "===== STEP 23 Acceptance criteria ====="
echo "A) We either find the canonical vote/score/signal computation in repo OR we prove it does not exist."
echo "B) We capture exact parsing anchors (=== BASIC === / === ADVANCED ===, header emoji 📊) already required by downstream tools."
echo "C) We list real indicators_* fields and their current values (tf_ok/weak/error/age_min/tf_actual_min) to ground health/cache labels."
echo "D) We identify the default pair/timeframe set expected by tg_bot + watchers (so replacement output remains compatible)."
echo
echo "Paste this entire output back here."
