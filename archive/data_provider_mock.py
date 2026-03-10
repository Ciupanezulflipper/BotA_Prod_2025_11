#!/usr/bin/env python3
"""
Deterministic mock data provider for BotA.

Usage:
  1) Save this file exactly as:  tools/data_provider_mock.py
  2) In your shell (or in ~/.env.runtime) set:
       PROVIDER_ORDER=data_provider_mock
  3) Run:
       bash tools/run_signal_once.sh EURUSD 15 150
  4) Inspect:
       sed -n '1,120p' logs/signal_EURUSD_15.json

This provider returns fresh, schema-correct candles so the pipeline can be
validated without hitting real APIs. It always reports ok=True, rows>=limit,
age_min≈0.0, and a recent last_ts.
"""

from __future__ import annotations
import time
from typing import Dict, Any, List

def _gen_candles(n: int = 150,
                 base: float = 1.1500,
                 drift: float = 0.00002) -> List[Dict[str, Any]]:
    """
    Generate n candles (oldest → newest) with keys:
      t (epoch seconds), o, h, l, c, v

    - Close 'c' drifts gently upward to yield a mild bullish bias.
    - 60s spacing so data appears fresh for intraday TFs.
    """
    now = int(time.time())
    candles: List[Dict[str, Any]] = []
    price = base

    for i in range(n):
        # Oldest first: start n minutes ago, 60s per step
        ts = now - (n - i) * 60

        # Gentle wiggle for realism without breaking confluence math
        wiggle = ((i % 20) - 10) * drift * 0.6
        price = price + drift + wiggle

        o = round(price - drift * 0.8, 6)
        c = round(price, 6)
        h = round(max(o, c) + 0.0003, 6)
        l = round(min(o, c) - 0.0003, 6)

        candles.append({
            "t": ts,
            "o": o,
            "h": h,
            "l": l,
            "c": c,      # SIGNAL ENGINE reads close via key 'c'
            "v": 1000,   # constant volume placeholder
        })

    return candles

def fetch(symbol: str, tf: str, limit: int) -> Dict[str, Any]:
    """
    Contract expected by tools/signal_engine._normalize_result():
      {
        "ok": bool,
        "rows": int,
        "age_min": float,
        "last_ts": int|str,
        "candles": list[dict],  # must include key 'c' for close
        "error": Optional[str]
      }
    """
    try:
        n = int(limit)
    except Exception:
        n = 150
    n = max(150, n)

    candles = _gen_candles(n=n)

    return {
        "ok": True,
        "rows": len(candles),
        "age_min": 0.0,                 # Always fresh
        "last_ts": candles[-1]["t"],    # Timestamp of the newest candle
        "candles": candles,             # List of dicts with 'c' present
        # "error": None  # omitted when ok=True
    }
