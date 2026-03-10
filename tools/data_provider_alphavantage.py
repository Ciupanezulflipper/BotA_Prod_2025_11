#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Alpha Vantage free-tier FX provider.
Handles rate-limit/Note cases and returns standardized JSON.

CLI:
  python3 tools/data_provider_alphavantage.py --symbol EURUSD --tf 15 --limit 150
"""
import os, sys, json, argparse, datetime as dt, urllib.request, urllib.error

def _tf_to_interval(tf) -> str:
    s = str(tf).lower().replace("m","")
    # AV supports: 1min,5min,15min,30min,60min
    return {"1":"1min","5":"5min","15":"15min","30":"30min","60":"60min"}.get(s,"15min")

def _utc_iso(ts: dt.datetime) -> str:
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=dt.timezone.utc)
    return ts.astimezone(dt.timezone.utc).isoformat().replace("+00:00","Z")

def fetch(symbol: str, tf, limit: int):
    key = os.getenv("ALPHA_VANTAGE_API_KEY","").strip()
    if not key:
        return {"ok": False, "error": "ALPHA_VANTAGE_API_KEY not set"}

    from_sym = symbol.replace("/","").upper()[:3]
    to_sym = symbol.replace("/","").upper()[3:]
    interval = _tf_to_interval(tf)

    url = ( "https://www.alphavantage.co/query"
            f"?function=FX_INTRADAY&from_symbol={from_sym}&to_symbol={to_sym}"
            f"&interval={interval}&outputsize=compact&apikey={key}" )

    try:
        with urllib.request.urlopen(url, timeout=20) as r:
            raw = r.read().decode("utf-8","ignore")
            data = json.loads(raw)
    except urllib.error.HTTPError as e:
        return {"ok": False, "error": f"HTTP {e.code}: {e.reason}"}
    except Exception as e:
        return {"ok": False, "error": f"request failed: {e}"}

    # Handle common free-tier messages
    if "Note" in data:
        return {"ok": False, "error": f"rate-limited: {data['Note'][:100]}..."}
    if "Information" in data:
        return {"ok": False, "error": f"info: {data['Information'][:100]}..."}
    if "Error Message" in data:
        return {"ok": False, "error": f"error: {data['Error Message']}"}

    # Expected key
    key_ts = next((k for k in data.keys() if k.startswith("Time Series FX")), None)
    if not key_ts or not isinstance(data.get(key_ts), dict):
        return {"ok": False, "error": "no time series returned"}

    series = data[key_ts]  # dict of time-> { "1. open": "...", ... }
    if not series:
        return {"ok": False, "error": "empty time series"}

    # Convert to ascending list
    items = sorted(series.items(), key=lambda kv: kv[0])
    if len(items) > limit:
        items = items[-limit:]

    candles = []
    last_ts_utc = None
    for tstr, row in items:
        # AV timestamps are in UTC like "2025-11-03 12:45:00"
        ts = dt.datetime.strptime(tstr, "%Y-%m-%d %H:%M:%S").replace(tzinfo=dt.timezone.utc)
        last_ts_utc = ts
        candles.append({
            "ts": _utc_iso(ts),
            "o": float(row.get("1. open", "nan")),
            "h": float(row.get("2. high", "nan")),
            "l": float(row.get("3. low", "nan")),
            "c": float(row.get("4. close", "nan")),
            "v": 0.0  # FX intraday endpoint lacks volume
        })

    now_utc = dt.datetime.now(dt.timezone.utc)
    age_min = (now_utc - last_ts_utc).total_seconds()/60.0 if last_ts_utc else 1e9

    return {
        "ok": True,
        "provider": "alpha_vantage",
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
