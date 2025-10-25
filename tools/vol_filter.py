#!/usr/bin/env python3
from __future__ import annotations
import os, sys, re, json
from statistics import pstdev
from typing import Dict, List, Tuple

ROOT = os.path.expanduser("~/BotA")
RUN_LOG = os.path.join(ROOT, "run.log")

HEADER_RE = re.compile(r"^===\s+([A-Z/]+)\s+snapshot\s+===$")
H1_RE = re.compile(
    r"^H1:\s+t=[^ ]+\s+close=([0-9.]+)\s+EMA9=[0-9.]+\s+EMA21=[0-9.]+\s+RSI14=(?:[0-9.]+|NA)\s+MACD_hist=(?:[-\d.]+|NA)\s+vote=[+\-]?\d+"
)

def load_h1_closes() -> Dict[str, List[float]]:
    closes: Dict[str, List[float]] = {}
    try:
        with open(RUN_LOG, "r", encoding="utf-8", errors="replace") as f:
            lines = f.read().splitlines()
    except FileNotFoundError:
        return closes
    cur = None
    for ln in lines:
        h = HEADER_RE.match(ln.strip())
        if h:
            cur = h.group(1).replace("/", "").upper()
            continue
        if cur:
            m = H1_RE.match(ln.strip())
            if m:
                closes.setdefault(cur, []).append(float(m.group(1)))
    return closes

def last_n_std(x: List[float], n: int) -> float:
    if len(x) < n:
        return 0.0
    # use returns std
    rets = [x[i] - x[i-1] for i in range(1, len(x))]
    if len(rets) < n:
        return 0.0
    window = rets[-n:]
    m = sum(window)/len(window)
    # population std
    var = sum((v-m)**2 for v in window)/len(window)
    return var**0.5

def main() -> int:
    # env knobs
    try:
        n = int(os.getenv("VOL_MIN_COUNT", "20"))
    except ValueError:
        n = 20
    try:
        thresh = float(os.getenv("VOL_MIN_STD", "0.00015"))
    except ValueError:
        thresh = 0.00015

    raw = sys.stdin.read().strip()
    try:
        arr = json.loads(raw) if raw else []
    except Exception:
        arr = []

    h1 = load_h1_closes()
    out = []
    for it in arr:
        pair = it.get("pair", "").upper()
        std = last_n_std(h1.get(pair, []), n)
        it2 = dict(it)
        it2["vol_std"] = std
        it2["vol_ok"] = std >= thresh
        if it2["vol_ok"]:
            out.append(it2)
    print(json.dumps(out, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    sys.exit(main())
