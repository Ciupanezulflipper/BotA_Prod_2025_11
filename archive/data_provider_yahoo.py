#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Yahoo provider (yfinance) for FX pairs, free tier.
Returns standardized JSON with candles and freshness metadata.

CLI:
  python3 tools/data_provider_yahoo.py --symbol EURUSD --tf 15 --limit 150
"""
import sys, json, argparse, math, datetime as dt, os

def _map_symbol(sym: str) -> str:
    s = sym.replace("/", "").upper()
    # Yahoo FX tickers use "=X" suffix (EURUSD -> EURUSD=X)
    return f"{s}=X"

def _tf_to_interval(tf) -> str:
    s = str(tf).lower().replace("m","")
    if s in ("1","5","15","30","60"):
        return {"1":"1m","5":"5m","15":"15m","30":"30m","60":"60m"}[s]
    # default to 15m if unknown
    return "15m"

def _period_for(tf: str, limit: int) -> str:
    # Heuristic periods that satisfy yfinance allowed set
    # 15m: up to ~5d gives ~130 bars/day windowing. Use 5d or 1mo if large.
    iv = tf
    if iv in ("1m","5m","15m","30m","60m"):
        bars_per_day = {"1m":1440, "5m":288, "15m":96, "30m":48, "60m":24}[iv]
        days = math.ceil(limit / bars_per_day) + 1
        if days <= 5:
            return "5d"
        elif days <= 30:
            return "1mo"
        elif days <= 90:
            return "3mo"
        else:
            return "6mo"
    return "5d"

def _utc_iso(ts) -> str:
    if ts.tzinfo is None:
        return ts.replace(tzinfo=dt.timezone.utc).isoformat().replace("+00:00","Z")
    return ts.astimezone(dt.timezone.utc).isoformat().replace("+00:00","Z")

def fetch(symbol: str, tf, limit: int):
    try:
        import yfinance as yf
        import pandas as pd
    except Exception as e:
        return {"ok": False, "error": f"yfinance/pandas not available: {e}"}

    ticker = _map_symbol(symbol)
    interval = _tf_to_interval(tf)
    period = _period_for(interval, limit)

    try:
        df = yf.download(
            tickers=ticker,
            interval=interval,
            period=period,
            auto_adjust=False,
            progress=False,
            threads=False,
        )
    except Exception as e:
        return {"ok": False, "error": f"yahoo download failed: {e}"}

    if df is None or df.empty:
        return {"ok": False, "error": "yahoo returned no data"}

    # Normalize columns (yfinance uses 'Open','High','Low','Close','Volume')
    for col in ("Open","High","Low","Close","Volume"):
        if col not in df.columns:
            return {"ok": False, "error": f"missing column {col}"}

    df = df.dropna()
    if df.empty:
        return {"ok": False, "error": "no rows after dropna()"}
    # Keep last `limit` rows
    if len(df) > limit:
        df = df.tail(limit)

    last_ts = df.index[-1]
    # yfinance index often tz-aware; handle both
    if hasattr(last_ts, "to_pydatetime"):
        last_ts = last_ts.to_pydatetime()

    now_utc = dt.datetime.now(dt.timezone.utc)
    if last_ts.tzinfo is None:
        last_ts_utc = last_ts.replace(tzinfo=dt.timezone.utc)
    else:
        last_ts_utc = last_ts.astimezone(dt.timezone.utc)
    age_min = (now_utc - last_ts_utc).total_seconds() / 60.0

    candles = []
    for ts, row in df.iterrows():
        ts_py = ts.to_pydatetime() if hasattr(ts, "to_pydatetime") else ts
        if ts_py.tzinfo is None:
            ts_py = ts_py.replace(tzinfo=dt.timezone.utc)
        else:
            ts_py = ts_py.astimezone(dt.timezone.utc)
        candles.append({
            "ts": _utc_iso(ts_py),
            "o": float(row["Open"]),
            "h": float(row["High"]),
            "l": float(row["Low"]),
            "c": float(row["Close"]),
            "v": float(row["Volume"]) if not (row["Volume"] != row["Volume"]) else 0.0,  # NaN-safe
        })

    out = {
        "ok": True,
        "provider": "yahoo",
        "symbol": symbol.upper(),
        "interval": interval,
        "rows": len(candles),
        "last_ts": _utc_iso(last_ts_utc),
        "age_min": round(age_min, 3),
        "candles": candles,   # ascending time
    }
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", required=True)
    ap.add_argument("--tf", required=True, help="15 or 15m etc")
    ap.add_argument("--limit", type=int, default=150)
    args = ap.parse_args()

    res = fetch(args.symbol, args.tf, args.limit)
    if not res.get("ok"):
        print(f"ERROR: {res.get('error','unknown')}", file=sys.stderr)
        sys.exit(1)
    print(json.dumps(res, ensure_ascii=False))
    sys.exit(0)

if __name__ == "__main__":
    main()
