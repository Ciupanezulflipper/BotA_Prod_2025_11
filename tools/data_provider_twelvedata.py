#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TwelveData free-tier provider (HTTP time_series).
Returns standardized JSON with candles. Handles 'status:error'.

CLI:
  python3 tools/data_provider_twelvedata.py --symbol EURUSD --tf 15 --limit 150
"""
import os, sys, json, argparse, datetime as dt, urllib.request, urllib.error

def _tf_to_interval(tf) -> str:
    s = str(tf).lower().replace("m","")
    return {"1":"1min","5":"5min","15":"15min","30":"30min","60":"60min"}.get(s,"15min")

def _format_symbol(sym: str) -> str:
    # TD needs "EUR/USD" with slash
    s = sym.upper().replace(" ", "")
    if "/" not in s and len(s) == 6:
        s = s[:3] + "/" + s[3:]
    return s

def _utc_iso(ts: dt.datetime) -> str:
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=dt.timezone.utc)
    return ts.astimezone(dt.timezone.utc).isoformat().replace("+00:00","Z")

def fetch(symbol: str, tf, limit: int):
    key = os.getenv("TWELVE_DATA_API_KEY","").strip()
    if not key:
        return {"ok": False, "error": "TWELVE_DATA_API_KEY not set"}

    interval = _tf_to_interval(tf)
    sym = _format_symbol(symbol)
    url = ( "https://api.twelvedata.com/time_series"
            f"?symbol={sym}&interval={interval}&outputsize={limit}&apikey={key}" )

    try:
        with urllib.request.urlopen(url, timeout=20) as r:
            raw = r.read().decode("utf-8","ignore")
            data = json.loads(raw)
    except urllib.error.HTTPError as e:
        return {"ok": False, "error": f"HTTP {e.code}: {e.reason}"}
    except Exception as e:
        return {"ok": False, "error": f"request failed: {e}"}

    # Handle error format
    if isinstance(data, dict) and data.get("status") == "error":
        msg = data.get("message","unknown")
        return {"ok": False, "error": f"twelvedata error: {msg}"}

    values = data.get("values")
    if not values:
        return {"ok": False, "error": "no values"}

    # TD values are newest-first; convert to ascending
    values = list(reversed(values))
    if len(values) > limit:
        values = values[-limit:]

    candles = []
    last_ts_utc = None
    for row in values:
        # example "datetime": "2025-11-03 12:45:00"
        ts = dt.datetime.strptime(row["datetime"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=dt.timezone.utc)
        last_ts_utc = ts
        candles.append({
            "ts": _utc_iso(ts),
            "o": float(row["open"]),
            "h": float(row["high"]),
            "l": float(row["low"]),
            "c": float(row["close"]),
            "v": float(row.get("volume") or 0.0),
        })

    now_utc = dt.datetime.now(dt.timezone.utc)
    age_min = (now_utc - last_ts_utc).total_seconds()/60.0 if last_ts_utc else 1e9

    return {
        "ok": True,
        "provider": "twelve_data",
        "symbol": symbol.upper(),
        "interval": interval,
        "rows": len(candles),
        "last_ts": _utc_iso(last_ts_utc) if last_ts_utc else None,
        "age_min": round(age_min,3),
        "candles": candles,
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", required=True)
    ap.add_argument("--tf", required=True)
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
