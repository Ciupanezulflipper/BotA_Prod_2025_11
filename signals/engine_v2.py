# Confluence scorer v2 (100-pt): trend, momentum, volume, structure, strength, volatility

from typing import Dict, List, Optional
from data.ohlcv import fetch
from data.indicators_more import vwap, adx, stoch_rsi, obv, mfi, psar, volume_spike
from data.structure import volume_profile, swing_levels

def _cl(c): return [x["c"] for x in c]
def _hi(c): return [x["h"] for x in c]
def _lo(c): return [x["l"] for x in c]
def _vo(c): return [x.get("v",0.0) for x in c]

def score_symbol(symbol: str, tf: str = "5min", limit: int = 300) -> Dict:
    candles = fetch(symbol, tf=tf, limit=limit)
    if not candles: 
        return {"ok": False, "why":"NO_DATA"}
    close = _cl(candles)

    # --- Trend (25) ---
    vw = vwap(candles, period=20)
    adxv, pdi, mdi = adx(candles, candles, close, period=14)
    trend_pts = 0
    if close[-1] > (vw[-1] or close[-1]): trend_pts += 10
    if adxv[-1] and adxv[-1] > 25 and (pdi[-1] or 0) > (mdi[-1] or 0): trend_pts += 8
    if (close[-1] - close[-20]) > 0: trend_pts += 7
    trend_pts = min(25, max(-25, trend_pts))

    # --- Momentum (20) ---
    k,d = stoch_rsi(close, period=14, k=3, d=3)
    mom = 0
    if k[-1] and d[-1]:
        if k[-1] < 20 and k[-1] > d[-1]: mom += 8
        if 30 <= k[-1] <= 60: mom += 6
    # simple MACD-like proxy: slope
    mom += 6 if (close[-1]-close[-5]) > 0 and (close[-5]-close[-10]) > 0 else 0
    mom = min(20, max(-20, mom))

    # --- Volume (20) ---
    ratio, spike = volume_spike(_vo(candles), lookback=50, threshold=1.5)
    ob = obv(close, _vo(candles))
    vol_pts = 0
    if spike: vol_pts += 8
    if len(ob) > 5 and ob[-1] > ob[-5]: vol_pts += 6
    mfi_v = mfi(candles, candles, candles, candles)
    if mfi_v[-1] and mfi_v[-1] < 30: vol_pts += 6
    vol_pts = min(20, max(-20, vol_pts))

    # --- Structure (15) ---
    vp = volume_profile(candles, bins=40)
    struct = 0
    if vp["poc"] and abs(close[-1]-vp["poc"]) <= (abs(close[-1])*0.0005): struct += 8
    sh, sl = swing_levels(candles, lookback=5)
    if sl and close[-1] >= max(sl): struct += 7  # bounce / reclaim
    struct = min(15, max(-15, struct))

    # --- Strength (10) ---
    stren = 0
    if adxv[-1] and adxv[-1] > 25: stren += 5
    ps, dr = psar(candles, candles)
    if dr[-1] == 1: stren += 5
    stren = min(10, max(-10, stren))

    # --- Volatility (10) ---
    # lightweight ATR proxy: recent range
    rng = (max(_hi(candles[-14:])) - min(_lo(candles[-14:]))) / (abs(close[-1]) or 1.0)
    vola = 0
    if 0.002 <= rng <= 0.02: vola += 10
    elif rng < 0.002: vola += 5
    else: vola += 3  # too hot
    vola = min(10, max(0, vola))

    score = trend_pts + mom + vol_pts + struct + stren + vola

    # class
    if score >= 75: cls, risk = "STRONG", 1.5
    elif score >= 60: cls, risk = "MODERATE", 1.0
    elif score >= 45: cls, risk = "WEAK", 0.5
    else: cls, risk = "HOLD", 0.0

    return {
        "ok": True, "symbol": symbol, "tf": tf, "score": score,
        "class": cls, "risk_pct": risk,
        "components": {
            "trend": trend_pts, "momentum": mom, "volume": vol_pts,
            "structure": struct, "strength": stren, "volatility": vola
        },
        "note": "engine_v2 demo"
    }
