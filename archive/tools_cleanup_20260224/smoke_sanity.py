#!/usr/bin/env python3
import os, sys
from datetime import timezone
from tools.fetch_data import get_ohlc, available_providers, available_usage_snapshot
from tools.news_fetch import fetch_headlines
from tools.news_sentiment import score_items

def main():
    print("== Providers ==", available_providers())
    print("== Usage before ==", available_usage_snapshot())
    # OHLC checks
    for sym in ("EURUSD","XAUUSD"):
        for tf in ("1h","4h","1day"):
            try:
                df = get_ohlc(sym, tf, limit=20)
                last = df.index[-1] if len(df) else None
                print(f"[OK] {sym} {tf} rows={len(df)} last={last}")
            except Exception as e:
                print(f"[FAIL] {sym} {tf} -> {e}")
    print("== Usage after ==", available_usage_snapshot())
    # News check
    try:
        items = fetch_headlines("EURUSD", window_hours=6, limit=6)
        sc, why = score_items(items)
        print(f"[NEWS] items={len(items)} score={sc}/10 | {why}")
    except Exception as e:
        print("[NEWS FAIL]", e)
    return 0

if __name__ == "__main__":
    sys.exit(main())
