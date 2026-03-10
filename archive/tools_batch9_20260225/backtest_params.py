#!/usr/bin/env python3
"""
Backtest EURUSD M15 with real indicators (RSI14, ADX14, MACD 12-26-9)
Counts BUY/SELL signals under multiple parameter sets and shows blockers.
Reads: eurusd_m15.csv  (columns: timestamp,open,high,low,close,volume)
"""

import pandas as pd
import numpy as np

CSV = "eurusd_m15.csv"

# --------------------- Indicator utils ---------------------
def ema(series, span):
    return series.ewm(span=span, adjust=False).mean()

def rsi_wilder(close, period=14):
    delta = close.diff()
    gain = (delta.clip(lower=0)).abs()
    loss = (-delta.clip(upper=0)).abs()
    avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)

def true_range(high, low, close):
    prev_close = close.shift(1)
    a = (high - low).abs()
    b = (high - prev_close).abs()
    c = (low  - prev_close).abs()
    tr = pd.concat([a, b, c], axis=1).max(axis=1)
    return tr

def adx(high, low, close, period=14):
    # +DM / -DM
    up = high.diff()
    dn = -low.diff()
    plus_dm  = np.where((up > dn) & (up > 0),  up, 0.0)
    minus_dm = np.where((dn > up) & (dn > 0), dn, 0.0)

    tr = true_range(high, low, close)
    atr = tr.ewm(alpha=1/period, adjust=False).mean()

    pdi = 100 * pd.Series(plus_dm, index=high.index).ewm(alpha=1/period, adjust=False).mean() / atr
    mdi = 100 * pd.Series(minus_dm, index=high.index).ewm(alpha=1/period, adjust=False).mean() / atr

    dx = ( (pdi - mdi).abs() / (pdi + mdi).replace(0, np.nan) ) * 100
    adx_val = dx.ewm(alpha=1/period, adjust=False).mean().fillna(0)
    return adx_val

def macd_hist(close, fast=12, slow=26, signal=9):
    macd_line = ema(close, fast) - ema(close, slow)
    signal_line = ema(macd_line, signal)
    hist = macd_line - signal_line
    return hist

# --------------------- Load & prep ---------------------
df = pd.read_csv(CSV)
for col in ["open","high","low","close","volume"]:
    df[col] = pd.to_numeric(df[col], errors="coerce")
df = df.dropna(subset=["open","high","low","close"]).reset_index(drop=True)

# Indicators
df["rsi"]    = rsi_wilder(df["close"], 14)
df["adx"]    = adx(df["high"], df["low"], df["close"], 14)
df["macd_h"] = macd_hist(df["close"], 12, 26, 9)

# --------------------- Configs ---------------------
CONFIGS = {
    "Current":       dict(ADX_MIN=18, RSI_BUY=65, RSI_SELL=35, MACD_MIN=0.00010, CONF_MIN=1.5),
    "Institutional": dict(ADX_MIN=14, RSI_BUY=62, RSI_SELL=38, MACD_MIN=0.000035, CONF_MIN=0.8),
    "Aggressive":    dict(ADX_MIN=12, RSI_BUY=60, RSI_SELL=40, MACD_MIN=0.000030, CONF_MIN=0.5),
}

# scoring same idea as runner: sum of passes (RSI extreme + MACD pass + ADX pass)
def score_row(row, cfg):
    s = 0.0
    if row["adx"] >= cfg["ADX_MIN"]:
        s += 0.5
    if abs(row["macd_h"]) >= cfg["MACD_MIN"]:
        s += 0.5
    if row["rsi"] >= cfg["RSI_BUY"] or row["rsi"] <= cfg["RSI_SELL"]:
        s += 0.5
    return s

def backtest(cfg_name, cfg, tail_n=None):
    data = df if tail_n is None else df.tail(tail_n).copy()

    # blockers
    b_adx = b_rsi = b_macd = 0
    signals = []
    for i, row in data.iterrows():
        pass_adx  = row["adx"]    >= cfg["ADX_MIN"]
        pass_macd = abs(row["macd_h"]) >= cfg["MACD_MIN"]
        pass_rsiB = row["rsi"] >= cfg["RSI_BUY"]
        pass_rsiS = row["rsi"] <= cfg["RSI_SELL"]
        conf = 0.0
        conf += 0.5 if pass_adx else 0.0
        conf += 0.5 if pass_macd else 0.0
        conf += 0.5 if (pass_rsiB or pass_rsiS) else 0.0

        if not pass_adx:  b_adx  += 1
        if not (pass_rsiB or pass_rsiS): b_rsi += 1
        if not pass_macd: b_macd += 1

        direction = None
        if (pass_adx and pass_macd and pass_rsiB):
            direction = "BUY"
        elif (pass_adx and pass_macd and pass_rsiS):
            direction = "SELL"

        if direction and conf >= cfg["CONF_MIN"]:
            signals.append((row.get("timestamp", i), row["close"], row["rsi"], row["adx"], row["macd_h"], conf, direction))

    print(f"\n=== {cfg_name} ===")
    print(f"Params: ADX_MIN={cfg['ADX_MIN']}  RSI_BUY={cfg['RSI_BUY']}  RSI_SELL={cfg['RSI_SELL']}  MACD_MIN={cfg['MACD_MIN']}  CONF_MIN={cfg['CONF_MIN']}")
    print(f"Rows tested: {len(data)}")
    print(f"Signals: {len(signals)}")
    if signals:
        print("Sample last 5 signals:")
        for s in signals[-5:]:
            ts, close, rsi, adx_v, m_h, conf, d = s
            print(f"  {ts} | close {close:.5f} | RSI {rsi:.1f} | ADX {adx_v:.1f} | MACD_H {m_h:.6f} | score {conf:.2f} | {d}")

    # blocker stats (how many rows failed each gate; rows can fail multiple gates)
    print("Blockers (count over all rows):")
    print(f"  ADX weak : {b_adx}")
    print(f"  RSI mid  : {b_rsi}")
    print(f"  MACD small: {b_macd}")

def main():
    # Full 500-row backtest
    for name, cfg in CONFIGS.items():
        backtest(name, cfg, tail_n=None)

    # Also show last 50 rows for the most relevant comparison
    print("\n--- Last 50-candle window ---")
    for name, cfg in CONFIGS.items():
        backtest(name + " (last50)", cfg, tail_n=50)

if __name__ == "__main__":
    main()
