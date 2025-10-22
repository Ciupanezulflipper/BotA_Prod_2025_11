# ~/bot-a/tools/tech_engine.py
# Lightweight tech engine with low limits for free-tier data sources.
# Uses the rotating fetcher (data_rotator.get_ohlc_rotating).

from __future__ import annotations
import math
import datetime as dt
from typing import Dict, Tuple, Any

import pandas as pd
import numpy as np

from tools.data_rotator import get_ohlc_rotating


# --- Runtime-safe LOW LIMITS (free tier friendly) ----------------------------
H1_LIMIT  = 20     # was 120 – trimmed to stay under per-minute quotas
H4_LIMIT  = 20     # was 120 – same reasoning
D1_LIMIT  = 100    # daily is cheap; leave some history for ATR/RSI

# -----------------------------------------------------------------------------


def _ema(s: pd.Series, span: int) -> pd.Series:
    return s.ewm(span=span, adjust=False).mean()


def _rsi(s: pd.Series, period: int = 14) -> pd.Series:
    # Wilder's RSI
    delta = s.diff()
    gain = (delta.clip(lower=0)).ewm(alpha=1/period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1/period, adjust=False).mean()
    rs = gain / (loss + 1e-12)
    return 100 - (100 / (1 + rs))


def _macd(s: pd.Series, fast=12, slow=26, signal=9) -> Tuple[pd.Series, pd.Series, pd.Series]:
    macd = _ema(s, fast) - _ema(s, slow)
    sig = _ema(macd, signal)
    hist = macd - sig
    return macd, sig, hist


def _atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    hl = df["high"] - df["low"]
    hc = (df["high"] - df["close"].shift()).abs()
    lc = (df["low"] - df["close"].shift()).abs()
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    return tr.ewm(alpha=1/period, adjust=False).mean()


def fetch(symbol: str, interval: str, limit: int) -> Tuple[pd.DataFrame, str]:
    """
    Pull OHLC with automatic provider rotation (and rate skipping).
    Returns (DataFrame, provider_used). DataFrame indexed by datetime (UTC).
    """
    df, provider = get_ohlc_rotating(symbol, interval, limit=limit)
    # normalize columns if needed
    cols = [c.lower() for c in df.columns]
    rename = {}
    for c in ["Open", "High", "Low", "Close", "Volume"]:
        if c in df.columns:
            rename[c] = c.lower()
    if rename:
        df = df.rename(columns=rename)
    return df, provider


def _tf_metrics(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Compute indicators for a timeframe DataFrame (expects open/high/low/close).
    Returns latest values.
    """
    df = df.copy()

    df["ema9"]  = _ema(df["close"], 9)
    df["ema21"] = _ema(df["close"], 21)
    df["rsi14"] = _rsi(df["close"], 14)
    df["rsi21"] = _rsi(df["close"], 21)
    df["macd"], df["macd_sig"], df["macd_hist"] = _macd(df["close"], 12, 26, 9)
    df["atr14"] = _atr(df, 14)

    last = df.iloc[-1]

    # Quick “vote” for trend on this timeframe
    vote = 0
    vote += 1 if last["close"] > last["ema21"] else 0
    vote += 1 if last["ema9"] > last["ema21"] else 0
    vote += 1 if last["macd_hist"] > 0 else 0
    vote += 1 if last["rsi14"] > 50 else 0

    return {
        "close": float(last["close"]),
        "ema9": float(last["ema9"]),
        "ema21": float(last["ema21"]),
        "ema50": float(_ema(df["close"], 50).iloc[-1]) if len(df) >= 50 else float(last["ema21"]),
        "rsi14": float(last["rsi14"]),
        "rsi21": float(last["rsi21"]),
        "macd": float(last["macd"]),
        "macd_sig": float(last["macd_sig"]),
        "macd_hist": float(last["macd_hist"]),
        "atr14": float(last["atr14"]),
        "vote": int(vote),
    }


def _bucket_and_score(tf1h: Dict[str, Any], tf4h: Dict[str, Any], tf1d: Dict[str, Any]) -> Tuple[str, float, int]:
    """
    Simple multi-timeframe bucket and score out of 10.
    """
    votes = tf1h["vote"] + tf4h["vote"] + tf1d["vote"]  # 0..12
    # rescale to 0..10
    tech_score = round(10 * votes / 12, 1)

    # Bucket
    bullish = sum([
        tf1h["close"] > tf1h["ema21"],
        tf4h["close"] > tf4h["ema21"],
        tf1d["close"] > tf1d["ema21"],
        tf1h["macd_hist"] > 0,
        tf4h["macd_hist"] > 0,
        tf1d["macd_hist"] > 0,
    ])

    bearish = sum([
        tf1h["close"] < tf1h["ema21"],
        tf4h["close"] < tf4h["ema21"],
        tf1d["close"] < tf1d["ema21"],
        tf1h["macd_hist"] < 0,
        tf4h["macd_hist"] < 0,
        tf1d["macd_hist"] < 0,
    ])

    if bullish >= bearish + 2:
        bucket = "BUY"
    elif bearish >= bullish + 2:
        bucket = "SELL"
    else:
        bucket = "HOLD"

    return bucket, tech_score, votes


def _levels(entry: float, direction: str, atr: float, symbol: str) -> Tuple[float, float]:
    """
    Derive TP/SL using ATR (half ATR). For FX (like EURUSD) ATR is in price units.
    """
    # Be conservative on free tiers: TP/SL = 0.5 * ATR14 (daily)
    delta = 0.5 * atr
    if direction == "BUY":
        tp = entry + delta
        sl = entry - delta
    elif direction == "SELL":
        tp = entry - delta
        sl = entry + delta
    else:
        tp = entry
        sl = entry
    # Round to 5 decimals for major FX pairs
    return (round(tp, 5), round(sl, 5))


def analyse(symbol: str) -> Dict[str, Any]:
    """
    Public API: compute multi-timeframe tech for `symbol`.
    Returns a compact dict used by final_runner/combine_runner.
    """
    # pull data with low limits
    h1_df, prov_h1 = fetch(symbol, "1h",  H1_LIMIT)
    h4_df, prov_h4 = fetch(symbol, "4h",  H4_LIMIT)
    d1_df, prov_d1 = fetch(symbol, "1d",  D1_LIMIT)

    tf1h = _tf_metrics(h1_df)
    tf4h = _tf_metrics(h4_df)
    tf1d = _tf_metrics(d1_df)

    bucket, tech_score, votes = _bucket_and_score(tf1h, tf4h, tf1d)

    entry_price = tf1h["close"]  # use latest 1h close as entry reference
    tp, sl = _levels(entry_price, bucket, tf1d["atr14"], symbol)

    return {
        "tech_bucket": bucket,
        "tech_score": tech_score,
        "entry": round(entry_price, 5),
        "tp": tp,
        "sl": sl,
        "mtf": {
            "1h": tf1h | {"provider": prov_h1},
            "4h": tf4h | {"provider": prov_h4},
            "1d": tf1d | {"provider": prov_d1},
        },
        "vote": votes,
    }


# Quick local test:
if __name__ == "__main__":
    out = analyse("EURUSD")
    print("*TECH*", out["tech_bucket"], "| score:", out["tech_score"])
    print("*Entry/TP/SL*", out["entry"], out["tp"], out["sl"])
    print("*1h*", out["mtf"]["1h"])
    print("*4h*", out["mtf"]["4h"])
    print("*1d*", out["mtf"]["1d"])
