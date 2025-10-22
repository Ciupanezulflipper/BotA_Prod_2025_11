#!/usr/bin/env python3
import os
import sys
from datetime import datetime, timezone

# Make sure .env is loaded and key names normalized
from tools.env_loader import ensure_env
ensure_env()

def mask(v: str) -> str:
    if not v:
        return "(missing)"
    if len(v) <= 6:
        return "*" * len(v)
    return v[:3] + "…" + v[-3:]

def show_keys():
    keys = {
        "FINNHUB_TOKEN": os.environ.get("FINNHUB_TOKEN", ""),
        "TWELVEDATA_TOKEN": os.environ.get("TWELVEDATA_TOKEN", ""),
        "ALPHAVANTAGE_KEY": os.environ.get("ALPHAVANTAGE_KEY", ""),
    }
    print("== Visible API keys (masked) ==")
    for k, v in keys.items():
        print(f"{k}: {mask(v)}")
    print()

def try_fetch(symbol: str, interval: str, limit: int = 5):
    print(f"[TEST] {symbol} {interval}")
    try:
        # Your existing fetcher
        from tools.fetch_data import get_ohlc
        df = get_ohlc(symbol, interval, limit=limit)
        if df is None or df.empty:
            print(" -> FAIL: empty DataFrame\n")
            return False
        print(f" -> OK: rows={len(df)}, cols={list(df.columns)}")
        try:
            print(df.head(3), "\n")
        except Exception:
            print(" -> OK but head() failed to print (non-fatal)\n")
        return True
    except Exception as e:
        print(" -> FAIL:", repr(e), "\n")
        return False

def main():
    print("check_env_and_providers.py |", datetime.now(timezone.utc).strftime("UTC %H:%M"))
    show_keys()
    ok_all = True
    for sym in ["EURUSD", "XAUUSD"]:
        ok = try_fetch(sym, "1h", limit=5)
        ok_all = ok_all and ok
    if not ok_all:
        sys.exit(2)

if __name__ == "__main__":
    main()
