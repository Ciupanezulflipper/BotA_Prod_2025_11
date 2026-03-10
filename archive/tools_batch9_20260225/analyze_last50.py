#!/usr/bin/env python3
"""
Analyze the last 50 EURUSD M15 candles from eurusd_m15.csv,
compute RSI(14), MACD(12,26,9), ADX(14), and show exactly why
our runner did (or did not) allow a signal for each candle.

No external libs beyond pandas/numpy.
"""

import os, sys, math
import pandas as pd
import numpy as np
from datetime import datetime, timezone

CSV_FILE = os.getenv("CSV_FILE", "eurusd_m15.csv")

# --- same gates your runner uses (adjust here if your runner differs)
CONF_MIN   = float(os.getenv("CONF_MIN", "1.50"))     # combined score minimum
ADX_MIN    = float(os.getenv("ADX_MIN",  "18"))       # minimum ADX for "trend strong"
RSI_BUY    = float(os.getenv("RSI_BUY",  "65"))       # RSI >= this contributes bullish
RSI_SELL   = float(os.getenv("RSI_SELL", "35"))       # RSI <= this contributes bearish
MACD_MIN   = float(os.getenv("MACD_MIN", "0.00010"))  # minimal |MACD hist| to count
# ---------------------------------------------------------------

def rsi14(series, period=14):
    delta = series.diff()
    up = np.where(delta > 0, delta, 0.0)
    dn = np.where(delta < 0, -delta, 0.0)
    up_ema = pd.Series(up).ewm(alpha=1/period, adjust=False).mean()
    dn_ema = pd.Series(dn).ewm(alpha=1/period, adjust=False).mean()
    rs = up_ema / (dn_ema + 1e-12)
    return 100 - (100 / (1 + rs))

def ema(x, n):
    return x.ewm(alpha=2/(n+1), adjust=False).mean()

def macd_hist(close, fast=12, slow=26, signal=9):
    macd = ema(close, fast) - ema(close, slow)
    sig  = ema(macd, signal)
    hist = macd - sig
    return macd, sig, hist

def true_range(h, l, c_prev):
    return np.maximum.reduce([
        h - l,
        (h - c_prev).abs(),
        (l - c_prev).abs()
    ])

def adx14(high, low, close, period=14):
    # Wilder’s ADX
    up_move   = high.diff()
    down_move = -low.diff()

    plus_dm  = np.where((up_move > down_move) & (up_move > 0),  up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

    tr = true_range(high, low, close.shift(1))
    tr_smooth = pd.Series(tr).rolling(window=period, min_periods=period).sum()
    tr_smooth = tr_smooth.combine_first(pd.Series(tr).ewm(alpha=1/period, adjust=False).mean())

    plus_di  = 100 * pd.Series(plus_dm).rolling(period).sum()  / (tr_smooth + 1e-12)
    minus_di = 100 * pd.Series(minus_dm).rolling(period).sum() / (tr_smooth + 1e-12)

    dx = 100 * (plus_di - minus_di).abs() / ((plus_di + minus_di) + 1e-12)
    adx = dx.rolling(period).mean()
    return plus_di, minus_di, adx

def score_row(rsi, adx, macd_h):
    score = 0.0
    notes = []

    # RSI contribution
    if rsi >= RSI_BUY:
        score += 0.5; notes.append("RSI≥BUY")
    elif rsi <= RSI_SELL:
        score += 0.5; notes.append("RSI≤SELL")
    else:
        notes.append("RSI mid")

    # ADX contribution
    if adx >= ADX_MIN:
        score += 0.7; notes.append("ADX strong")
    else:
        notes.append("ADX weak")

    # MACD histogram contribution
    if abs(macd_h) >= MACD_MIN:
        # give directional nudge
        if macd_h > 0:
            score += 0.3; notes.append("MACD↑")
        else:
            score += 0.3; notes.append("MACD↓")
    else:
        notes.append("ΔMACD small")

    # direction
    direction = "FLAT"
    if (rsi >= RSI_BUY and macd_h > 0) and adx >= ADX_MIN:
        direction = "BUY"
    elif (rsi <= RSI_SELL and macd_h < 0) and adx >= ADX_MIN:
        direction = "SELL"

    return round(score, 2), direction, notes

def main():
    if not os.path.exists(CSV_FILE):
        print(f"ERROR: {CSV_FILE} not found"); sys.exit(1)

    df = pd.read_csv(CSV_FILE)
    # standardize column names (your CSV is: timestamp,open,high,low,close,volume)
    cols = {c.lower(): c for c in df.columns}
    need = ["timestamp","open","high","low","close"]
    for n in need:
        if n not in [c.lower() for c in df.columns]:
            print("ERROR: CSV missing columns", df.columns); sys.exit(2)

    df["ts"] = pd.to_datetime(df[cols["timestamp"]], utc=True, errors="coerce")
    df = df.sort_values("ts").reset_index(drop=True)

    close = df[cols["close"]].astype(float)
    high  = df[cols["high"]].astype(float)
    low   = df[cols["low"]].astype(float)

    df["rsi"] = rsi14(close, 14)
    _, _, df["macd_h"] = macd_hist(close, 12, 26, 9)
    df["+di"], df["-di"], df["adx"] = adx14(high, low, close, 14)

    view = df.tail(50).copy()
    rows = []
    blockers = {"ADX weak":0, "RSI mid":0, "ΔMACD small":0, "Other":0}

    print("\n=== ANALYZE last 50 candles ===")
    for _, r in view.iterrows():
        score, direction, notes = score_row(r["rsi"], r["adx"], r["macd_h"])
        why = "; ".join(notes)
        # Count top blockers
        for key in ["ADX weak","RSI mid","ΔMACD small"]:
            if key in notes: blockers[key]+=1
        if all(k not in notes for k in ["ADX weak","RSI mid","ΔMACD small"]):
            blockers["Other"] += 1

        rows.append({
            "time": r["ts"].strftime("%Y-%m-%d %H:%M"),
            "close": round(float(r[cols["close"]]), 5),
            "rsi": round(float(r["rsi"]), 1),
            "adx": round(float(r["adx"]), 1) if not math.isnan(r["adx"]) else np.nan,
            "macd_h": round(float(r["macd_h"]), 6),
            "score": score,
            "dir": direction,
            "why": why
        })

    out = pd.DataFrame(rows)
    # show compact table
    with pd.option_context('display.max_rows', None, 'display.max_colwidth', 120):
        print(out.to_string(index=False))

    # summary
    last_ts = view.iloc[-1]["ts"]
    age_min = (datetime.now(timezone.utc) - last_ts).total_seconds()/60.0
    print("\n--- SUMMARY ---")
    print(f"Last candle: {last_ts} (age ~{age_min:.1f} min)")
    print(f"CONF_MIN={CONF_MIN}  ADX_MIN={ADX_MIN}  RSI_BUY={RSI_BUY}  RSI_SELL={RSI_SELL}  MACD_MIN={MACD_MIN}")
    print("Top blockers in last 50:")
    for k,v in blockers.items():
        print(f"  {k:12s}: {v}")

    # quick ‘would we have sent?’ check using current gates
    sendable = out[(out["dir"]!="FLAT") & (out["score"]>=CONF_MIN)]
    if sendable.empty:
        print("\nResult: No candle met direction≠FLAT *and* score≥CONF_MIN. That’s why no alert fired.")
    else:
        print("\nCandles that WOULD have sent under current gates:")
        with pd.option_context('display.max_rows', None):
            print(sendable[["time","close","rsi","adx","macd_h","score","dir"]].to_string(index=False))

if __name__ == "__main__":
    main()
