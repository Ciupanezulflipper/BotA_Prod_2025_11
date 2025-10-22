# data/ohlcv.py  — TwelveData-only, clean OHLCV with on-grid timestamps
from __future__ import annotations
import os
import requests
import datetime as dt

# ensure env + aliases are loaded (TWELVEDATA_API_KEY / TWELVE_DATA_API_KEY, etc.)
from tools import env_loader as _  # noqa: F401


def _get_any(*names: str) -> str:
    for n in names:
        v = os.getenv(n)
        if v:
            return v.strip()
    return ""


def _tf_map(tf: str) -> tuple[str, int]:
    tf = (tf or "").strip().lower()
    aliases = {
        "m1": "1min", "1m": "1min",
        "m5": "5min", "5m": "5min",
        "m15": "15min", "15m": "15min",
        "m30": "30min", "30m": "30min",
        "h1": "1h", "1h": "1h",
        "h4": "4h", "4h": "4h",
        "d1": "1day", "1d": "1day",
    }
    iv = aliases.get(tf, tf) or "15min"
    delta = {
        "1min": 60, "5min": 300, "15min": 900, "30min": 1800,
        "1h": 3600, "4h": 14400, "1day": 86400,
    }.get(iv, 900)
    return iv, delta


def _norm_pair(sym: str) -> str:
    s = (sym or "").strip().upper()
    if len(s) == 6 and "/" not in s:
        return f"{s[:3]}/{s[3:]}"
    return s


def fetch(symbol: str = "EURUSD", tf: str = "5min", limit: int = 200):
    """
    Return a list of dicts: [{t:int(epoch s UTC aligned to TF grid), o,h,l,c,v:float}, ...]
    Oldest -> newest. Strictly aligned timestamps to avoid spacing anomalies.
    """
    key = _get_any("TWELVEDATA_API_KEY", "TWELVE_DATA_API_KEY", "TWELVEDATA_KEY", "TD_KEY")
    if not key:
        return []

    interval, delta = _tf_map(tf)
    sym = _norm_pair(symbol)

    url = "https://api.twelvedata.com/time_series"
    params = {
        "symbol": sym,
        "interval": interval,
        "outputsize": int(limit),
        "apikey": key,
    }

    try:
        r = requests.get(url, params=params, timeout=15)
        j = r.json()
    except Exception:
        return []

    if j.get("status") != "ok" or "values" not in j:
        return []

    vals = list(reversed(j["values"]))  # oldest -> newest
    out = []
    for it in vals:
        # TwelveData returns 'datetime' like "2025-10-09 19:00:00" (UTC)
        ts = dt.datetime.fromisoformat(it["datetime"].replace(" ", "T")).replace(tzinfo=dt.timezone.utc)
        t = int(ts.timestamp())
        # align to exact TF grid (floor), e.g., H1 -> :00, M15 -> :00/:15/:30/:45
        t = t - (t % delta)

        out.append({
            "t": t,
            "o": float(it["open"]),
            "h": float(it["high"]),
            "l": float(it["low"]),
            "c": float(it["close"]),
            "v": float(it.get("volume") or 0.0),
        })

    return out
