# BotA/tools/indicators_ext.py
# Single, stable API: analyze_indicators(df_or_rows, pair=None, tf=None) -> dict
# Returns a plain dict with keys used by runner_confluence & signal_card.

from __future__ import annotations

import math
from dataclasses import asdict, is_dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Union

import pandas as pd
import numpy as np


# ---------- helpers ----------

def _to_dataframe(data: Union[pd.DataFrame, Sequence[dict]]) -> pd.DataFrame:
    """
    Accept either a DataFrame or a list of OHLC dicts and return a clean
    DataFrame with columns: time, open, high, low, close
    Sorted oldest -> newest, time is timezone-naive UTC (pandas Timestamp).
    """
    if isinstance(data, pd.DataFrame):
        df = data.copy()
    else:
        # list/iterable of dicts
        df = pd.DataFrame(list(data or []))

    # normalize column names
    cols = {c.lower(): c for c in df.columns}
    def pick(*names):
        for n in names:
            if n in cols:
                return cols[n]
        return None

    col_time = pick("time", "timestamp", "date", "datetime")
    col_open = pick("open", "o")
    col_high = pick("high", "h")
    col_low  = pick("low",  "l")
    col_close= pick("close","c","price")

    need = [col_time, col_open, col_high, col_low, col_close]
    if any(x is None for x in need):
        raise ValueError("indicators_ext: missing OHLC columns in input")

    df = df[[col_time, col_open, col_high, col_low, col_close]].rename(
        columns={
            col_time:"time", col_open:"open", col_high:"high",
            col_low:"low", col_close:"close"
        }
    )

    # parse/convert
    df["time"] = pd.to_datetime(df["time"], utc=True).dt.tz_convert(None)
    for c in ["open","high","low","close"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["open","high","low","close"]).sort_values("time").reset_index(drop=True)
    return df


def _ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def _adx(df: pd.DataFrame, window: int = 14) -> pd.Series:
    """
    Wilder's ADX using high/low/close.
    Returns ADX series (same length, with NaN at start).
    """
    high, low, close = df["high"], df["low"], df["close"]
    up_move   = high.diff()
    down_move = -low.diff()

    plus_dm  = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

    tr1 = (high - low).abs()
    tr2 = (high - close.shift()).abs()
    tr3 = (low  - close.shift()).abs()
    tr  = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    atr = tr.ewm(alpha=1/window, adjust=False).mean()

    plus_di  = 100 * pd.Series(plus_dm).ewm(alpha=1/window, adjust=False).mean() / atr
    minus_di = 100 * pd.Series(minus_dm).ewm(alpha=1/window, adjust=False).mean() / atr

    dx  = ( (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan) ) * 100
    adx = dx.ewm(alpha=1/window, adjust=False).mean()
    adx.index = df.index
    return adx


def _near_fib(close: float, lo: float, hi: float) -> Tuple[bool, Optional[float]]:
    """
    Check if `close` is near a standard Fibonacci level of the swing [lo,hi].
    Tolerance ~ 0.0008 (≈8 pips on EURUSD), scaled to price magnitude.
    Returns (is_near, level_price).
    """
    if not np.isfinite(close) or not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
        return (False, None)

    levels = [0.236, 0.382, 0.5, 0.618, 0.786]
    tol = max(0.00008 * max(1.0, close), 1e-6)  # ~8 pips for ~1.0 price
    near_any = False
    nearest = None
    for r in levels:
        lvl = lo + (hi - lo) * r
        if abs(close - lvl) <= tol:
            near_any = True
            nearest = lvl
            break
    return (near_any, nearest)


# ---------- main API ----------

def analyze_indicators(data: Union[pd.DataFrame, Sequence[dict]],
                       pair: Optional[str] = None,
                       tf: Optional[str] = None) -> Dict[str, Any]:
    """
    ALWAYS returns a plain dict.
    Keys provided:
      - action: 'BUY' | 'SELL' | 'WAIT'
      - trend_score: int (0..16)
      - momentum_score: int (0..16)   # kept for compatibility, runner only reads totals
      - total_score: int (0..16)      # main /16 score used by the card
      - filters_score: int (0..6)     # +/6 part
      - reason: str
      - risk: str
      - spread: Optional[float]       # leave None; card may compute fallback
    """
    df = _to_dataframe(data)
    if len(df) < 40:
        # not enough bars – return WAIT but keep shape
        return {
            "action": "WAIT",
            "trend_score": 0,
            "momentum_score": 0,
            "total_score": 0,
            "filters_score": 0,
            "reason": "insufficient data",
            "risk": "normal",
            "spread": None,
        }

    close = df["close"]
    ema_fast = _ema(close, 12)
    ema_slow = _ema(close, 26)
    macd = ema_fast - ema_slow
    macd_signal = _ema(macd, 9)
    macd_hist = macd - macd_signal

    ema50 = _ema(close, 50)
    # slope: compare last vs 3 bars ago
    slope_up = (ema50.iloc[-1] > ema50.iloc[-4]) if len(ema50) >= 4 else False
    slope_down = (ema50.iloc[-1] < ema50.iloc[-4]) if len(ema50) >= 4 else False

    adx = _adx(df, 14)
    adx_last = float(adx.iloc[-1]) if np.isfinite(adx.iloc[-1]) else 0.0
    has_trend = adx_last >= 18.0  # mild threshold ~ 18–20

    mom_up = float(macd_hist.iloc[-1]) > 0
    mom_down = float(macd_hist.iloc[-1]) < 0

    # simple swing for fib check (use last ~120 bars or entire set if smaller)
    wnd = min(len(df), 120)
    recent = df.iloc[-wnd:]
    lo, hi = float(recent["low"].min()), float(recent["high"].max())
    near_fib, fib_level = _near_fib(float(close.iloc[-1]), lo, hi)

    # Compose reason string
    reasons = []
    reasons.append("ADX trend present" if has_trend else "Weak trend")
    reasons.append("MACD momentum up" if mom_up else "MACD momentum down" if mom_down else "MACD flat")
    if slope_up:
        reasons.append("EMA50 slope up")
    elif slope_down:
        reasons.append("EMA50 slope down")
    else:
        reasons.append("EMA50 flat")
    if near_fib:
        reasons.append("Near Fibonacci level")
    reasons.append("No nearby S/R clutter")  # placeholder – conservative friendly text

    # Scores (deterministic, simple)
    score_trend = 8 if has_trend else 0
    score_mom   = 4 if mom_up or mom_down else 0
    score_ema   = 4 if slope_up or slope_down else 0
    total16     = min(16, score_trend + score_mom + score_ema)

    filters6 = 0
    if near_fib:
        filters6 += 3
    # assume no clutter gives the remaining 3
    filters6 += 3

    # Action decision
    if has_trend and slope_up and mom_up:
        action = "BUY"
    elif has_trend and slope_down and mom_down:
        action = "SELL"
    else:
        action = "WAIT"

    return {
        "action": action,
        "trend_score": score_trend,
        "momentum_score": score_mom,
        "total_score": total16,
        "filters_score": filters6,
        "reason": " + ".join(reasons),
        "risk": "normal",
        "spread": None,  # let the card compute fallback from df, if it supports it
    }
