# tools/tp_sl.py
from __future__ import annotations
import numpy as np
import pandas as pd

def atr(df: pd.DataFrame, period: int = 14) -> float:
    """Compute ATR(period) from an OHLC DataFrame with columns: open, high, low, close."""
    if not {"open","high","low","close"}.issubset(df.columns):
        raise ValueError("ATR needs columns: open, high, low, close")
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = pd.concat([
        (high - low).abs(),
        (high - prev_close).abs(),
        (low  - prev_close).abs()
    ], axis=1).max(axis=1)
    atr_series = tr.rolling(period, min_periods=period).mean()
    val = float(atr_series.iloc[-1])
    if not np.isfinite(val) or val <= 0:
        raise ValueError("ATR invalid")
    return val

def derive_tp_sl(side: str, entry: float, df_4h: pd.DataFrame,
                 atr_mult: float = 1.2, rr: float = 1.5) -> tuple[float, float]:
    """
    Returns (tp, sl) based on ATR from 4h data.
    side: 'BUY' or 'SELL'
    """
    a = atr(df_4h, 14) * atr_mult
    if side.upper() == "BUY":
        sl = entry - a
        tp = entry + (entry - sl) * rr
    else:
        sl = entry + a
        tp = entry - (sl - entry) * rr
    # round to 1e-5 typical for FX 5-decimals
    r = lambda x: float(np.round(x, 5))
    return (r(tp), r(sl))
