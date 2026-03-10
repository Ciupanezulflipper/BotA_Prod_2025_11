#!/usr/bin/env python3
"""
Pair pip/point utilities for BotA accuracy.
- Default FX majors: 0.0001
- JPY crosses:      0.01
- XAUUSD (gold):    0.10 point granularity by default (treat as "pips" for display)
You can override via environment PIP_OVERRIDE_JSON='{"XAUUSD":0.05}' if needed.
"""
from __future__ import annotations
import json, os
from typing import Dict

DEFAULT_MAP: Dict[str, float] = {
    # Majors (4 dp)
    "EURUSD": 0.0001, "GBPUSD": 0.0001, "AUDUSD": 0.0001, "NZDUSD": 0.0001, "USDCAD": 0.0001, "USDCHF": 0.0001,
    # Yen pairs (2 dp)
    "USDJPY": 0.01, "EURJPY": 0.01, "GBPJPY": 0.01, "AUDJPY": 0.01, "CADJPY": 0.01, "CHFJPY": 0.01,
    # Metals
    "XAUUSD": 0.10,  # treat 0.10 as one "pip" unit for evaluation display
}

def _load_override() -> Dict[str, float]:
    raw = os.environ.get("PIP_OVERRIDE_JSON","").strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return {k.upper(): float(v) for k,v in data.items()}
    except Exception:
        return {}

PIP_MAP: Dict[str, float] = {**DEFAULT_MAP, **_load_override()}

def pip_value(pair: str) -> float:
    return PIP_MAP.get(pair.upper(), 0.0001)

def price_to_pips(pair: str, delta_price: float) -> float:
    pv = pip_value(pair)
    if pv <= 0: return 0.0
    return delta_price / pv

def pips_to_price(pair: str, pips: float) -> float:
    return pips * pip_value(pair)
