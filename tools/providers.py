"""BotA/tools/providers.py
Robust multi-provider OHLC fetcher with retry + cache + SSL toggle.
"""

from __future__ import annotations
import os, json, time, requests, argparse
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timezone

# --------------------------- config ---------------------------

CACHE_DIR = Path.home() / "BotA" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_TTL_SEC = 30 * 60

YAHOO_ENDPOINTS = (
    "https://query1.finance.yahoo.com",
    "https://query2.finance.yahoo.com",
)
YAHOO_RETRIES = 3
YAHOO_BACKOFF_BASE = 2

TF_TO_YAHOO = {
    "M1": "1m",
    "M5": "5m",
    "M15": "15m",
    "M30": "30m",
    "H1": "60m",
    "H4": "1h",
    "D1": "1d",
}
TF_TO_AV = {
    "M1": "1min",
    "M5": "5min",
    "M15": "15min",
    "M30": "30min",
    "H1": "60min",
}
TF_TO_TD = {
    "M1": "1min",
    "M5": "5min",
    "M15": "15min",
    "M30": "30min",
    "H1": "1h",
    "H4": "4h",
    "D1": "1day",
}

# --------------------------- helpers ---------------------------

def _bool_env(name: str, default: bool = True) -> bool:
    return os.getenv(name, "true" if default else "false").lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def _provider_order() -> List[str]:
    return [
        p.strip().lower()
        for p in os.getenv(
            "PROVIDER_ORDER", "yahoo,alphavantage,twelvedata"
        ).split(",")
    ]


def _cache_path(pair: str, tf: str) -> Path:
    return CACHE_DIR / f"{pair}_{tf}.json"


def _cache_load(pair: str, tf: str) -> Optional[Tuple[List[Dict], str]]:
    p = _cache_path(pair, tf)
    if not p.exists():
        return None
    try:
        obj = json.loads(p.read_text())
        if time.time() - obj.get("cached_at", 0) > CACHE_TTL_SEC:
            return None
        rows = obj.get("rows") or []
        src = obj.get("source", "unknown")
        if rows:
            return rows, f"cache:{src}"
    except:
        return None
    return None


def _cache_save(pair: str, tf: str, rows: List[Dict], src: str) -> None:
    try:
        _cache_path(pair, tf).write_text(
            json.dumps({"cached_at": time.time(), "rows": rows, "source": src})
        )
    except:
        pass


