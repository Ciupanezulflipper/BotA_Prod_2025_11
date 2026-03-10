#!/usr/bin/env bash
set -euo pipefail

echo "STATUS: ok"
echo "SCOPE: Analysis only (NO edits to existing files)."
echo "GOAL: Extract downstream parsing expectations + available indicators_* inputs for the status_pretty replacement."
echo

echo "===== 22A) Inventory: available indicators_* cache files (pairs/timeframes) ====="
if [[ -d cache ]]; then
  ls -1 cache/indicators_*.json 2>/dev/null | sed 's#^#- #' || true
else
  echo "MISSING: ./cache directory"
fi
echo

echo "===== 22B) Parse the available pairs/timeframes from filenames ====="
python3 - <<'PY'
import re, pathlib, time
from datetime import datetime, timezone

def fmt_utc(ts:int)->str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

root = pathlib.Path("cache")
pat = re.compile(r"^indicators_([A-Z0-9]+)_([A-Z0-9]+)\.json$")
pairs = {}
now = int(time.time())

files = sorted(root.glob("indicators_*.json"))
if not files:
    print("NO FILES: cache/indicators_*.json not found")
    raise SystemExit(0)

for f in files:
    m = pat.match(f.name)
    if not m:
        continue
    pair, tf = m.group(1), m.group(2)
    pairs.setdefault(pair, []).append(tf)

print("now_utc:", fmt_utc(now), "| epoch", now)
print()
print("Detected pairs/timeframes from cache:")
for pair in sorted(pairs):
    tfs = sorted(set(pairs[pair]))
    print(f"- {pair}: {', '.join(tfs)}")

print()
print("File freshness (mtime age) by pair/tf:")
for pair in sorted(pairs):
    for tf in sorted(set(pairs[pair])):
        p = root / f"indicators_{pair}_{tf}.json"
        st = p.stat()
        mtime = int(st.st_mtime)
        age = now - mtime
        print(f"- {pair} {tf}: mtime={fmt_utc(mtime)} age_sec={age} size={st.st_size}B")
PY
echo

echo "===== 22C) Downstream parsers: locate ANCHORS / regex expectations ====="
echo "--- tools/pretty_bridge.py (extracts BASIC/ADVANCED slices) ---"
if [[ -f tools/pretty_bridge.py ]]; then
  grep -nE "BASIC|ADVANCED|===|📊|EUR/USD|GBP/USD|USD/JPY|status_pretty\.py|split|extract|section" tools/pretty_bridge.py | sed -n '1,220p' || true
else
  echo "MISSING: tools/pretty_bridge.py"
fi
echo

echo "--- tools/signal_watcher.sh (greps lines out of status_pretty output) ---"
if [[ -f tools/signal_watcher.sh ]]; then
  grep -nE "status_pretty\.py|python3|EUR/USD|GBP/USD|USD/JPY|📊|🟢|🔴|NEUTRAL|BUY|SELL|grep|sed|awk|cut|head|tail|ADVANCED|BASIC|===" tools/signal_watcher.sh | sed -n '1,260p' || true
else
  echo "MISSING: tools/signal_watcher.sh"
fi
echo

echo "--- tools/probe_signals.py (parses formatted text) ---"
if [[ -f tools/probe_signals.py ]]; then
  grep -nE "status_pretty\.py|ADVANCED|BASIC|📊|EUR/USD|GBP/USD|USD/JPY|BUY|SELL|NEUTRAL|parse|split|regex" tools/probe_signals.py | sed -n '1,260p' || true
else
  echo "MISSING: tools/probe_signals.py"
fi
echo

echo "--- tg_bot.py (calls status_pretty) ---"
if [[ -f tg_bot.py ]]; then
  grep -nE "status_pretty\.py|PRETTY|advanced|basic|subprocess|python3|run\(" tg_bot.py | sed -n '1,220p' || true
else
  echo "MISSING: tg_bot.py"
fi
echo

echo "===== 22D) Confirm CURRENT output shape (demo) that parsers may rely on ====="
echo "----- RUN: python3 tools/status_pretty.py advanced (first 140 lines) -----"
python3 tools/status_pretty.py advanced 2>&1 | sed -n '1,140p'
echo

echo "===== 22E) Contract we must preserve (draft, grounded in 22C/22D) ====="
cat <<'TXT'
1) Must keep section headers exactly:
   - "=== BASIC ==="
   - "=== ADVANCED ==="
   (pretty_bridge/probe_signals likely splits by these anchors)

2) Each pair block must begin with a header line starting with:
   - "📊 " + pair_pretty + " " + TF + " — " + timestamp
   Example: "📊 EUR/USD H1 — 2026-02-03 17:15 UTC"

3) BASIC section must be 2 lines per pair:
   Line1: 📊 ...
   Line2: "<emoji> <SIGNAL> | RSI <int> | <trend_arrow> <+vote> | 🩺 <freshness>"
   (so signal_watcher grep/awk can extract BUY/SELL and freshness)

4) ADVANCED section must be 4 lines per pair (+ optional extras line):
   Line1: 📊 ...
   Line2: "<emoji> <SIGNAL> (Trend: <Bullish/Bearish/Range>) — Vote <+n>"
   Line3: "📈 RSI <int> | EMA 9>21/9<21/9≈21 <arrow>"
   Line4: "🩺 Fresh <freshness> | Provider: <...> | Cache OK/WARN"
   Optional Line5: begins with "🧪 " and can include "ADX <n> | ATR <n>p"

5) Timestamp source for replacement:
   - MUST be indicators_* file mtime (Step 19/20 proved this)
   - Freshness should be derived from now - indicators_mtime
   - Provider/Cache OK should reflect indicators tf_ok/weak/error fields (not Yahoo caches)

6) Inputs available (confirmed Step 21):
   indicators JSON keys include:
   pair,timeframe,price,age_min,tf_ok,tf_actual_min,weak,error,ema9,ema21,rsi,macd_hist,adx,atr,atr_pips
TXT
echo

echo "===== STEP 22 Acceptance criteria ====="
echo "A) Output shows which anchors downstream parsers grep/split on (from 22C)."
echo "B) Output shows current demo output shape (22D) to preserve compatibility."
echo "C) Output lists real inputs available + confirms timestamp source = indicators mtimes (22B/22E)."
echo
echo "Paste this entire output back here."
