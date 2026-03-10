#!/usr/bin/env python3
"""
BotA — early_watch bridge → JSON for alert pipeline

v2.2 changes:
- Parse HYBRID / HTF_ONLY / SCALPER_ONLY from early_watch lines.
- Introduce two thresholds:
    • MIN_WEIGHT_TRADE (defaults to MIN_WEIGHT / ALERT_WEIGHT_THRESHOLD / 2)
    • MIN_WEIGHT_WATCH (defaults to 1)
- Enforce:
    • Only HYBRID can ever be "trade" tier.
    • HTF_ONLY and SCALPER_ONLY are always "watch" tier at best.
- Preserve best (highest |weighted|) entry per pair.
- Output schema (per item):
    {
      "pair": "EURUSD",
      "weighted": 3,
      "bias": "BUY",
      "source": "HYBRID" | "HTF_ONLY" | "SCALPER_ONLY" | "UNKNOWN",
      "reason": "threshold" | "watch" | "status",
      "tier": "trade" | "watch",
      "raw": "[early_watch] …"
    }
"""

from __future__ import annotations
import os
import sys
import json
import re
from typing import List, Dict, Any

LINE_RE = re.compile(
    r"""
    ^\s*\[early_watch\]\s+        
    ([A-Z/]+)                     
    .*?weighted=([\-0-9]+)\s+     
    bias=([A-Za-z]+)              
    (?:\s+source=([A-Z_]+))?      
    """,
    re.IGNORECASE | re.VERBOSE,
)

def parse(text: str) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue

        m = LINE_RE.search(s)
        if not m:
            continue

        pair_raw = m.group(1) or "UNKNOWN"
        pair = pair_raw.replace("/", "").upper()

        try:
            weighted = int(m.group(2))
        except Exception:
            weighted = 0

        bias = (m.group(3) or "UNKNOWN").upper()
        source = (m.group(4) or "UNKNOWN").upper()

        reason = "watch" if "WATCH" in s.upper() else "status"

        items.append(
            {
                "pair": pair,
                "weighted": weighted,
                "bias": bias,
                "source": source,
                "raw": s,
                "reason": reason,
            }
        )
    return items


def filter_actionable(items: List[Dict[str, Any]], min_weight_trade: int, min_weight_watch: int) -> List[Dict[str, Any]]:
    if not items:
        return []

    best_by_pair: Dict[str, Dict[str, Any]] = {}
    for it in items:
        pair = it["pair"]
        w = abs(int(it.get("weighted", 0)))
        cur = best_by_pair.get(pair)
        if cur is None or w > abs(int(cur.get("weighted", 0))):
            best_by_pair[pair] = it

    out: List[Dict[str, Any]] = []
    for pair, it in best_by_pair.items():
        w = abs(int(it.get("weighted", 0)))
        source = it.get("source", "UNKNOWN").upper()

        tier = None

        if source == "HYBRID" and w >= min_weight_trade:
            tier = "trade"
        elif w >= min_weight_watch:
            tier = "watch"
        else:
            continue

        it2 = dict(it)
        it2["tier"] = tier

        if tier == "trade":
            it2["reason"] = "threshold"
        else:
            if it2.get("reason") not in ("watch", "status", "threshold"):
                it2["reason"] = "watch"

        out.append(it2)

    return out


def main() -> int:
    try:
        min_weight_trade = int(
            os.getenv(
                "MIN_WEIGHT_TRADE",
                os.getenv(
                    "MIN_WEIGHT",
                    os.getenv("ALERT_WEIGHT_THRESHOLD", "2"),
                ),
            )
        )
    except Exception:
        min_weight_trade = 2

    try:
        min_weight_watch = int(os.getenv("MIN_WEIGHT_WATCH", "1"))
    except Exception:
        min_weight_watch = 1

    text = "" if sys.stdin.isatty() else sys.stdin.read()

    parsed = parse(text)
    actionable = filter_actionable(parsed, min_weight_trade, min_weight_watch)
    print(json.dumps(actionable, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
