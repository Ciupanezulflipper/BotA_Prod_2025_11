#!/usr/bin/env python3
import argparse, os, sys
from datetime import timezone
import pandas as pd

def get_ohlc_safe(pair, tf, bars):
    try:
        from BotA.tools.providers import get_ohlc
    except Exception as e:
        print(f"✗ Provider import failed: {e}")
        sys.exit(1)
    try:
        rows, source = get_ohlc(pair, tf, bars)
    except Exception as e:
        print(f"✗ Fetch failed: {e}")
        sys.exit(1)
    if not rows or len(rows) < 60:
        print(f"✗ Not enough data ({len(rows) if rows else 0}) from {source if 'source' in locals() else 'provider'}"); sys.exit(1)
    df = pd.DataFrame(rows)
    for c in ["open","high","low","close"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["time"] = pd.to_datetime(df["time"], utc=True, errors="coerce")
    df = df.dropna(subset=["time","close"]).sort_values("time").set_index("time")
    return df, source

def atr(df, period=14):
    h,l,c = df["high"], df["low"], df["close"]
    pc = c.shift(1)
    tr = pd.concat([(h-l).abs(), (h-pc).abs(), (l-pc).abs()], axis=1).max(axis=1)
    a = tr.rolling(window=period, min_periods=period).mean().dropna()
    if len(a) == 0:
        raise ValueError("ATR empty")
    return float(a.iloc[-1])

def pip_size(pair): 
    return 0.01 if pair.upper().endswith("JPY") else 0.0001

def main():
    ap = argparse.ArgumentParser(description="Append a backdated test signal to signals_v2.csv")
    ap.add_argument("--pair", default="EURUSD")
    ap.add_argument("--tf", default="M15")
    ap.add_argument("--action", choices=["BUY","SELL"], default="BUY")
    ap.add_argument("--outfile", default="signals_v2.csv")
    ap.add_argument("--back_bars", type=int, default=8)  # backdate by N bars so auditor has future data
    args = ap.parse_args()

    atr_period = int(os.getenv("ATR_PERIOD","14"))
    sl_mult   = float(os.getenv("ATR_SL_MULT","1.5"))
    tp1_mult  = float(os.getenv("ATR_TP1_MULT","1.5"))
    tp2_mult  = float(os.getenv("ATR_TP2_MULT","3.0"))

    df, source = get_ohlc_safe(args.pair, args.tf, 300)

    # Choose a bar 'back_bars' ago (ensure index exists)
    idx = -1 - max(args.back_bars, 0)
    if abs(idx) > len(df):
        print("✗ back_bars too large for available history"); sys.exit(1)

    price = float(df["close"].iloc[idx])
    sig_time = df.index[idx]

    # Compute ATR using history up to (and including) the signal bar
    hist = df.iloc[:idx+1] if idx < -1 else df
    atr_price = atr(hist, atr_period)

    if args.action == "BUY":
        sl  = price - sl_mult  * atr_price
        tp1 = price + tp1_mult * atr_price
        tp2 = price + tp2_mult * atr_price
        tp3 = price + (tp2_mult * 1.5) * atr_price
    else:
        sl  = price + sl_mult  * atr_price
        tp1 = price - tp1_mult * atr_price
        tp2 = price - tp2_mult * atr_price
        tp3 = price - (tp2_mult * 1.5) * atr_price

    pip = pip_size(args.pair)
    atr_pips = atr_price / pip

    row = {
        "timestamp": sig_time.isoformat(),
        "pair": args.pair.upper(),
        "timeframe": args.tf.upper(),
        "action": args.action,
        "entry_price": f"{price:.5f}",
        "stop_loss": f"{sl:.5f}",
        "tp1": f"{tp1:.5f}",
        "tp2": f"{tp2:.5f}",
        "tp3": f"{tp3:.5f}",
        "spread": "n/a",
        "atr": f"{atr_pips:.1f}",
        "score16": "n/a",
        "score6": "n/a",
        "reason": "test injection",
        "original_action": args.action,
        "rejection_reason": ""
    }

    import csv
    write_header = not os.path.exists(args.outfile) or os.stat(args.outfile).st_size == 0
    with open(args.outfile, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(row.keys()))
        if write_header:
            w.writeheader()
        w.writerow(row)

    print(f"✓ Appended {args.action} {args.pair} {args.tf} @ {row['entry_price']} (ATR {row['atr']} pips, back {args.back_bars} bars) → {args.outfile}")

if __name__ == "__main__":
    main()
