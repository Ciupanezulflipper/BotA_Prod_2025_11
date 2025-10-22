#!/usr/bin/env python3
import os, sys
from signals.engine_v1 import score_symbol_v1

def main():
    sym = (sys.argv[1] if len(sys.argv) > 1 else "EURUSD").upper()
    tf  = os.getenv("TF", "5min")
    lim = int(os.getenv("LIMIT", "300"))
    res = score_symbol_v1(sym, tf=tf, limit=lim)
    print(res["text"] if res.get("ok") else res.get("text","N/A"))

if __name__ == "__main__":
    main()
