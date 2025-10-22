#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EURUSD M15 backtester (Termux/Linux)

- Replays a CSV (default: eurusd_m15.csv) through the SAME logic as runner_full
- Uses Wilder/EWM ADX (alpha=1/length), RSI, MACD
- Scoring matches runner_full: ADX +0.5, |ΔMACD| +0.3, Direction +0.2 (cap 1.0)
- Modes: institutional / aggressive (threshold presets), or override via env/flags

Usage:
  python3 runner_backtest.py                   # uses eurusd_m15.csv + env/INSTITUTIONAL defaults
  python3 runner_backtest.py ~/path/file.csv   # custom csv
  MODE=aggressive python3 runner_backtest.py
  python3 runner_backtest.py --mode aggressive --rows 500

CSV required columns: timestamp, open, high, low, close (volume optional)
"""

import os, sys, math, argparse, textwrap
from datetime import datetime, timezone
import pandas as pd
import numpy as np

# ---------- Params (env with sensible defaults; mode presets below) ----------
DEF_ADX_MIN   = float(os.getenv("ADX_MIN", "14"))
DEF_RSI_BUY   = float(os.getenv("RSI_BUY", "62"))
DEF_RSI_SELL  = float(os.getenv("RSI_SELL", "38"))
DEF_MACD_MIN  = float(os.getenv("MACD_MIN", "3.5e-05"))
DEF_CONF_MIN  = float(os.getenv("CONF_MIN", "0.8"))

# Aggressive preset (looser gates)
AGG = dict(ADX_MIN=12.0, RSI_BUY=60.0, RSI_SELL=40.0, MACD_MIN=3e-05, CONF_MIN=0.5)
# Institutional preset (your tuned live defaults)
INST = dict(ADX_MIN=14.0, RSI_BUY=62.0, RSI_SELL=38.0, MACD_MIN=3.5e-05, CONF_MIN=0.8)

# ---------- Indicators (aligned with runner_full) ----------
def rsi(series: pd.Series, length: int = 14) -> pd.Series:
    s = series.astype(np.float64)
    delta = s.diff()
    gain = (delta.clip(lower=0)).ewm(alpha=1/length, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1/length, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    out = 100 - (100 / (1 + rs))
    return out.fillna(50.0)

def macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    s = series.astype(np.float64)
    ema_fast = s.ewm(span=fast, adjust=False).mean()
    ema_slow = s.ewm(span=slow, adjust=False).mean()
    line = ema_fast - ema_slow
    sig  = line.ewm(span=signal, adjust=False).mean()
    hist = line - sig
    return line, sig, hist

def adx(high: pd.Series, low: pd.Series, close: pd.Series, length: int = 14) -> pd.Series:
    # Wilder/EWM, consistent with analysis tools & live runner
    high = high.astype(np.float64); low = low.astype(np.float64); close = close.astype(np.float64)
    upmove = high.diff()
    downmove = -low.diff()
    plus_dm = np.where((upmove > downmove) & (upmove > 0), upmove, 0.0)
    minus_dm = np.where((downmove > upmove) & (downmove > 0), downmove, 0.0)

    tr1 = (high - low)
    tr2 = (high - close.shift()).abs()
    tr3 = (low  - close.shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    atr = tr.ewm(alpha=1/length, adjust=False).mean()
    plus_di  = 100 * (pd.Series(plus_dm, index=high.index).ewm(alpha=1/length, adjust=False).mean() / atr)
    minus_di = 100 * (pd.Series(minus_dm, index=high.index).ewm(alpha=1/length, adjust=False).mean() / atr)

    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx_val = dx.ewm(alpha=1/length, adjust=False).mean()
    return adx_val.fillna(0.0)

# ---------- Scoring (identical to runner_full) ----------
def decide_direction(rsi_v, macd_h_v, ADX_MIN, RSI_BUY, RSI_SELL, MACD_MIN, adx_v) -> str:
    if adx_v >= ADX_MIN and macd_h_v >=  MACD_MIN and rsi_v >= RSI_BUY:
        return "BUY"
    if adx_v >= ADX_MIN and macd_h_v <= -MACD_MIN and rsi_v <= RSI_SELL:
        return "SELL"
    return "FLAT"

def score_row(rsi_v, adx_v, macd_h_v, direction) -> float:
    conf = 0.0
    if adx_v >= params.ADX_MIN: conf += 0.5
    if abs(macd_h_v) >= params.MACD_MIN: conf += 0.3
    if direction != "FLAT": conf += 0.2
    return min(conf, 1.0)

def blockers(rsi_v, adx_v, macd_h_v, direction, p) -> list:
    b = []
    if adx_v < p.ADX_MIN: b.append("ADX weak")
    if abs(macd_h_v) < p.MACD_MIN: b.append("ΔMACD small")
    if rsi_v > p.RSI_SELL and rsi_v < p.RSI_BUY:
        b.append("RSI mid")
    if direction == "FLAT":
        # give hint which side missing
        if rsi_v >= p.RSI_BUY and macd_h_v <= p.MACD_MIN: b.append("MACD not ↑")
        if rsi_v <= p.RSI_SELL and macd_h_v >= -p.MACD_MIN: b.append("MACD not ↓")
    return b or ["—"]

# ---------- Backtest core ----------
def prepare_df(csv_path: str, rows: int = None) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    # Normalize columns
    # Accept: time or timestamp
    tcol = "timestamp" if "timestamp" in df.columns else ("time" if "time" in df.columns else None)
    if tcol is None:
        raise RuntimeError("CSV must have a 'timestamp' (or 'time') column.")
    df = df.rename(columns={tcol: "timestamp"})
    for c in ("open", "high", "low", "close"):
        if c not in df.columns: raise RuntimeError(f"CSV missing column '{c}'")
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    df = df.dropna(subset=["timestamp"])
    for c in ("open", "high", "low", "close"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["open", "high", "low", "close"]).reset_index(drop=True)
    if rows and rows > 0:
        df = df.tail(rows).reset_index(drop=True)
    return df

def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df["rsi"]   = rsi(df["close"], 14)
    _, _, h     = macd(df["close"], 12, 26, 9)
    df["macd_h"]= h
    df["adx"]   = adx(df["high"], df["low"], df["close"], 14)
    return df

def run_backtest(df: pd.DataFrame, p) -> pd.DataFrame:
    # Decide/score per row
    dirs = []
    scores = []
    blks = []
    for i in range(len(df)):
        r, a, m = df.loc[i, "rsi"], df.loc[i, "adx"], df.loc[i, "macd_h"]
        d = decide_direction(r, m, p.ADX_MIN, p.RSI_BUY, p.RSI_SELL, p.MACD_MIN, a)
        s = score_row(r, a, m, d)
        dirs.append(d); scores.append(s); blks.append("; ".join(blockers(r, a, m, d, p)))
    out = df.copy()
    out["score"] = np.round(scores, 2)
    out["dir"]   = dirs
    out["why"]   = blks
    return out

def summarize(bt: pd.DataFrame, p, title: str):
    sigs = bt[(bt["dir"]!="FLAT") & (bt["score"]>=p.CONF_MIN)]
    print("\n== BACKTEST SUMMARY ==")
    print(f"Mode: {title}")
    print(f"Rows tested: {len(bt)}")
    print(f"Signals: {len(sigs)} (CONF_MIN={p.CONF_MIN})")
    if not sigs.empty:
        print("\nSample last 5 signals:")
        for _, r in sigs.tail(5).iterrows():
            ts = r['timestamp'].strftime('%Y-%m-%d %H:%M:%S %Z')
            print(f"  {ts} | close {r['close']:.5f} | score {r['score']:.2f} | {r['dir']} | "
                  f"RSI {r['rsi']:.1f} | ADX {r['adx']:.1f} | ΔMACD {r['macd_h']:.6f}")
    # blockers
    weak_adx = (bt["adx"] < p.ADX_MIN).sum()
    rsi_mid  = ((bt["rsi"] > p.RSI_SELL) & (bt["rsi"] < p.RSI_BUY)).sum()
    macd_sm  = (bt["macd_h"].abs() < p.MACD_MIN).sum()
    print("\nTop blockers (count over all rows):")
    print(f"  ADX weak : {weak_adx}")
    print(f"  RSI mid  : {rsi_mid}")
    print(f"  ΔMACD small: {macd_sm}")
    print("\nCandles that WOULD have sent under current gates (last 3):")
    for _, r in sigs.tail(3).iterrows():
        ts = r['timestamp'].strftime('%Y-%m-%d %H:%M:%S %Z')
        print(f"  {ts} | close {r['close']:.5f} | RSI {r['rsi']:.1f} | ADX {r['adx']:.1f} | "
              f"ΔMACD {r['macd_h']:.6f} | score {r['score']:.2f} | {r['dir']}")

# Small helper struct for params
class Params:
    def __init__(self, **k): self.__dict__.update(k)
    def __getattr__(self, k): return self.__dict__[k]

def choose_params(mode: str):
    mode = (mode or os.getenv("MODE", "institutional")).strip().lower()
    if mode in ("aggressive", "agg"):
        base = AGG
        title = "Aggressive"
    else:
        base = INST
        title = "Institutional"
    # allow env overrides on top of preset
    p = dict(
        ADX_MIN=float(os.getenv("ADX_MIN", base["ADX_MIN"])),
        RSI_BUY=float(os.getenv("RSI_BUY", base["RSI_BUY"])),
        RSI_SELL=float(os.getenv("RSI_SELL", base["RSI_SELL"])),
        MACD_MIN=float(os.getenv("MACD_MIN", base["MACD_MIN"])),
        CONF_MIN=float(os.getenv("CONF_MIN", base["CONF_MIN"])),
    )
    # If user exported DEF_* explicitly, prefer those (optional)
    if "ADX_MIN" in os.environ and "MODE" not in os.environ and not mode:
        p["ADX_MIN"] = DEF_ADX_MIN
        p["RSI_BUY"] = DEF_RSI_BUY
        p["RSI_SELL"] = DEF_RSI_SELL
        p["MACD_MIN"] = DEF_MACD_MIN
        p["CONF_MIN"] = DEF_CONF_MIN
    return Params(**p), title

def main():
    ap = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Backtest EURUSD M15 using live-runner logic.",
        epilog=textwrap.dedent("""\
            Examples:
              python3 runner_backtest.py
              python3 runner_backtest.py ~/bot-a/tools/eurusd_m15.csv --mode aggressive --rows 500
        """),
    )
    ap.add_argument("csv", nargs="?", default=os.path.expanduser("~/bot-a/tools/eurusd_m15.csv"))
    ap.add_argument("--mode", choices=["institutional","aggressive"], default=os.getenv("MODE","institutional"))
    ap.add_argument("--rows", type=int, default=500, help="Tail N rows from CSV (default 500)")
    args = ap.parse_args()

    global params
    params, title = choose_params(args.mode)

    print("[INFO] Loading CSV:", args.csv)
    df = prepare_df(args.csv, rows=args.rows)
    if len(df) < 60:
        print("[WARN] Few rows; indicators may be immature.")

    df = compute_indicators(df)
    bt = run_backtest(df, params)
    summarize(bt, params, title)

if __name__ == "__main__":
    main()
