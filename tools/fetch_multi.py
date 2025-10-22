#!/usr/bin/env python3
"""
EURUSD 15m data fetcher with robust fallbacks
Order: TwelveData -> Finnhub -> EODHD -> Polygon -> Yahoo
Output: eurusd_m15.csv (timestamp,open,high,low,close,volume)
"""

import os, sys, time, math, json, logging
from datetime import datetime, timedelta, timezone
import requests
import pandas as pd

# ---------- logging ----------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
log = logging.getLogger("fetch_multi")

CSV_FILE = "eurusd_m15.csv"
PAIR      = "EURUSD"        # canonical
TZ_UTC    = timezone.utc
NOW       = datetime.now(TZ_UTC)
FROM_TS   = int((NOW - timedelta(days=7)).timestamp())  # ~7 days for 500x 15m bars
TO_TS     = int(NOW.timestamp())
TIMEOUT   = 25

def _std_df(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure correct order, types, sizes; final polish."""
    df = df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    num_cols = ["open","high","low","close","volume"]
    for c in num_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna().sort_values("timestamp")
    # keep last 500 bars
    df = df.tail(500)
    # ISO8601 with timezone +00:00
    df["timestamp"] = df["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S+00:00")
    return df[["timestamp","open","high","low","close","volume"]]

# ---------- Provider 1: TwelveData ----------
def fetch_twelvedata():
    key = os.getenv("TWELVEDATA_KEY") or os.getenv("TWELVE_DATA_API_KEY")
    if not key:
        log.info("TwelveData: no API key set; skipping.")
        return None
    url = "https://api.twelvedata.com/time_series"
    params = {
        "symbol": "EUR/USD",
        "interval": "15min",
        "outputsize": "500",
        "apikey": key,
        "format": "JSON"
    }
    try:
        r = requests.get(url, params=params, timeout=TIMEOUT)
        r.raise_for_status()
        js = r.json()
        if "values" not in js:
            log.error("TwelveData: unexpected response: %s", js)
            return None
        vals = js["values"]
        df = pd.DataFrame(vals)
        # twelvedata returns newest-first; ensure datetime asc
        df["datetime"] = pd.to_datetime(df["datetime"], utc=True)
        df = df.sort_values("datetime")
        df.rename(columns={
            "datetime":"timestamp",
            "open":"open","high":"high","low":"low","close":"close",
            "volume":"volume"
        }, inplace=True)
        # volume may be missing/strings
        if "volume" not in df.columns:
            df["volume"] = 0.0
        return _std_df(df)
    except Exception as e:
        log.error("TwelveData error: %s", e)
        return None

# ---------- Provider 2: Finnhub ----------
def fetch_finnhub():
    key = os.getenv("FINNHUB_API_KEY")
    if not key:
        log.info("Finnhub: no API key set; skipping.")
        return None
    # Free plans sometimes lack forex intraday; handle 403/permission errors gracefully
    url = "https://finnhub.io/api/v1/forex/candle"
    params = {
        "symbol": "OANDA:EUR_USD",
        "resolution": "15",
        "from": FROM_TS,
        "to": TO_TS,
        "token": key
    }
    try:
        r = requests.get(url, params=params, timeout=TIMEOUT)
        if r.status_code != 200:
            log.error("Finnhub HTTP %s: %s", r.status_code, r.text[:200])
            return None
        js = r.json()
        if js.get("s") != "ok":
            log.error("Finnhub returned: %s", js)
            return None
        # js fields: t,o,h,l,c,v arrays
        df = pd.DataFrame({
            "timestamp": pd.to_datetime(js["t"], unit="s", utc=True),
            "open":  js["o"],
            "high":  js["h"],
            "low":   js["l"],
            "close": js["c"],
            "volume": js.get("v", [0]*len(js["t"]))
        })
        return _std_df(df)
    except Exception as e:
        log.error("Finnhub error: %s", e)
        return None

# ---------- Provider 3: EODHD ----------
def fetch_eodhd():
    key = os.getenv("EODHD_API_KEY")
    if not key:
        log.info("EODHD: no API key set; skipping.")
        return None
    # EODHD intraday: /api/intraday/EUR-USD?interval=15m&from=YYYY-MM-DD&to=YYYY-MM-DD
    url = f"https://eodhd.com/api/intraday/EUR-USD"
    params = {
        "interval": "15m",
        "from": (NOW - timedelta(days=7)).strftime("%Y-%m-%d"),
        "to": NOW.strftime("%Y-%m-%d"),
        "api_token": key,
        "fmt": "json"
    }
    try:
        r = requests.get(url, params=params, timeout=TIMEOUT)
        r.raise_for_status()
        js = r.json()
        if not isinstance(js, list) or not js:
            log.error("EODHD: unexpected response: %s", str(js)[:200])
            return None
        df = pd.DataFrame(js)
        # columns: datetime, open, high, low, close, volume
        if "datetime" not in df.columns:
            log.error("EODHD: missing datetime in response.")
            return None
        df.rename(columns={"datetime":"timestamp"}, inplace=True)
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        if "volume" not in df.columns:
            df["volume"] = 0.0
        return _std_df(df)
    except Exception as e:
        log.error("EODHD error: %s", e)
        return None

# ---------- Provider 4: Polygon ----------
def fetch_polygon():
    key = os.getenv("POLYGON_API_KEY")
    if not key:
        log.info("Polygon: no API key set; skipping.")
        return None
    # Polygon aggregates for forex: ticker "C:EURUSD"
    date_from = (NOW - timedelta(days=7)).strftime("%Y-%m-%d")
    date_to   = NOW.strftime("%Y-%m-%d")
    url = f"https://api.polygon.io/v2/aggs/ticker/C:EURUSD/range/15/minute/{date_from}/{date_to}"
    params = {
        "adjusted": "true",
        "sort": "asc",
        "limit": 50000,
        "apiKey": key,
    }
    try:
        r = requests.get(url, params=params, timeout=TIMEOUT)
        if r.status_code != 200:
            log.error("Polygon HTTP %s: %s", r.status_code, r.text[:200])
            return None
        js = r.json()
        res = js.get("results") or []
        if not res:
            log.error("Polygon: empty results: %s", str(js)[:200])
            return None
        # results have t (ms), o,h,l,c,v
        df = pd.DataFrame(res)
        df.rename(columns={"t":"ts","o":"open","h":"high","l":"low","c":"close","v":"volume"}, inplace=True)
        df["timestamp"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
        return _std_df(df[["timestamp","open","high","low","close","volume"]])
    except Exception as e:
        log.error("Polygon error: %s", e)
        return None

# ---------- Provider 5 (last resort): Yahoo ----------
def fetch_yahoo():
    try:
        import yfinance as yf
    except Exception as e:
        log.info("Yahoo/yfinance not available: %s", e)
        return None
    try:
        tk = yf.Ticker("EURUSD=X")
        df = tk.history(period="7d", interval="15m", auto_adjust=False, prepost=False, repair=True)
        if df is None or df.empty:
            log.error("Yahoo: empty dataframe.")
            return None
        df = df.dropna()
        if len(df) < 10:
            log.error("Yahoo: too few rows: %d", len(df))
            return None
        df = df.reset_index().rename(columns={"Datetime":"timestamp","Open":"open","High":"high","Low":"low","Close":"close","Volume":"volume"})
        df["volume"] = 0.0 if "volume" not in df else df["volume"].fillna(0.0)
        return _std_df(df[["timestamp","open","high","low","close","volume"]])
    except Exception as e:
        log.error("Yahoo error: %s", e)
        return None

PROVIDERS = [
    ("TwelveData", fetch_twelvedata),
    ("Finnhub",    fetch_finnhub),
    ("EODHD",      fetch_eodhd),
    ("Polygon",    fetch_polygon),
    ("Yahoo",      fetch_yahoo),   # last resort
]

def save_csv(df: pd.DataFrame):
    df.to_csv(CSV_FILE, index=False, float_format="%.5f")
    log.info("Saved %d rows -> %s", len(df), CSV_FILE)
    print("== HEAD ==")
    print(df.head().to_string(index=False))
    print("== TAIL ==")
    print(df.tail().to_string(index=False))

def main():
    log.info("[START] fetch_multi | 15m %s -> %s", PAIR, CSV_FILE)
    for name, fn in PROVIDERS:
        log.info("[FETCH] Trying %s ...", name)
        df = fn()
        if df is not None and len(df) >= 100:
            log.info("%s OK: %d rows", name, len(df))
            save_csv(df)
            return 0
        else:
            log.warning("%s failed or insufficient rows.", name)
    log.error("All providers failed. No data written.")
    return 1

if __name__ == "__main__":
    sys.exit(main())
