#!/usr/bin/env python3
# tools/risk_filter.py
# Lightweight risk sanity checks (no external data).
# - Enforces min SL/TP distance in pips.
# - Enforces min Risk:Reward.
# - Optional spread and ATR guards (via env overrides).
#
# Symbols supported: EURUSD, XAUUSD. Defaults are sensible; override via env:
#   EURUSD:
#     BOT_A_MIN_STOP_PIPS_EURUSD=5
#     BOT_A_MIN_TP_PIPS_EURUSD=8
#     BOT_A_MIN_RR_EURUSD=1.2
#     BOT_A_MAX_SPREAD_PIPS_EURUSD=2.0
#     BOT_A_ATR_MIN_PIPS_EURUSD=0     # 0 = disabled
#   XAUUSD:
#     BOT_A_MIN_STOP_PIPS_XAUUSD=50
#     BOT_A_MIN_TP_PIPS_XAUUSD=80
#     BOT_A_MIN_RR_XAUUSD=1.2
#     BOT_A_MAX_SPREAD_PIPS_XAUUSD=8.0
#     BOT_A_ATR_MIN_PIPS_XAUUSD=0
#
# Optional static spread if you want a hard cap but lack live spread:
#     BOT_A_SPREAD_PIPS_EURUSD=1.5
#     BOT_A_SPREAD_PIPS_XAUUSD=4.0
#
# Return shape from evaluate():
#   {
#     "ok": bool,
#     "reasons": [ "text", ... ],
#     "metrics": { "stop_pips": float, "tp_pips": float, "rr": float, "spread_pips": float|None }
#   }

from typing import Dict, Any, Optional
import os

_PIP_DECIMALS = {
    "EURUSD": 4,   # 0.0001
    "XAUUSD": 1,   # 0.1
}

def _pip_value(symbol: str) -> float:
    d = _PIP_DECIMALS.get(symbol.upper(), 4)
    return 10 ** (-d)

def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except Exception:
        return default

def _cfg_for(symbol: str) -> Dict[str, float]:
    s = symbol.upper()
    if s == "XAUUSD":
        return {
            "min_stop": _env_float("BOT_A_MIN_STOP_PIPS_XAUUSD", 50.0),
            "min_tp":   _env_float("BOT_A_MIN_TP_PIPS_XAUUSD",   80.0),
            "min_rr":   _env_float("BOT_A_MIN_RR_XAUUSD",        1.2),
            "max_sp":   _env_float("BOT_A_MAX_SPREAD_PIPS_XAUUSD", 8.0),
            "atr_min":  _env_float("BOT_A_ATR_MIN_PIPS_XAUUSD",  0.0),
            "def_sp":   _env_float("BOT_A_SPREAD_PIPS_XAUUSD",   -1.0),
        }
    # EURUSD default
    return {
        "min_stop": _env_float("BOT_A_MIN_STOP_PIPS_EURUSD", 5.0),
        "min_tp":   _env_float("BOT_A_MIN_TP_PIPS_EURUSD",   8.0),
        "min_rr":   _env_float("BOT_A_MIN_RR_EURUSD",        1.2),
        "max_sp":   _env_float("BOT_A_MAX_SPREAD_PIPS_EURUSD", 2.0),
        "atr_min":  _env_float("BOT_A_ATR_MIN_PIPS_EURUSD",  0.0),
        "def_sp":   _env_float("BOT_A_SPREAD_PIPS_EURUSD",   -1.0),
    }

def _to_float(v) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except Exception:
        return None

def evaluate(symbol: str, decision: str, entry, tp, sl, atr_pips: Optional[float]=None, spread_pips: Optional[float]=None) -> Dict[str, Any]:
    """
    Basic sanity:
      - SL and TP must be present, numeric.
      - stop distance >= min_stop
      - tp distance   >= min_tp
      - RR            >= min_rr
      - if spread known or default provided, spread <= max_sp
      - if atr_min > 0 and atr provided, require stop_pips >= atr_min
    """
    s = symbol.upper()
    pv = _pip_value(s)
    cfg = _cfg_for(s)
    reasons = []

    e = _to_float(entry)
    t = _to_float(tp)
    l = _to_float(sl)

    if e is None or t is None or l is None:
        return {
            "ok": False,
            "reasons": ["missing entry/tp/sl"],
            "metrics": {"stop_pips": None, "tp_pips": None, "rr": None, "spread_pips": spread_pips},
        }

    stop_pips = abs(e - l) / pv
    tp_pips   = abs(t - e) / pv
    rr = tp_pips / stop_pips if stop_pips > 0 else 0.0

    # Min distances
    if stop_pips < cfg["min_stop"]:
        reasons.append(f"stop too small: {stop_pips:.1f}p < {cfg['min_stop']:.1f}p")
    if tp_pips < cfg["min_tp"]:
        reasons.append(f"tp too small: {tp_pips:.1f}p < {cfg['min_tp']:.1f}p")
    if rr < cfg["min_rr"]:
        reasons.append(f"RR too low: {rr:.2f} < {cfg['min_rr']:.2f}")

    # Spread: use provided, else env default if set (>0)
    sp = spread_pips
    if (sp is None or sp <= 0) and cfg["def_sp"] > 0:
        sp = cfg["def_sp"]
    if sp is not None and sp > 0 and sp > cfg["max_sp"]:
        reasons.append(f"spread high: {sp:.1f}p > {cfg['max_sp']:.1f}p")

    # ATR gate if supplied and configured
    atr_min = cfg["atr_min"]
    if atr_min > 0 and (atr_pips is not None) and (stop_pips < atr_min):
        reasons.append(f"stop < ATR_min: {stop_pips:.1f}p < {atr_min:.1f}p")

    return {
        "ok": (len(reasons) == 0),
        "reasons": reasons,
        "metrics": {"stop_pips": stop_pips, "tp_pips": tp_pips, "rr": rr, "spread_pips": sp},
    }
