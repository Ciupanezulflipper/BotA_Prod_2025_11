#!/usr/bin/env python3
"""
scoring.py — computes a trade signal for a symbol/timeframe.

Exports:
    score_v2(symbol: str, tf: str="5min", limit: int=300) -> dict

Returns dict with:
{
  "side": "BUY"/"SELL"/"HOLD",
  "score": int,
  "bias": "Bullish"/"Bearish"/"Neutral",
  "entry": float or None,
  "stop": float or None,
  "target": float or None,
  "trend": int, "mom": int, "vol": int, "struct": int, "volat": int,
  "note": str
}
"""

from __future__ import annotations
import math, os
import numpy as np
import pandas as pd
from typing import Optional, Dict

from tools import providers  # relies on your existing tools/providers.py

def _ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False, min_periods=max(1, n)).mean()

def _rsi14(close: pd.Series) -> pd.Series:
    delta = close.diff()
    up = delta.clip(lower=0.0)
    dn = (-delta).clip(lower=0.0)
    roll_up = up.ewm(alpha=1/14, adjust=False).mean()
    roll_dn = dn.ewm(alpha=1/14, adjust=False).mean()
    rs = roll_up / (roll_dn.replace(0, np.nan))
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50.0)

def _atr(df: pd.DataFrame, n: int=14) -> pd.Series:
    h, l, c = df["High"], df["Low"], df["Close"]
    tr = pd.concat([
        (h - l),
        (h - c.shift()).abs(),
        (l - c.shift()).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1/n, adjust=False).mean()

def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))

def _swing_score(close: pd.Series, look: int=40) -> float:
    # very light structure proxy: std of rolling median deviations
    m = close.rolling(look, min_periods=max(2, look//2)).median()
    dev = (close - m).abs()
    v = float(dev.tail(look).mean() / (close.tail(look).mean()+1e-9))
    # scale to ~0..20
    return _clamp(v * 100.0, 0, 20)

def _bias_from_rsi(rsi_last: float, above50: bool, above200: bool) -> str:
    if above50 and above200 and rsi_last >= 52:
        return "Bullish"
    if (not above50) and (not above200) and rsi_last <= 48:
        return "Bearish"
    return "Neutral"

def score_v2(symbol: str, tf: str="5min", limit: int=300) -> Dict[str, object]:
    # Pull recent candles
    df = providers.fetch_ohlcv_safe(symbol, tf=tf, limit=limit)
    if df is None or df.empty or "Close" not in df:
        # no data; return a "no-op" HOLD
        return {
            "side": "HOLD", "score": 0, "bias": "Neutral",
            "entry": None, "stop": None, "target": None,
            "trend": 0, "mom": 0, "vol": 0, "struct": 0, "volat": 0,
            "note": "no data"
        }

    df = df.copy()
    close = df["Close"].astype(float)

    # EMAs
    df["ema20"]  = _ema(close, 20)
    df["ema50"]  = _ema(close, 50)
    df["ema200"] = _ema(close, 200)

    # RSI + ATR
    df["rsi14"] = _rsi14(close)
    df["atr14"] = _atr(df, 14)

    # Components
    trend = 0
    # slope/stacking heuristic
    last = df.iloc[-1]
    if last["ema20"] > last["ema50"] > last["ema200"]:
        trend += 8
    if last["ema20"] > df["ema20"].iloc[-5]:
        trend += 6
    if last["ema50"] > df["ema50"].iloc[-10]:
        trend += 4
    # cap
    trend = int(_clamp(trend, 0, 20))

    # momentum via RSI position & change
    rsi_last = float(last["rsi14"])
    rsi_prev = float(df["rsi14"].iloc[-5])
    mom = int(_clamp((rsi_last - 50) / 2.0 + (rsi_last - rsi_prev) / 2.0, 0, 20))

    # volatility stat (rolling std of returns scaled)
    ret = close.pct_change().tail(60)
    vol = int(_clamp(ret.std() * 1000.0, 0, 20))

    # structure proxy
    struct = int(_swing_score(close, 40))

    # ATR% of price
    atrp = float(last["atr14"] / (last["Close"] + 1e-9) * 100.0)
    volat = int(_clamp(atrp, 0, 20))

    # bias
    above50  = bool(last["Close"] > last["ema50"])
    above200 = bool(last["Close"] > last["ema200"])
    bias = _bias_from_rsi(rsi_last, above50, above200)

    # tiny heuristic note and side
    note = "-"
    if trend >= 12 and mom >= 6 and struct >= 8:
        note = "trend momentum present, clean structure"
        bias_pref = "BUY"
    elif (vol + volat) >= 20:
        note = "volatility tradable"
        bias_pref = "BUY" if bias == "Bullish" else "SELL" if bias == "Bearish" else "HOLD"
    else:
        bias_pref = "HOLD"

    # aggregate score (keep 0..100)
    score = int(_clamp(trend + mom + vol + struct + volat, 0, 100))

    # entry/stop/target
    entry = float(last["Close"])
    atr = float(last["atr14"])
    rr = 2.0

    side = "HOLD"
    stop = None
    target = None
    if bias_pref == "BUY" and bias != "Bearish":
        side = "BUY"
        stop = round(entry - max(atr * 0.7, entry * 0.0015), 5)
        target = round(entry + rr * (entry - stop), 5)
    elif bias_pref == "SELL" and bias != "Bullish":
        side = "SELL"
        stop = round(entry + max(atr * 0.7, entry * 0.0015), 5)
        target = round(entry - rr * (stop - entry), 5)

    return {
        "side": side,
        "score": score,
        "bias": bias,
        "entry": entry if side != "HOLD" else None,
        "stop": stop,
        "target": target,
        "trend": int(trend),
        "mom": int(mom),
        "vol": int(vol),
        "struct": int(struct),
        "volat": int(volat),
        "note": note,
    }

if __name__ == "__main__":
    import pprint
    print("Smoke test:")
    pprint.pp(score_v2("EURUSD", "5min", 300))
