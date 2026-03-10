#!/usr/bin/env python3
"""
One-shot EUR/USD 15-minute OHLC fetcher (no loops).
Prefers TwelveData (uses TWELVEDATA_KEY), falls back to yfinance.
Writes: eurusd_m15.csv with columns:
timestamp,open,high,low,close,volume
"""

import os
import sys
import json
import time
import logging
from datetime import datetime, timezone

import pandas as pd

# yfinance is optional fallback
try:
    import yfinance as yf  # type: ignore
except Exception:
    yf = None

import requests

CSV_FILE = "eurusd_m15.csv"
TD_SYMBOL = "EUR/USD"
TD_INTERVAL = "15min"
TD_OUTPUTSIZE = "500"  # keep it reasonable on free plan

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
log = logging.getLogger("fetch")

def _coerce_float(x):
    try:
        return float(x)
    except Exception:
        return float(0.0)

def fetch_twelvedata():
    """Return DataFrame or None."""
    api_key = os.getenv("TWELVEDATA_KEY", "").strip()
    if not api_key:
        log.info("TWELVEDATA_KEY not set; skipping TwelveData.")
        return None

    url = "https://api.twelvedata.com/time_series"
    params = {
        "symbol": TD_SYMBOL,
        "interval": TD_INTERVAL,
        "outputsize": TD_OUTPUTSIZE,
        "timezone": "UTC",
        "apikey": api_key,
    }
    log.info("Fetching from TwelveData …")
    try:
        r = requests.get(url, params=params, timeout=30)
        r.raise_for_status()
        js = r.json()
        # Basic result validation
        if "status" in js and js["status"] == "error":
            log.error("TwelveData error: %s", js.get("message"))
            return None
        if "values" not in js:
            log.error("TwelveData unexpected payload: %s", list(js.keys()))
            return None

        rows = []
        for rec in js["values"]:
            # Keys are strings: datetime, open, high, low, close, (volume may be missing)
            ts_raw = rec.get("datetime")
            o = _coerce_float(rec.get("open"))
            h = _coerce_float(rec.get("high"))
            l = _coerce_float(rec.get("low"))
            c = _coerce_float(rec.get("close"))
            v = _coerce_float(rec.get("volume", 0.0))  # fill missing with 0.0

            # Normalize timestamp to timezone-aware UTC
            ts = pd.to_datetime(ts_raw, utc=True, errors="coerce")
            if pd.isna(ts):
                continue

            rows.append(
                {"timestamp": ts, "open": o, "high": h, "low": l, "close": c, "volume": v}
            )

        if not rows:
            log.error("TwelveData returned no usable candles.")
            return None

        df = pd.DataFrame(rows).sort_values("timestamp").reset_index(drop=True)
        log.info("TwelveData OK: %d candles.", len(df))
        return df

    except requests.exceptions.RequestException as e:
        log.error("HTTP error calling TwelveData: %s", e)
    except json.JSONDecodeError as e:
        log.error("TwelveData JSON error: %s", e)
    except Exception as e:
        log.error("TwelveData unexpected: %s", e)
    return None

def fetch_yfinance():
    """Return DataFrame or None."""
    if yf is None:
        log.info("yfinance not available; skipping fallback.")
        return None
    try:
        log.info("Fetching from yfinance (EURUSD=X, 7d, 15m) …")
        tic = yf.Ticker("EURUSD=X")
        data = tic.history(period="7d", interval="15m", auto_adjust=False, prepost=False, repair=True)
        if data is None or data.empty:
            log.error("yfinance returned empty dataset.")
            return None

        data = data.dropna()
        if data.empty:
            log.error("yfinance dataset empty after dropna.")
            return None

        # Normalize columns to our schema
        data = data.rename(
            columns={"Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"}
        )
        data["timestamp"] = pd.to_datetime(data.index, utc=True)
        # Some forex feeds set volume to NaN — coerce to 0.0
        if "volume" not in data.columns:
            data["volume"] = 0.0
        else:
            data["volume"] = data["volume"].fillna(0.0).astype(float)

        df = data[["timestamp", "open", "high", "low", "close", "volume"]].copy()
        df = df.sort_values("timestamp").reset_index(drop=True)
        log.info("yfinance OK: %d candles.", len(df))
        return df
    except Exception as e:
        log.error("yfinance failed: %s", e)
        return None

def save_csv(df: pd.DataFrame):
    # Ensure correct order + types
    out = df.copy()
    out["timestamp"] = pd.to_datetime(out["timestamp"], utc=True)
    for col in ["open", "high", "low", "close", "volume"]:
        out[col] = out[col].astype(float)
    out = out.sort_values("timestamp")
    out.to_csv(CSV_FILE, index=False, columns=["timestamp", "open", "high", "low", "close", "volume"], float_format="%.5f")
    log.info("Saved %d rows -> %s", len(out), CSV_FILE)
    # Small sample to stdout
    print("\n== SAMPLE (head) ==")
    print(out.head().to_string(index=False))
    print("\n== SAMPLE (tail) ==")
    print(out.tail().to_string(index=False))

def main():
    # 1) Try TwelveData first (uses your TWELVEDATA_KEY)
    df = fetch_twelvedata()
    # 2) Fallback to yfinance if needed
    if df is None:
        df = fetch_yfinance()

    if df is None or len(df) < 10:
        log.error("No sufficient data from any source. Exiting.")
        sys.exit(2)

    save_csv(df)
    log.info("Done.")

if __name__ == "__main__":
    main()
