#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
smoke_bundle.py
One-shot diagnostic runner:
- Tries multiple symbols and timeframes with the current provider rotator.
- Prints a compact status line per (symbol, timeframe).
- Appends results to logs/smoke_bundle-YYYYMMDD.csv for later analysis.
- NEVER edits your .env; respects current environment exports:
  ROTATOR_ORDER, *_RATE_PER_MIN, etc.

Usage examples:
  PYTHONPATH="$HOME/bot-a" python ~/bot-a/tools/smoke_bundle.py
  PYTHONPATH="$HOME/bot-a" python ~/bot-a/tools/smoke_bundle.py --symbols EURUSD XAUUSD --tfs 1h 4h 1d --limit 10
"""

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
import traceback

import pandas as pd  # pandas is used only for pretty tail() formatting

# We rely on your existing rotator; no .env edits here.
from tools.data_rotator import get_ohlc_rotating

DEFAULT_SYMBOLS = ["EURUSD", "XAUUSD"]
DEFAULT_TFS = ["1h", "4h", "1d"]

def utc_now_str():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

def ensure_logs_dir() -> Path:
    base = Path(os.environ.get("HOME", "")) / "bot-a" / "logs"
    base.mkdir(parents=True, exist_ok=True)
    return base

def log_csv_row(csv_path: Path, row: dict):
    header = not csv_path.exists()
    import csv
    with csv_path.open("a", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "utc_ts","symbol","tf","status","provider",
                "rows","last_index","message"
            ],
        )
        if header:
            w.writeheader()
        w.writerow(row)

def main():
    ap = argparse.ArgumentParser(description="Bundle smoke test for FX data providers.")
    ap.add_argument("--symbols", nargs="+", default=DEFAULT_SYMBOLS, help="Symbols to test")
    ap.add_argument("--tfs", nargs="+", default=DEFAULT_TFS, help="Timeframes (e.g., 1h 4h 1d)")
    ap.add_argument("--limit", type=int, default=10, help="Rows to request per pull")
    args = ap.parse_args()

    logs_dir = ensure_logs_dir()
    csv_path = logs_dir / f"smoke_bundle-{datetime.utcnow().strftime('%Y%m%d')}.csv"

    print(f"=== SMOKE BUNDLE @ {utc_now_str()} ===")
    print(f"Symbols: {args.symbols} | TFs: {args.tfs} | limit={args.limit}")
    print(f"ROTATOR_ORDER={os.environ.get('ROTATOR_ORDER','<default inside rotator>')}")
    print("------------------------------------------------------------")

    # Run the matrix
    for sym in args.symbols:
        for tf in args.tfs:
            try:
                df, provider = get_ohlc_rotating(sym, tf, limit=args.limit)
                rows = len(df)
                last_idx = str(df.index[-1]) if rows else ""
                print(f"[OK]    {sym:7s} {tf:3s} via {provider:12s} rows={rows:3d} last={last_idx}")
                # Show the last 3 for a quick eyeball
                try:
                    print(df.tail(3).to_string())
                except Exception:
                    pass

                log_csv_row(
                    csv_path,
                    dict(
                        utc_ts=utc_now_str(),
                        symbol=sym,
                        tf=tf,
                        status="ok",
                        provider=provider,
                        rows=rows,
                        last_index=last_idx,
                        message="",
                    ),
                )
            except Exception as e:
                # Don’t crash: record the failure and continue.
                msg = str(e).replace("\n", " ")[:400]
                # If our rotator raised a composed error, try to reveal last provider in the message
                provider_hint = ""
                for hint in ("twelvedata", "alphavantage", "finnhub", "eodhd", "yahoo", "polygon", "marketaaux", "exchangerate"):
                    if hint in msg:
                        provider_hint = hint
                        break

                print(f"[FAIL]  {sym:7s} {tf:3s} via {provider_hint or '-':12s} -> {msg}")
                # Optional: uncomment to debug deep trace locally
                # traceback.print_exc()

                log_csv_row(
                    csv_path,
                    dict(
                        utc_ts=utc_now_str(),
                        symbol=sym,
                        tf=tf,
                        status="fail",
                        provider=provider_hint,
                        rows=0,
                        last_index="",
                        message=msg,
                    ),
                )

    print("------------------------------------------------------------")
    print(f"CSV log appended: {csv_path}")

if __name__ == "__main__":
    sys.exit(main())
