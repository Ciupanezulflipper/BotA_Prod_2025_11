#!/usr/bin/env python3
"""
Bot A — Phase 5: Alert rules & parsing for early_watch output.

Reads early_watch.py text from STDIN and emits actionable signals as JSON.
Actionable definition (default):
  - Any line containing 'WATCH' and NOT containing 'too weak' / 'outside session'
  - OR abs(weighted) >= MIN_WEIGHT (default 2), taken from lines like:
      [early_watch] EURUSD weighted=3 bias=BULLISH

Env / CLI:
  MIN_WEIGHT (env) or --min-weight N   default 2
  --json  (default): emit JSON list of signals to stdout
  --text: quick human summary (debug)

Output JSON item shape:
  {
    "pair": "EURUSD",
    "weighted": 3,
    "bias": "BULLISH",
    "raw": "[early_watch] EURUSD weighted=3 bias=BULLISH",
    "reason": "threshold" | "watch"
  }
"""
from __future__ import annotations
import os, sys, json, re
from typing import List, Dict

LINE_RE = re.compile(
    r"^\s*\[early_watch\]\s+([A-Z/]+)\s+weighted=([-\d]+)\s+bias=([A-Za-z]+)",
    re.IGNORECASE,
)

def parse(text: str) -> List[Dict]:
    items: List[Dict] = []
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        # WATCH keyword (but not the negatives)
        if "WATCH" in s and ("too weak" not in s) and ("outside session" not in s):
            # Try to extract pair if present, fall back to raw
            m = LINE_RE.search(s)
            pair = (m.group(1).replace("/", "") if m else "UNKNOWN").upper()
            w = int(m.group(2)) if (m and m.group(2).lstrip("-").isdigit()) else 0
            bias = (m.group(3).upper() if m else "UNKNOWN")
            items.append({"pair": pair, "weighted": w, "bias": bias, "raw": s, "reason": "watch"})
            continue
        # Standard weighted/bias status line
        m = LINE_RE.match(s)
        if m:
            pair = m.group(1).replace("/", "").upper()
            weighted = int(m.group(2))
            bias = m.group(3).upper()
            items.append({"pair": pair, "weighted": weighted, "bias": bias, "raw": s, "reason": "status"})
    return items

def filter_actionable(items: List[Dict], min_weight: int) -> List[Dict]:
    out: List[Dict] = []
    for it in items:
        if it["reason"] == "watch":
            out.append(it)
        else:
            if abs(it.get("weighted", 0)) >= min_weight:
                it2 = dict(it)
                it2["reason"] = "threshold"
                out.append(it2)
    # dedupe by pair keeping strongest
    best: Dict[str, Dict] = {}
    for it in out:
        key = it["pair"]
        cur = best.get(key)
        if cur is None or abs(it.get("weighted", 0)) > abs(cur.get("weighted", 0)):
            best[key] = it
    return list(best.values())

def main() -> int:
    # thresholds
    try:
        min_weight = int(os.getenv("MIN_WEIGHT", os.getenv("ALERT_WEIGHT_THRESHOLD", "2")))
    except ValueError:
        min_weight = 2
    # flags
    mode_text = ("--text" in sys.argv)
    # read stdin
    data = sys.stdin.read() if not sys.stdin.isatty() else ""
    parsed = parse(data)
    actionable = filter_actionable(parsed, min_weight)
    if mode_text:
        if not actionable:
            print("(no actionable)")
        else:
            for it in actionable:
                print(f"{it['pair']}: weighted={it['weighted']} bias={it['bias']} [{it['reason']}]")
    else:
        print(json.dumps(actionable, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    sys.exit(main())
