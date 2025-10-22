# Market structure tools: volume profile, swing levels, round numbers, sessions

from typing import List, Dict, Tuple, Optional
import math, datetime as dt

def volume_profile(candles: List[Dict], bins: int = 40) -> Dict[str, object]:
    """Simple volume profile over given candles. Returns {bins:[(price,vol)], poc:price, val_low, val_high}"""
    if not candles: return {"bins": [], "poc": None, "val_low": None, "val_high": None}
    lows  = [c["l"] for c in candles]; highs = [c["h"] for c in candles]
    vols  = [c.get("v", 0.0) for c in candles]
    lo, hi = min(lows), max(highs)
    if hi <= lo: hi = lo + 1e-6
    step = (hi - lo) / float(bins)
    hist = [0.0] * bins
    for c in candles:
        p = (c["h"] + c["l"] + c["c"]) / 3.0
        b = min(bins - 1, int((p - lo) / step))
        hist[b] += c.get("v", 0.0)
    bins_out = []
    for i, v in enumerate(hist):
        price = lo + (i + 0.5) * step
        bins_out.append((price, v))
    # POC and value area (70%)
    total = sum(hist) or 1.0
    poc_index = max(range(bins), key=lambda i: hist[i]) if bins else 0
    sorted_ix = sorted(range(bins), key=lambda i: hist[i], reverse=True)
    acc = 0.0; take = set()
    for i in sorted_ix:
        take.add(i); acc += hist[i]
        if acc / total >= 0.7: break
    val_low  = lo + (min(take) + 0.5) * step
    val_high = lo + (max(take) + 0.5) * step
    return {"bins": bins_out, "poc": lo + (poc_index + 0.5) * step, "val_low": val_low, "val_high": val_high}

def swing_levels(candles: List[Dict], lookback: int = 5) -> Tuple[List[float], List[float]]:
    """Detect local swing highs/lows using a simple window."""
    highs = []; lows = []
    for i in range(lookback, len(candles) - lookback):
        h = candles[i]["h"]; l = candles[i]["l"]
        hh = max(c["h"] for c in candles[i - lookback:i + lookback + 1])
        ll = min(c["l"] for c in candles[i - lookback:i + lookback + 1])
        if h >= hh: highs.append(h)
        if l <= ll: lows.append(l)
    return highs, lows

def round_numbers(candles: List[Dict], step: float) -> List[float]:
    """Round-number magnets (e.g., 0.005 for FX, 1.0 for metals)."""
    if not candles: return []
    lo = min(c["l"] for c in candles); hi = max(c["h"] for c in candles)
    rn=[]; p = math.floor(lo/step)*step
    while p <= hi:
        rn.append(round(p, 10))
        p += step
    return rn

def session_tag(ts_utc: str) -> str:
    """Tag by session (rough UTC windows)."""
    t = dt.datetime.fromisoformat(ts_utc.replace("Z","")).time()
    h = t.hour
    if 0 <= h < 8:   return "ASIA"
    if 8 <= h < 13:  return "EU_PRE"
    if 13 <= h < 16: return "OVERLAP"
    if 16 <= h < 21: return "US"
    return "OFF"