def _iso_ts(ts):
    return (
        datetime.fromtimestamp(ts, tz=timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _iso_str(s):
    return s.replace(" ", "T") + ("" if s.endswith("Z") else "Z")


# --------------------------- providers ---------------------------

def _fetch_yahoo(pair, tf, bars, verify):
    interval = TF_TO_YAHOO.get(tf)
    if not interval:
        raise RuntimeError(f"Yahoo: TF {tf} not supported")
    sym = f"{pair}=X"
    rng = {
        "1m": "7d",
        "5m": "60d",
        "15m": "60d",
        "30m": "60d",
        "60m": "730d",
        "1h": "730d",
        "1d": "max",
    }.get(interval, "60d")
    last = "yahoo unknown"
    for att in range(YAHOO_RETRIES):
        base = YAHOO_ENDPOINTS[att % 2]
        url = f"{base}/v8/finance/chart/{sym}"
        try:
            r = requests.get(
                url,
                params={"interval": interval, "range": rng},
                timeout=15,
                verify=verify,
                headers={"User-Agent": "Mozilla"},
            )
            if r.status_code == 429:
                last = "429 rate limit"
                time.sleep(YAHOO_BACKOFF_BASE ** (att + 1))
                continue
            r.raise_for_status()
            data = r.json()
            res = (data.get("chart") or {}).get("result") or []
            if not res:
                raise RuntimeError("Yahoo: empty result")
            q = res[0]
            ts = q.get("timestamp") or []
            ind = q.get("indicators", {}).get("quote", [{}])[0]
            rows = []
            for i, t in enumerate(ts):
                c = ind["close"][i] if i < len(ind["close"]) else None
                if c is None:
                    continue
                rows.append(
                    {
                        "time": _iso_ts(t),
                        "open": float(ind["open"][i] or c),
                        "high": float(ind["high"][i] or c),
                        "low": float(ind["low"][i] or c),
                        "close": float(c),
                    }
                )
            if len(rows) < bars * 0.5:
                raise RuntimeError("Yahoo: insufficient bars")
            return rows[-bars:]
        except Exception as e:
            last = str(e)
    raise RuntimeError(last)


def _fetch_av(pair, tf, bars, verify):
    key = os.getenv("ALPHAVANTAGE_API_KEY")
    if not key:
        raise RuntimeError("AlphaVantage: no key configured; skipping")
    interval = TF_TO_AV.get(tf)
    if not interval:
        raise RuntimeError(f"AV: TF {tf} not supported")
    url = "https://www.alphavantage.co/query"
    params = {
        "function": "FX_INTRADAY",
        "from_symbol": pair[:3],
        "to_symbol": pair[3:],
        "interval": interval,
        "outputsize": "full",
        "apikey": key,
    }
    r = requests.get(url, params=params, timeout=15, verify=verify)
    r.raise_for_status()
    d = r.json()
    if "Note" in d:
        raise RuntimeError("AV: rate limit")
    k = f"Time Series FX ({interval})"
    s = d.get(k) or {}
    rows = [
        {
            "time": _iso_str(t),
            "open": float(v["1. open"]),
            "high": float(v["2. high"]),
            "low": float(v["3. low"]),
            "close": float(v["4. close"]),
        }
        for t, v in sorted(s.items())
    ]
    if len(rows) < bars * 0.5:
        raise RuntimeError("AV insufficient")
    return rows[-bars:]


def _fetch_td(pair, tf, bars, verify):
    key = os.getenv("TWELVEDATA_API_KEY") or os.getenv("TWELVE_DATA_API_KEY")
    if not key:
        raise RuntimeError("TD: no key configured; skipping")
    interval = TF_TO_TD.get(tf)
    if not interval:
        raise RuntimeError(f"TD: TF {tf} not supported")
    sym = f"{pair[:3]}/{pair[3:]}"
    r = requests.get(
        "https://api.twelvedata.com/time_series",
        params={
            "symbol": sym,
            "interval": interval,
            "outputsize": bars + 50,
            "apikey": key,
        },
        timeout=15,
        verify=verify,
    )
    r.raise_for_status()
    d = r.json()
    vals = d.get("values") or []
    rows = [
        {
            "time": _iso_str(v["datetime"]),
            "open": float(v["open"]),
            "high": float(v["high"]),
            "low": float(v["low"]),
            "close": float(v["close"]),
        }
        for v in reversed(vals)
    ]
    return rows[-bars:]

# --------------------------- unified fetch ---------------------------

def get_ohlc(pair: str, tf: str, bars: int = 200) -> Tuple[List[Dict], str]:
    verify = _bool_env("VERIFY_SSL", True)
    order = _provider_order()
    cached = _cache_load(pair, tf)
    if cached:
        return cached
    last_error = None
    for src in order:
        try:
            if src == "yahoo":
                rows = _fetch_yahoo(pair, tf, bars, verify)
            elif src == "alphavantage":
                rows = _fetch_av(pair, tf, bars, verify)
            elif src == "twelvedata":
                rows = _fetch_td(pair, tf, bars, verify)
            else:
                continue
            _cache_save(pair, tf, rows, src)
            return rows, src
        except Exception as e:
            last_error = e
    raise RuntimeError(f"All providers failed: {last_error}")

# --------------------------- CLI ---------------------------

def _cli():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pair", required=True)
    ap.add_argument(
        "--tf",
        required=True,
        choices=sorted(
            set(TF_TO_TD.keys())
            | set(TF_TO_YAHOO.keys())
            | set(TF_TO_AV.keys())
        ),
    )
    ap.add_argument("--bars", type=int, default=120)
    args = ap.parse_args()
    rows, src = get_ohlc(args.pair, args.tf, args.bars)
    print(f"{args.pair} via {src} rows={len(rows)} sample={rows[-1]}")


if __name__ == "__main__":
    _cli()

# accept "1d" as a daily alias for TwelveData
TF_TO_TD["1d"] = "1day"

# accept "1h"/"4h" as intraday aliases for TwelveData
TF_TO_TD["1h"] = "1h"
TF_TO_TD["4h"] = "4h"
