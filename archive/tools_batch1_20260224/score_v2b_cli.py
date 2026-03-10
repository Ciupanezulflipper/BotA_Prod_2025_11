#!/data/data/com.termux/files/usr/bin/python
# Bot-A CLI: score with engine_v2b (EMA9/21 + VWAP fallback + volume proxy)

import os, sys
from signals.engine_v2b import score_symbol  # must exist in your repo

def main():
    sym = sys.argv[1] if len(sys.argv) > 1 else "EURUSD"
    tf  = os.getenv("TF", "5min")
    lim = int(os.getenv("LIMIT", "300"))

    res = score_symbol(sym, tf=tf, limit=lim)
    if not res or not res.get("ok"):
        print(f"{sym} score = N/A ({res.get('why') if isinstance(res, dict) else 'no data'})")
        return 1

    score = res.get("score")
    cls   = res.get("class")
    comps = res.get("components", {})
    trend      = comps.get("trend")
    momentum   = comps.get("momentum")
    volume     = comps.get("volume")
    structure  = comps.get("structure")
    volatility = comps.get("volatility")

    print(
        f"{sym} score = {score:.0f}/100 ({cls}) "
        f"[trend {trend}, mom {momentum}, vol {volume}, "
        f"struct {structure}, volat {volatility}]"
    )
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
