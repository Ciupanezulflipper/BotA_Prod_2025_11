#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_providers.py
Quick sanity test for data/providers.py:
- ping_any()
- fetch_price() for each symbol
- fetch_ohlcv_safe() for each symbol at configured TF (default 5min)
Exits with non-zero status if any critical step fails.
"""

from __future__ import annotations
import os, sys, time
from datetime import datetime, timezone

# Allow "python ~/bot-a/tools/test_providers.py" from anywhere
sys.path.insert(0, os.path.expanduser("~/bot-a"))

from data import providers  # our module under test

GREEN = "\033[32m"
RED   = "\033[31m"
YELL  = "\033[33m"
DIM   = "\033[2m"
RESET = "\033[0m"

def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")

def env(name: str, default: str) -> str:
    return os.getenv(name, default)

def ok(msg: str):
    print(f"{GREEN}PASS{RESET} {msg}")

def fail(msg: str):
    print(f"{RED}FAIL{RESET} {msg}")

def warn(msg: str):
    print(f"{YELL}WARN{RESET} {msg}")

def main() -> int:
    print(f"{DIM}[test] {utcnow()} starting provider checks{RESET}")

    # ---------- config ----------
    watchlist = [s.strip().upper() for s in env("WATCHLIST", "EURUSD,XAUUSD").split(",") if s.strip()]
    tf        = env("BASE_TF", "5min")
    limit     = int(env("TF_LIMIT", "300"))  # rows requested for OHLCV

    print(f"{DIM}[cfg] WATCHLIST={watchlist}  TF={tf}  LIMIT={limit}{RESET}")

    # ---------- 1) ping ----------
    name, ok_ping, code, detail = providers.ping_any()
    if ok_ping:
        ok(f"ping_any(): provider={name} code={code} detail={detail}")
    else:
        # Not fatal (we’ll still try fallbacks), but surface it loudly.
        warn(f"ping_any(): provider={name} code={code} detail={detail}")

    overall_errors = 0

    # ---------- 2) loop symbols ----------
    for sym in watchlist:
        print(f"{DIM}--- {sym} ---{RESET}")

        # 2a) last price
        t0 = time.perf_counter()
        price = providers.fetch_price(sym)
        dt = (time.perf_counter() - t0) * 1000.0
        if price is not None:
            ok(f"{sym} price={price:.6f}  ({dt:.0f} ms)")
        else:
            fail(f"{sym} price=None  ({dt:.0f} ms)")
            overall_errors += 1  # price should usually succeed via at least one provider

        # 2b) OHLCV
        t0 = time.perf_counter()
        df = providers.fetch_ohlcv_safe(sym, tf=tf, limit=limit)
        dt = (time.perf_counter() - t0) * 1000.0

        if df is None or df.empty:
            fail(f"{sym} OHLCV: no data  ({dt:.0f} ms)")
            overall_errors += 1
        else:
            # show a tiny sample so we can visually verify shape & recency
            last_ts = df.index[-1].strftime("%Y-%m-%d %H:%MZ")
            ok(f"{sym} OHLCV: rows={len(df)} last={last_ts}  ({dt:.0f} ms)")
            # print first 3 rows compactly
            with pd_option():
                print(df.head(3))

    print(f"{DIM}[test] {utcnow()} done{RESET}")
    return 0 if overall_errors == 0 else 1


# Small context manager to print compact tables without global side-effects
import contextlib, pandas as pd
@contextlib.contextmanager
def pd_option():
    with pd.option_context(
        "display.width", 120,
        "display.max_rows", 6,
        "display.max_columns", 6,
        "display.precision", 6,
    ):
        yield


if __name__ == "__main__":
    raise SystemExit(main())
