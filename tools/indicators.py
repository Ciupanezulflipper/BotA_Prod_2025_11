#!/usr/bin/env python3
from typing import List, Tuple

def ema(values: List[float], period: int) -> List[float]:
    if period <= 0 or not values:
        return []
    k = 2.0 / (period + 1.0)
    out: List[float] = []
    ema_val = values[0]
    out.append(ema_val)
    for v in values[1:]:
        ema_val = (v - ema_val) * k + ema_val
        out.append(ema_val)
    return out

def rsi(values: List[float], period: int = 14) -> List[float]:
    if period <= 0 or len(values) < period + 1:
        return [50.0] * len(values)
    gains: List[float] = [0.0]
    losses: List[float] = [0.0]
    for i in range(1, len(values)):
        ch = values[i] - values[i-1]
        gains.append(max(ch, 0.0))
        losses.append(max(-ch, 0.0))
    # first avg
    avg_gain = sum(gains[1:period+1]) / period
    avg_loss = sum(losses[1:period+1]) / period
    rsis = [50.0] * len(values)
    if avg_loss == 0:
        rsis[period] = 100.0
    else:
        rsis[period] = 100.0 - (100.0 / (1.0 + (avg_gain / avg_loss)))
    # subsequent
    for i in range(period+1, len(values)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        if avg_loss == 0:
            rsis[i] = 100.0
        else:
            rsis[i] = 100.0 - (100.0 / (1.0 + (avg_gain / avg_loss)))
    return rsis

def last_non_none(seq):
    for v in reversed(seq):
        if v is not None:
            return v
    return None
