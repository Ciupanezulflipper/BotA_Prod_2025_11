# engine_v1.py — Trend + Momentum scoring (0–100 demo)
# Uses your data/ohlcv.fetch and data/indicators helpers

from typing import List, Dict, Any
from data.ohlcv import fetch
from data.indicators import ema, rsi, macd, stoch_rsi

def _last(vals: List[float], n: int = 1) -> float:
    return float(vals[-n])

def score_symbol_v1(symbol: str = "EURUSD", tf: str = "5min", limit: int = 300) -> Dict[str, Any]:
    # 1) data
    candles = fetch(symbol, tf=tf, limit=limit)
    if not candles or len(candles) < 50:
        return {"ok": False, "reason": "NO_DATA", "text": f"📉 {symbol} score = N/A (no data)"}

    close = [c["c"] for c in candles]
    high  = [c["h"] for c in candles]
    low   = [c["l"] for c in candles]

    # 2) indicators
    ema9  = ema(close, 9)
    ema21 = ema(close, 21)

    rsi14 = rsi(close, 14)
    macd_line, signal_line, hist = macd(close, 5, 13, 9)
    k, d = stoch_rsi(close, period=14, k=3, d=3)

    # 3) Trend score (25 pts)
    trend_pts = 0
    px = close[-1]
    e9 = _last(ema9); e21 = _last(ema21)

    # emulate VWAP bias via ema stack for now (placeholder)
    if px > e9 > e21:
        trend_pts = 25
        trend_note = "Perfect bull alignment"
    elif px > e9 and px > e21:
        trend_pts = 15
        trend_note = "Moderate bull bias"
    elif px < e9 < e21:
        trend_pts = -25
        trend_note = "Perfect bear alignment"
    elif px < e9 and px < e21:
        trend_pts = -15
        trend_note = "Moderate bear bias"
    else:
        trend_pts = 10
        trend_note = "Neutral / test"

    # 4) Momentum (20 pts): MACD + RSI + StochRSI
    mom_pts = 0
    macd_ok = macd_line[-1] > signal_line[-1] and hist[-1] > hist[-2]
    rsi_ok  = (rsi14[-1] < 30 and rsi14[-2] <= rsi14[-1]) or (30 <= rsi14[-1] <= 50 and rsi14[-1] > rsi14[-2])
    stoch_ok = k[-1] > d[-1] and min(k[-1], d[-1]) < 20

    if macd_ok:  mom_pts += 8
    if rsi_ok:   mom_pts += 6
    if stoch_ok: mom_pts += 6

    # 5) Sum (only first two categories now; others later)
    raw = 25 + 20  # max for implemented blocks
    got = max(0, trend_pts) + mom_pts
    # scale into 0..100 so UI is consistent
    score = round(100.0 * got / raw, 0)

    # Direction suggestion
    direction = "BUY" if (trend_pts >= 0 and mom_pts >= 12) else ("SELL" if (trend_pts < 0 and mom_pts >= 12) else "HOLD")

    notes = []
    notes.append(f"trend: {trend_note}")
    notes.append(f"mom: macd={'✓' if macd_ok else '✗'}, rsi={'✓' if rsi_ok else '✗'}, stoch={'✓' if stoch_ok else '✗'}")

    text = (
        f"📊 {symbol} score (v1) = {int(score)}/100\n"
        f"🧭 direction: {direction}\n"
        f"📝 " + " | ".join(notes)
    )

    return {
        "ok": True,
        "symbol": symbol,
        "tf": tf,
        "score": score,
        "direction": direction,
        "notes": notes,
        "text": text,
    }
