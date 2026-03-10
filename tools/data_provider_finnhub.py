#!/usr/bin/env python3
# File: tools/data_provider_finnhub.py
# Desc: Fetch OHLC candles from Finnhub for FX pairs with fallback / graceful error handling.

import os, sys, time, json, argparse, datetime as dt
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError

BASE = "https://finnhub.io/api/v1/forex/candle"

TF_MAP = {
    1:"1", 3:"3", 5:"5", 15:"15", 30:"30", 60:"60",
    120:"120", 240:"240", 480:"480", 1440:"D"
}

def to_finnhub_symbol(symbol: str) -> str:
    s = symbol.upper().replace("/", "")
    return f"OANDA:{s}"

def fetch(symbol: str, tf_minutes: int, limit: int, token: str, retries=2, wait=1.5):
    if not token:
        raise RuntimeError("FINNHUB_TOKEN not set")
    res = TF_MAP.get(tf_minutes)
    if not res:
        raise ValueError(f"Unsupported tf {tf_minutes}m")

    now = int(time.time())
    bars = max(limit + 5, 60)
    _from = now - bars * tf_minutes * 60
    _to = now

    sym = to_finnhub_symbol(symbol)
    url = f"{BASE}?symbol={sym}&resolution={res}&from={_from}&to={_to}&token={token}"

    last_err = None
    for _ in range(retries + 1):
        try:
            req = Request(url, headers={"User-Agent":"Mozilla/5.0"})
            with urlopen(req, timeout=10) as r:
                raw = r.read().decode("utf-8")
            data = json.loads(raw)
            # handle permission/denied case
            if "error" in data:
                # likely insufficient plan / access denied
                raise RuntimeError(f"Finnhub: {data['error']}")
            if data.get("s") != "ok":
                raise RuntimeError(f"Finnhub status={data.get('s')} msg={data}")
            rows=[]
            for i,(t,o,h,l,c,v) in enumerate(zip(
                data["t"], data["o"], data["h"], data["l"], data["c"], data["v"]
            )):
                rows.append({
                    "t": int(t),
                    "o": float(o),
                    "h": float(h),
                    "l": float(l),
                    "c": float(c),
                    "v": float(v),
                })
            return rows[-limit:]
        except (HTTPError, URLError, RuntimeError, ValueError) as e:
            last_err = e
            time.sleep(wait)
    raise RuntimeError(f"Finnhub failed: {last_err}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", required=True)
    ap.add_argument("--tf", type=int, required=True, help="minutes (e.g. 15)")
    ap.add_argument("--limit", type=int, default=150)
    ap.add_argument("--json", action="store_true", help="print json lines")
    args = ap.parse_args()

    token = os.getenv("FINNHUB_TOKEN") or os.getenv("FINNHUB_API_KEY") or ""
    try:
        rows = fetch(args.symbol, args.tf, args.limit, token)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(json.dumps(rows))
    else:
        print(f"OK {args.symbol} tf={args.tf} got={len(rows)}")
        for r in rows[-5:]:
            ts = dt.datetime.utcfromtimestamp(r["t"]).strftime("%F %T")
            print(ts, r["o"], r["h"], r["l"], r["c"], r["v"])

if __name__ == "__main__":
    main()
