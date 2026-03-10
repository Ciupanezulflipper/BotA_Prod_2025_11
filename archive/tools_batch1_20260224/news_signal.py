#!/usr/bin/env python3
import os, json
from tools.news import news_for_symbols

def main():
    wl = os.getenv("WATCHLIST","EURUSD,XAUUSD").split(",")
    wl = [s.strip().upper() for s in wl if s.strip()]
    res = news_for_symbols(wl)
    # pretty print one-liners
    for r in res:
        print(f"{r['symbol']:7} | news {r['score']:+d} | {r['bias']:<7} | {r['why']}")
    # also emit JSON (for bots to consume)
    print("\nJSON:")
    print(json.dumps(res, ensure_ascii=False))

if __name__ == "__main__":
    main()
