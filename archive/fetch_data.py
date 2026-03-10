import os
import json
import time
import requests
import pandas as pd
import datetime as dt
from datetime import timedelta  # kept for compatibility (even if unused)

# -----------------------------
# Config & Paths
# -----------------------------
BASE = os.getenv("BOT_BASE", os.path.expanduser("~/bot-a"))
RUN_DIR = os.path.join(BASE, "run")
USAGE_FILE = os.path.join(RUN_DIR, "provider_usage.json")
os.makedirs(RUN_DIR, exist_ok=True)

# -----------------------------
# UTC helpers (timezone-aware; avoids datetime.utcnow() DeprecationWarning)
# IMPORTANT: preserve all existing output string formats.
# -----------------------------
UTC = getattr(dt, "UTC", dt.timezone.utc)


def _utcnow() -> dt.datetime:
    return dt.datetime.now(UTC)


def _utc_hm() -> str:
    # Preserve EXACT prior format used in logs: "UTC HH:MM"
    return _utcnow().strftime("%H:%M")


# API keys (from .env exported to environment)
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")
TWELVEDATA_API_KEY = os.getenv("TWELVE_DATA_API_KEY")
ALPHAVANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY")
EODHD_API_KEY = os.getenv("EODHD_API_KEY")
POLYGON_API_KEY = os.getenv("POLYGON_API_KEY")

# Per-minute limits (safe defaults; override in .env if needed)
LIMITS_PER_MIN = {
    "twelvedata": int(os.getenv("TWELVEDATA_RATE_PER_MIN", "8")),  # free tier ~8/min
    "finnhub": int(os.getenv("FINNHUB_RATE_PER_MIN", "30")),  # conservative
    "alphavantage": int(os.getenv("ALPHAVANTAGE_RATE_PER_MIN", "5")),  # free tier 5/min
    "yahoo": 9999,  # yfinance (no key) – we still count, but don’t throttle
    "polygon": int(os.getenv("POLYGON_RATE_PER_MIN", "5")),
    "eodhd": int(os.getenv("EODHD_RATE_PER_MIN", "10")),
}

# Provider order
def available_providers():
    return ["twelvedata", "finnhub", "alphavantage", "yahoo", "polygon", "eodhd"]


# -----------------------------
# Logging helper
# -----------------------------
def log(msg: str):
    """Safe log that won’t be mistaken for a shell command."""
    print(f"LOG {msg}")


