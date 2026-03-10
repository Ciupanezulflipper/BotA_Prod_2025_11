from __future__ import annotations
from typing import Tuple
import numpy as np

def compute_atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> float:
    if min(len(high), len(low), len(close)) < period + 1:
        return 0.0
    tr = np.maximum(high[1:] - low[1:], np.maximum(abs(high[1:] - close[:-1]), abs(low[1:] - close[:-1])))
    atr = np.zeros_like(close)
    atr[period] = np.mean(tr[:period])
    for i in range(period+1, len(close)):
        atr[i] = (atr[i-1]*(period-1) + tr[i-1]) / period
    return float(atr[-1])

def rr_gate(direction: int, price: float, high: np.ndarray, low: np.ndarray, close: np.ndarray,
            rr_min: float = 1.5, atr_mult: float = 1.5) -> Tuple[bool, float, float, float]:
    """
    Returns (ok, rr, sl, tp).
    SL = ATR * atr_mult (away from price in the adverse direction)
    TP = price +/- rr*SL accordingly
    """
    atr = compute_atr(high, low, close, period=14)
    if atr <= 0:
        return False, 0.0, 0.0, 0.0
    sl = atr * atr_mult
    if direction > 0:
        rr = (sl * rr_min) / sl
        tp = price + rr_min * sl
        sl_price = price - sl
    elif direction < 0:
        tp = price - rr_min * sl
        sl_price = price + sl
        rr = (sl * rr_min) / sl
    else:
        return False, 0.0, 0.0, 0.0
    return True, rr, float(sl_price), float(tp)
