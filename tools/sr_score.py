#!/usr/bin/env python3
"""
BotA Support/Resistance Proximity Scorer
=========================================
Detects S/R levels from H1 candles using swing high/low detection.
Scores current price proximity to nearest S/R level.

Score output:
  +8  = price at key support (BUY) or resistance (SELL) — strong confluence
  +5  = price near support/resistance (within 0.5x ATR)
  +3  = mild proximity (within 1x ATR)
   0  = neutral (no nearby levels)
  -5  = price trading INTO resistance (BUY) or INTO support (SELL)
  -8  = price deep inside opposing zone

Usage:
  python3 tools/sr_score.py --pair EURUSD --direction BUY --price 1.1480 --atr 0.0008
  Returns: integer score on stdout

Called from scoring_engine.sh:
  sr_comp=$(python3 "${TOOLS}/sr_score.py" \
    --pair "${PAIR}" --direction "${direction}" \
    --price "${price}" --atr "${atr}" 2>/dev/null || echo "0")
"""

from __future__ import annotations
import os, sys, json, argparse, math
from pathlib import Path
from typing import List, Tuple

ROOT  = Path(os.environ.get("BOTA_ROOT", Path.home() / "BotA"))
CACHE = ROOT / "cache"


def load_h1_candles(pair: str) -> List[dict]:
    """Load H1 candles from cache. Returns list of {h, l, c} dicts."""
    path = CACHE / f"{pair}_H1.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return []
        result = data.get("chart", {}).get("result", [{}])[0]
        ts  = result.get("timestamp", [])
        q   = result.get("indicators", {}).get("quote", [{}])[0]
        highs  = q.get("high", [])
        lows   = q.get("low", [])
        closes = q.get("close", [])
        n = min(len(ts), len(highs), len(lows), len(closes))
        candles = []
        for i in range(n):
            h = highs[i]
            l = lows[i]
            c = closes[i]
            if h is None or l is None or c is None:
                continue
            if h <= 0 or l <= 0:
                continue
            candles.append({"h": float(h), "l": float(l), "c": float(c)})
        return candles
    except Exception:
        return []


def detect_swing_levels(candles: List[dict], lookback: int = 100,
                         window: int = 3) -> Tuple[List[float], List[float]]:
    """
    Detect swing highs and swing lows using rolling window.
    Returns (resistance_levels, support_levels)
    """
    if len(candles) < window * 2 + 1:
        return [], []

    recent = candles[-lookback:] if len(candles) > lookback else candles
    highs  = [c["h"] for c in recent]
    lows   = [c["l"] for c in recent]

    resistances = []
    supports    = []

    for i in range(window, len(recent) - window):
        # Swing high: higher than all candles in window on both sides
        h = highs[i]
        if all(h >= highs[i-j] for j in range(1, window+1)) and \
           all(h >= highs[i+j] for j in range(1, window+1)):
            resistances.append(h)

        # Swing low: lower than all candles in window on both sides
        l = lows[i]
        if all(l <= lows[i-j] for j in range(1, window+1)) and \
           all(l <= lows[i+j] for j in range(1, window+1)):
            supports.append(l)

    return resistances, supports


def merge_levels(levels: List[float], merge_pips: float = 0.0010) -> List[float]:
    """Merge levels that are within merge_pips of each other."""
    if not levels:
        return []
    sorted_levels = sorted(set(levels))
    merged = [sorted_levels[0]]
    for level in sorted_levels[1:]:
        if level - merged[-1] > merge_pips:
            merged.append(level)
        else:
            # Replace with midpoint
            merged[-1] = (merged[-1] + level) / 2
    return merged


def score_sr_proximity(price: float, direction: str, atr: float,
                        resistances: List[float], supports: List[float]) -> int:
    """
    Score signal based on S/R proximity.

    BUY signals:
      - Near support = GOOD (price bouncing off floor) → +8 to +3
      - Near resistance = BAD (price hitting ceiling) → -5 to -8

    SELL signals:
      - Near resistance = GOOD (price hitting ceiling) → +8 to +3
      - Near support = BAD (price at floor) → -5 to -8
    """
    if atr <= 0 or not (resistances or supports):
        return 0

    direction = direction.upper()

    # Find nearest support and resistance
    nearest_support    = min(supports,    key=lambda x: abs(x - price)) if supports    else None
    nearest_resistance = min(resistances, key=lambda x: abs(x - price)) if resistances else None

    def dist_atr(level):
        return abs(price - level) / atr

    best_score = 0

    if direction == "BUY":
        # Support confluence
        if nearest_support is not None:
            dist = dist_atr(nearest_support)
            is_at_or_above = price >= nearest_support  # price at or above support
            if is_at_or_above:
                if dist <= 0.3:
                    best_score = max(best_score, 8)   # at support — strong buy
                elif dist <= 0.8:
                    best_score = max(best_score, 5)   # near support
                elif dist <= 1.5:
                    best_score = max(best_score, 3)   # mild proximity

        # Resistance headwind
        if nearest_resistance is not None:
            dist = dist_atr(nearest_resistance)
            is_below = price < nearest_resistance  # price approaching resistance
            if is_below:
                if dist <= 0.3:
                    best_score = min(best_score, -8)  # right at resistance wall
                elif dist <= 0.8:
                    best_score = min(best_score, -5)  # close to resistance

    elif direction == "SELL":
        # Resistance confluence
        if nearest_resistance is not None:
            dist = dist_atr(nearest_resistance)
            is_at_or_below = price <= nearest_resistance
            if is_at_or_below:
                if dist <= 0.3:
                    best_score = max(best_score, 8)   # at resistance — strong sell
                elif dist <= 0.8:
                    best_score = max(best_score, 5)
                elif dist <= 1.5:
                    best_score = max(best_score, 3)

        # Support headwind
        if nearest_support is not None:
            dist = dist_atr(nearest_support)
            is_above = price > nearest_support
            if is_above:
                if dist <= 0.3:
                    best_score = min(best_score, -8)
                elif dist <= 0.8:
                    best_score = min(best_score, -5)

    return best_score


def main():
    ap = argparse.ArgumentParser(description="BotA S/R Proximity Scorer")
    ap.add_argument("--pair",      required=True)
    ap.add_argument("--direction", required=True, choices=["BUY", "SELL"])
    ap.add_argument("--price",     required=True, type=float)
    ap.add_argument("--atr",       required=True, type=float)
    ap.add_argument("--debug",     action="store_true")
    args = ap.parse_args()

    pair = args.pair.upper().replace("/", "").replace("_", "")

    candles = load_h1_candles(pair)
    if len(candles) < 10:
        print("0")
        return

    resistances, supports = detect_swing_levels(candles, lookback=100, window=3)

    # Merge levels within 10 pips
    pip = 0.01 if "JPY" in pair else 0.0001
    resistances = merge_levels(resistances, merge_pips=10 * pip)
    supports    = merge_levels(supports,    merge_pips=10 * pip)

    score = score_sr_proximity(
        args.price, args.direction, args.atr,
        resistances, supports
    )

    if args.debug:
        sys.stderr.write(f"[SR] pair={pair} dir={args.direction} "
                         f"price={args.price} atr={args.atr}\n")
        sys.stderr.write(f"[SR] resistances={[round(r,5) for r in resistances[-5:]]}\n")
        sys.stderr.write(f"[SR] supports={[round(s,5) for s in supports[-5:]]}\n")
        sys.stderr.write(f"[SR] score={score}\n")

    print(score)


if __name__ == "__main__":
    main()