# -----------------------------
# Usage counters (per-minute)
# -----------------------------
def _epoch_minute(ts=None):
    if ts is None:
        ts = time.time()
    return int(ts // 60)


def _load_usage():
    try:
        with open(USAGE_FILE, "r") as f:
            obj = json.load(f)
            # prune old minutes (keep last 120 minutes for safety)
            nowm = _epoch_minute()
            for prov in list(obj.keys()):
                for m in list(obj[prov].keys()):
                    if int(m) < nowm - 120:
                        del obj[prov][m]
            return obj
    except Exception:
        return {}


def _save_usage(obj):
    try:
        with open(USAGE_FILE, "w") as f:
            json.dump(obj, f, indent=2, sort_keys=True)
    except Exception as e:
        log(f"USAGE save warn: {e}")


def _get_minute_count(provider):
    usage = _load_usage()
    m = str(_epoch_minute())
    return usage.get(provider, {}).get(m, 0)


def _inc_minute_count(provider):
    usage = _load_usage()
    m = str(_epoch_minute())
    usage.setdefault(provider, {})
    usage[provider][m] = usage[provider].get(m, 0) + 1
    _save_usage(usage)


def _can_call(provider):
    limit = LIMITS_PER_MIN.get(provider, 5)
    cnt = _get_minute_count(provider)
    return cnt < limit, cnt, limit


# -----------------------------
# Symbol helpers per provider
# -----------------------------
def _split_fx(sym: str):
    # EURUSD -> ("EUR","USD") ; XAUUSD -> ("XAU","USD")
    base = sym[:-3]
    quote = sym[-3:]
    return base, quote


def symbol_for_twelvedata(sym: str):
    try:
        b, q = _split_fx(sym)
        return f"{b}/{q}"
    except Exception:
        return sym


def symbol_for_finnhub(sym: str):
    try:
        b, q = _split_fx(sym)
        return f"OANDA:{b}_{q}"
    except Exception:
        return sym


def symbol_for_alphavantage(sym: str):
    return sym  # AV likes 'EURUSD', 'XAUUSD'


# -----------------------------
# Provider implementations
# -----------------------------
def fetch_from_twelvedata(symbol, interval, limit=100):
    if not TWELVEDATA_API_KEY:
        raise RuntimeError("TWELVEDATA_API_KEY missing")
    sym = symbol_for_twelvedata(symbol)
    url = (
        "https://api.twelvedata.com/time_series"
        f"?symbol={sym}&interval={interval}&outputsize={limit}&apikey={TWELVEDATA_API_KEY}"
    )
    r = requests.get(url, timeout=15)
    data = r.json()
    if "values" not in data:
        raise RuntimeError(f"twelvedata: {data.get('message','no data')}")
    df = pd.DataFrame(data["values"])
    # TwelveData returns strings; rename/convert columns
    df["time"] = pd.to_datetime(df["datetime"])
    df = df.rename(
        columns={
            "open": "open",
            "high": "high",
            "low": "low",
            "close": "close",
            "volume": "volume",
        }
    )
    df = df.drop(
        columns=[
            c
            for c in df.columns
            if c not in ["time", "open", "high", "low", "close", "volume"]
        ]
    )
    # numeric
    for c in ["open", "high", "low", "close", "volume"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.set_index("time").sort_index()
    return df


def fetch_from_finnhub(symbol, interval, limit=100):
    if not FINNHUB_API_KEY:
        raise RuntimeError("FINNHUB_API_KEY missing")
    res_map = {"1h": "60", "1d": "D"}
    resolution = res_map.get(interval, "60")

    # timezone-aware UTC epoch seconds (replaces deprecated datetime.utcnow())
    to_ts = int(_utcnow().timestamp())

    # a bit wider window to ensure enough bars
    seconds = 3600 if resolution == "60" else 86400
    from_ts = to_ts - seconds * (limit + 5)

    sym = symbol_for_finnhub(symbol)
    url = (
        "https://finnhub.io/api/v1/stock/candle"
        f"?symbol={sym}&resolution={resolution}&from={from_ts}&to={to_ts}&token={FINNHUB_API_KEY}"
    )
    r = requests.get(url, timeout=15)
    data = r.json()
    if data.get("s") != "ok":
        raise RuntimeError(f"finnhub: {data.get('s','fail')}")
    df = (
        pd.DataFrame(
            {
                "time": pd.to_datetime(data["t"], unit="s"),
                "open": data["o"],
                "high": data["h"],
                "low": data["l"],
                "close": data["c"],
                "volume": data["v"],
            }
        )
        .set_index("time")
        .sort_index()
    )
    return df.tail(limit)


def fetch_from_alphavantage(symbol, interval, limit=100):
    if not ALPHAVANTAGE_API_KEY:
        raise RuntimeError("ALPHAVANTAGE_API_KEY missing")
    iv_map = {"1h": "60min", "1d": "Daily"}
    func = "TIME_SERIES_INTRADAY" if interval == "1h" else "TIME_SERIES_DAILY"
    url = (
        "https://www.alphavantage.co/query"
        f"?function={func}&symbol={symbol_for_alphavantage(symbol)}"
        f"&interval={iv_map.get(interval,'60min')}&apikey={ALPHAVANTAGE_API_KEY}"
    )
    r = requests.get(url, timeout=20)
    data = r.json()
    # AV structures the payload with a last key like 'Time Series (60min)'
    keys = [k for k in data.keys() if "Time Series" in k]
    if not keys:
        raise RuntimeError(
            f"alphavantage: {data.get('Note') or data.get('Error Message') or 'no series'}"
        )
    ts = data[keys[0]]
    df = pd.DataFrame(ts).T
    df.index = pd.to_datetime(df.index)
    df = df.rename(
        columns={
            "1. open": "open",
            "2. high": "high",
            "3. low": "low",
            "4. close": "close",
            "5. volume": "volume",
        }
    )
    for c in ["open", "high", "low", "close", "volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.sort_index().tail(limit)
    return df


# -----------------------------
# Public API
# -----------------------------
def get_ohlc(symbol, interval="1h", limit=100, provider=None):
    """
    Pull OHLC with provider auto-rotation and per-minute rate limiting.
    """
    order = [provider] if provider else available_providers()
    errors = []
    for p in order:
        ok, used, cap = _can_call(p)
        if not ok:
            log(f"UTC {_utc_hm()} | SKIP {p.upper()} rate {used}/{cap} this minute")
            continue

        try:
            log(
                f"UTC {_utc_hm()} | Trying {p.upper()} {symbol} interval={interval} size~{limit}"
            )
            if p == "twelvedata":
                df = fetch_from_twelvedata(symbol, interval, limit)
            elif p == "finnhub":
                df = fetch_from_finnhub(symbol, interval, limit)
            elif p == "alphavantage":
                df = fetch_from_alphavantage(symbol, interval, limit)
            else:
                raise RuntimeError(f"{p}: not implemented")

            _inc_minute_count(p)
            log(f"{p.upper()} OK {symbol} rows={len(df)} last={df.index[-1]}")
            return df

        except Exception as e:
            _inc_minute_count(p)  # still count the attempt
            msg = f"{p}: {e}"
            log(f"{p.upper()} FAIL {msg}")
            errors.append(msg)

    raise RuntimeError("All providers failed: " + " | ".join(errors))


def available_usage_snapshot():
    """Return a dict of {provider: {minute_epoch: count}} (recent window)."""
    return _load_usage()
