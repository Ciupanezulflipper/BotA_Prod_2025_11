#!/usr/bin/env python3
from __future__ import annotations
import os, sys, re, json
from collections import defaultdict
from typing import List, Dict, Tuple

ROOT = os.path.expanduser("~/BotA")
RUN_LOG = os.path.join(ROOT, "run.log")

HEADER_RE = re.compile(r"^===\s+([A-Z/]+)\s+snapshot\s+===$")
TF_RE = re.compile(
    r"^(H1|H4|D1):\s+t=([0-9:-]+\s?[0-9:]*Z)\s+close=([0-9.]+)\s+EMA9=([0-9.]+)\s+EMA21=([0-9.]+)\s+RSI14=([0-9.]+|NA)\s+MACD_hist=([-\d.]+|NA)\s+vote=([+\-]?\d+)"
)

def load_runs(path: str) -> Dict[str, Dict[str, List[Tuple[float, float, float, int]]]]:
    """Return series[pair][tf] -> [(close, rsi, macd, vote), ...] chronological."""
    lines = []
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.read().splitlines()
    except FileNotFoundError:
        return {}
    cur = None
    series = defaultdict(lambda: defaultdict(list))
    for ln in lines:
        h = HEADER_RE.match(ln.strip())
        if h:
            cur = h.group(1).replace("/", "").upper()
            continue
        m = TF_RE.match(ln.strip())
        if m and cur:
            tf, _ts, close, _e9, _e21, rsi, macd, vote = m.groups()
            c = float(close)
            r = None if rsi == "NA" else float(rsi)
            mval = None if macd == "NA" else float(macd)
            v = int(vote)
            series[cur][tf].append((c, r if r is not None else 0.0, mval if mval is not None else 0.0, v))
    return series

def rolling(values: List[float], n: int) -> float:
    if not values: return 0.0
    if len(values) < n: return sum(values)/len(values)
    return sum(values[-n:]) / n

def divergence(last3: List[Tuple[float, float]]) -> str:
    """Simple divergence on last 3 points: price vs RSI.
       bearish if price up while RSI down; bullish if price down while RSI up."""
    if len(last3) < 3: return "none"
    (c1, r1), (c2, r2), (c3, r3) = last3[-3:]
    price_up = c3 > c1 + 1e-9
    price_dn = c3 < c1 - 1e-9
    rsi_up = r3 > r1 + 1e-9
    rsi_dn = r3 < r1 - 1e-9
    if price_up and rsi_dn: return "bearish"
    if price_dn and rsi_up: return "bullish"
    return "none"

def enrich(items: List[Dict]) -> List[Dict]:
    series = load_runs(RUN_LOG)
    out = []
    for it in items:
        pair = it.get("pair","").upper()
        s = series.get(pair, {})
        # build simple aggregates across TFs
        feats = {}
        for tf in ("H1","H4","D1"):
            pts = s.get(tf, [])
            closes = [p[0] for p in pts]
            rsis = [p[1] for p in pts]
            macds = [p[2] for p in pts]
            votes = [p[3] for p in pts]
            feats[tf] = {
                "vote_mean_5": rolling(votes, 5),
                "macd_mean_5": rolling(macds, 5),
                "div_rsi": divergence(list(zip(closes, rsis))),
                "len": len(pts),
            }
        it2 = dict(it)
        it2["analytics"] = feats
        # summarize a strength score: current |weighted| + avg of recent votes across TFs
        avg_votes = sum(feats[tf]["vote_mean_5"] for tf in ("H1","H4","D1")) / 3.0
        it2["strength"] = round(abs(it.get("weighted",0)) + abs(avg_votes), 2)
        # preferred_tf: TF with longest history
        it2["preferred_tf"] = max(("H1","H4","D1"), key=lambda tf: feats[tf]["len"])
        out.append(it2)
    return out

def main() -> int:
    raw = sys.stdin.read()
    try:
        arr = json.loads(raw) if raw.strip() else []
    except Exception:
        arr = []
    enr = enrich(arr)
    print(json.dumps(enr, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    sys.exit(main())
