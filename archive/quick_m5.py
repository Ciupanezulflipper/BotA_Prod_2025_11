#!/usr/bin/env python3
"""
quick_m5.py — Return a quick M5 BUY/SELL/NEUTRAL using yfinance:
- EMA(9/21) cross + RSI(14) gates (>=55 buy, <=45 sell, else neutral)
- Prints: "M5 EURUSD BUY rsi=61.2 ema=9>21 t=2025-10-28 01:05Z"
- On ImportError/HTTP failure: prints "M5 EURUSD NEUTRAL ..." and exits 0 (never crash the caller)
"""
import sys, datetime as dt
def safe_print(s): 
    try: print(s)
    except: pass

try:
    import yfinance as yf
    import pandas as pd
    import numpy as np
except Exception:
    pair = sys.argv[1] if len(sys.argv) > 1 else "EURUSD"
    safe_print(f"M5 {pair} NEUTRAL rsi=? ema=? t=? (yfinance_missing)")
    sys.exit(0)

def rsi14(series):
    delta = series.diff()
    up = delta.clip(lower=0)
    down = -delta.clip(upper=0)
    roll_up = up.ewm(alpha=1/14, adjust=False).mean()
    roll_down = down.ewm(alpha=1/14, adjust=False).mean()
    rs = roll_up / (roll_down.replace(0, 1e-9))
    return 100 - (100/(1+rs))

def ema(series, n): 
    return series.ewm(span=n, adjust=False).mean()

def yf_symbol(pair):
    # Map FX pair to Yahoo format: "EURUSD=X", "GBPUSD=X", "XAUUSD=X"
    return f"{pair}=X"

def main():
    pair = (sys.argv[1] if len(sys.argv)>1 else "EURUSD").upper()
    try:
        sym = yf_symbol(pair)
        df = yf.download(sym, period="2d", interval="5m", progress=False, auto_adjust=False)
        if df is None or df.empty:
            safe_print(f"M5 {pair} NEUTRAL rsi=? ema=? t=? (no_data)")
            return
        close = df["Close"].dropna()
        if close.size < 30:
            safe_print(f"M5 {pair} NEUTRAL rsi=? ema=? t=? (insufficient)")
            return
        e9, e21 = ema(close, 9), ema(close, 21)
        rsi = rsi14(close).iloc[-1]
        e9v, e21v = e9.iloc[-1], e21.iloc[-1]
        t = df.index[-1].tz_convert("UTC").strftime("%Y-%m-%d %H:%MZ")
        signal = "NEUTRAL"
        if e9v > e21v and rsi >= 55: signal = "BUY"
        elif e9v < e21v and rsi <= 45: signal = "SELL"
        rel = "9>21" if e9v>e21v else ("9<21" if e9v<e21v else "9=21")
        safe_print(f"M5 {pair} {signal} rsi={rsi:.1f} ema={rel} t={t}")
    except Exception as e:
        safe_print(f"M5 {pair} NEUTRAL rsi=? ema=? t=? (err)")
        return

if __name__ == "__main__":
    main()
