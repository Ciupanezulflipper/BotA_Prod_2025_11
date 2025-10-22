# -*- coding: utf-8 -*-
"""
Lightweight signal engine v2b
- fetches OHLCV via data.providers.fetch_ohlcv_safe()
- computes a 0..100 score with 5 sub-scores
- returns a dict consumable by the bot
"""
from __future__ import annotations
import logging, math
from datetime import datetime, timezone
import numpy as np
import pandas as pd

from data import providers  # must expose fetch_ohlcv_safe, fetch_price

log = logging.getLogger("engine_v2b")

# ---------- helpers ----------
def _ema(s: pd.Series, n: int) -> pd.Series:
    if s is None or len(s) == 0: return s
    return s.ewm(span=n, adjust=False).mean()

def _rsi(s: pd.Series, n: int = 14) -> pd.Series:
    if s is None or len(s) < n + 1: return pd.Series(dtype=float)
    delta = s.diff()
    up = delta.clip(lower=0.0)
    dn = (-delta).clip(lower=0.0)
    rs = up.ewm(alpha=1/n, adjust=False).mean() / dn.ewm(alpha=1/n, adjust=False).mean()
    rsi = 100 - (100 / (1 + rs))
    return rsi

def _atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    if df is None or len(df) < n + 1: return pd.Series(dtype=float)
    high, low, close = df["High"], df["Low"], df["Close"]
    prev_close = close.shift(1)
    tr = pd.concat([
        (high - low),
        (high - prev_close).abs(),
        (low - prev_close).abs()
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1/n, adjust=False).mean()

def _pct(x: float, y: float) -> float:
    try:
        return 0.0 if y == 0 or y is None else 100.0 * (x / y)
    except Exception:
        return 0.0

def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v if v is not None and not math.isnan(v) else 0.0))

def _last(series: pd.Series, default: float | None = None) -> float | None:
    try:
        return None if series is None or series.empty else float(series.iloc[-1])
    except Exception:
        return default

def _swing_score(close: pd.Series, lookback: int = 30) -> int:
    """Very light structure proxy: distance to local extremes."""
    if close is None or len(close) < lookback + 5: return 0
    window = close.tail(lookback)
    hi, lo, px = float(window.max()), float(window.min()), float(window.iloc[-1])
    span = max(1e-9, hi - lo)
    # closer to edges -> more "structure" (levels)
    edge_prox = max((px - lo), (hi - px)) / span
    return int(_clamp(edge_prox * 20, 0, 20))

# ---------- core ----------
def score_symbol(symbol: str, tf: str = "5min", limit: int = 300) -> dict:
    """
    Returns a dict:
      score, trend, mom, vol, struct, volat, bias, note
    All ints except bias/note. Robust to None data.
    """
    try:
        df = providers.fetch_ohlcv_safe(symbol, tf=tf, limit=limit)
    except Exception as e:
        log.warning("fetch_ohlcv_safe raised for %s: %s", symbol, e)
        df = None

    if df is None or len(df) < 50 or any(c not in df.columns for c in ["Open","High","Low","Close"]):
        return {
            "score": 0,
            "trend": 0,
            "mom": 0,
            "vol": 0,
            "struct": 0,
            "volat": 0,
            "bias": "Neutral",
            "note": "no data"
        }

    df = df.copy()
    close = df["Close"].astype(float)

    # Trend: alignment of EMA50 / EMA200 and price location
    ema50 = _ema(close, 50)
    ema200 = _ema(close, 200)
    above50 = int(_last(close > ema50, 0))
    above200 = int(_last(close > ema200, 0))
    trend_base = (above50 + above200) * 5  # 0/5/10
    slope50 = _last(ema50.diff().tail(10).mean(), 0.0) or 0.0
    slope200 = _last(ema200.diff().tail(10).mean(), 0.0) or 0.0
    slope_boost = _clamp((abs(slope50) + abs(slope200)) * 1e4, 0, 10)
    trend = int(_clamp(trend_base + slope_boost, 0, 20))

    # Momentum: RSI(14) distance from 50
    rsi = _rsi(close, 14)
    rsi_last = _last(rsi, 50.0) or 50.0
    mom = int(_clamp(abs(rsi_last - 50.0) / 50.0 * 20.0, 0, 20))

    # Volatility (stat): rolling stdev of returns scaled
    ret = close.pct_change().tail(60)
    vol = int(_clamp(ret.std() * 1000.0, 0, 20))  # ~0..20

    # Structure proxy
    struct = int(_clamp(_swing_score(close, 40), 0, 20))

    # Volatility (ATR%): ATR14 as percent of price
    atr = _atr(df, 14)
    atrp = _pct(_last(atr, 0.0), max(1e-9, _last(close, 0.0)))
    volat = int(_clamp(atrp, 0, 20))

    # Bias
    if above50 and above200 and rsi_last >= 52:
        bias = "Bullish"
    elif (not above50) and (not above200) and rsi_last <= 48:
        bias = "Bearish"
    else:
        bias = "Neutral"

    # Note (tiny heuristic)
    note = (
        "trend momentum present, clean structure" if (trend >= 12 and mom >= 6 and struct >= 8)
        else "volatility tradable" if (vol + volat) >= 20
        else "-"
    )

    score = int(_clamp(trend + mom + vol + struct + volat, 0, 100))

    return {
        "score": score,
        "trend": int(trend or 0),
        "mom": int(mom or 0),
        "vol": int(vol or 0),
        "struct": int(struct or 0),
        "volat": int(volat or 0),
        "bias": bias,
        "note": note or ""
    }
