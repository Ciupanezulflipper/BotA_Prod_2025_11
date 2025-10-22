#!/data/data/com.termux/files/usr/bin/python
import os, sys

# Data fetch + scoring
from data.ohlcv import fetch
from signals.engine import score_series

def normalize_symbol(sym: str) -> str:
    s = sym.upper().replace(" ", "")
    mapping = {
        "EURUSD": "EUR/USD",
        "GBPUSD": "GBP/USD",
        "USDJPY": "USD/JPY",
        "AUDUSD": "AUD/USD",
        "NZDUSD": "NZD/USD",
        "USDCAD": "USD/CAD",
        "USDCHF": "USD/CHF",
        "XAUUSD": "XAU/USD",
        "XAGUSD": "XAG/USD",
        "BTCUSD": "BTC/USD",
        "ETHUSD": "ETH/USD",
    }
    return mapping.get(s, sym)

def main():
    sym = sys.argv[1] if len(sys.argv) > 1 else "EURUSD"
    tf = os.getenv("TF", "5min")
    limit = int(os.getenv("LIMIT", "300"))

    norm = normalize_symbol(sym)
    candles = fetch(norm, tf=tf, limit=limit)

    # Fallback: if no data and no slash, try auto-inserting slash
    if not candles and "/" not in sym and len(sym) == 6:
        alt = f"{sym[:3]}/{sym[3:]}"
        candles = fetch(alt, tf=tf, limit=limit)

    if not candles:
        print(f"{sym} score = N/A (no data)")
        sys.exit(1)

    scores = score_series(candles)
    last = [s for s in scores if s is not None][-1]
    print(f"{sym} score = {last:.0f}/100 (engine-demo)")

if __name__ == "__main__":
    main()
