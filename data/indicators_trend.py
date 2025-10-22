# Lightweight EMA helpers (append-only)
from typing import List, Optional

def ema(values: List[float], period: int) -> List[Optional[float]]:
    if not values or period <= 0: return [None]*len(values)
    k = 2.0/(period+1)
    out=[None]*len(values)
    s=None
    for i,v in enumerate(values):
        if s is None:
            if i+1>=period:
                s = sum(values[i+1-period:i+1])/period
                out[i]=s
        else:
            s = v*k + s*(1-k)
            out[i]=s
    return out
