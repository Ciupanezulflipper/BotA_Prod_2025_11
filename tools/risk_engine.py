from __future__ import annotations
import os
import math
from dataclasses import dataclass
from typing import Optional, Tuple, List, Dict

@dataclass
class RiskConfig:
    risk_suggest: bool
    balance: float
    risk_pct: float
    sl_atr_mult: float
    rr: float
    lot_base: int
    min_lot: float
    lot_step: float

    @classmethod
    def from_env(cls) -> "RiskConfig":
        def f(key, default, cast=float):
            v = os.getenv(key)
            return cast(v) if v not in (None, "") else default

        return cls(
            risk_suggest = os.getenv("RISK_SUGGEST", "0") == "1",
            balance      = f("ACCOUNT_BALANCE", 0.0),
            risk_pct     = f("RISK_PCT", 0.0),
            sl_atr_mult  = f("SL_ATR_MULT", 1.5),
            rr           = f("RR", 2.0),
            lot_base     = int(f("LOT_SIZE_BASE", 100000, int)),
            min_lot      = f("MIN_LOT", 0.01),
            lot_step     = f("LOT_STEP", 0.01),
        )

def _true_range(prev_close: float, high: float, low: float) -> float:
    return max(high - low, abs(high - prev_close), abs(low - prev_close))

def atr(ohlc: List[Dict], period: int = 14) -> Optional[float]:
    if not ohlc or len(ohlc) < period + 1:
        return None
    trs: List[float] = []
    for i in range(1, period + 1):
        prev = ohlc[-(i+1)]
        cur  = ohlc[-i]
        tr = _true_range(prev["close"], cur["high"], cur["low"])
        trs.append(tr)
    return sum(trs) / period if trs else None

def _round_step(value: float, step: float) -> float:
    if step <= 0: 
        return value
    return math.floor(value / step + 1e-9) * step

def pip_value_per_lot(pair: str) -> float:
    # EURUSD assumption: ~$10 per pip per 1.0 lot
    return 10.0

def price_to_pips(pair: str, price_distance: float) -> float:
    # EURUSD pip size = 0.0001
    return price_distance / 0.0001

def suggest_sl_tp_and_size(
    pair: str,
    direction: str,  # "BUY" or "SELL"
    last_close: float,
    ohlc: List[Dict],
    cfg: Optional[RiskConfig] = None,
) -> Optional[Dict]:
    """
    Returns dict:
      {"sl_price": float, "tp_price": float, "sl_pips": float, "tp_pips": float, "size_lots": Optional[float], "atr": float}
    or None if disabled / insufficient data.
    """
    cfg = cfg or RiskConfig.from_env()
    if not cfg.risk_suggest:
        return None

    a = atr(ohlc, period=14)
    if a is None or a <= 0:
        return None

    sl_dist = cfg.sl_atr_mult * a
    if direction.upper() == "BUY":
        sl_price = last_close - sl_dist
        tp_price = last_close + cfg.rr * sl_dist
    else:
        sl_price = last_close + sl_dist
        tp_price = last_close - cfg.rr * sl_dist

    sl_pips = price_to_pips(pair, abs(last_close - sl_price))
    tp_pips = price_to_pips(pair, abs(tp_price - last_close))

    size_lots = None
    if cfg.balance > 0 and cfg.risk_pct > 0 and sl_pips > 0:
        dollar_risk = cfg.balance * (cfg.risk_pct / 100.0)
        per_lot_loss = sl_pips * pip_value_per_lot(pair)  # $ per 1.0 lot at SL
        raw_lots = dollar_risk / per_lot_loss if per_lot_loss > 0 else 0.0
        lots = max(cfg.min_lot, _round_step(raw_lots, cfg.lot_step))
        size_lots = round(lots, 2)

    return {
        "sl_price": round(sl_price, 5),
        "tp_price": round(tp_price, 5),
        "sl_pips": round(sl_pips, 1),
        "tp_pips": round(tp_pips, 1),
        "size_lots": size_lots,
        "atr": round(a, 5),
    }
