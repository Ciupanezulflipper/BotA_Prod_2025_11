# BotA/tools/ohlc_fix.py
# Robustly convert various provider payloads to a pandas OHLC DataFrame

from __future__ import annotations
from typing import Any, Tuple
import pandas as pd

CANDLES_COLS = ["time", "open", "high", "low", "close", "volume"]

def _coerce_numeric(df: pd.DataFrame) -> pd.DataFrame:
    for c in ("open", "high", "low", "close", "volume"):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df

def _finalize(df: pd.DataFrame) -> pd.DataFrame:
    if "time" not in df.columns:
        raise ValueError("Missing 'time' column after normalization")
    df["time"] = pd.to_datetime(df["time"], errors="coerce", utc=True)
    df = df.sort_values("time").dropna(subset=["time", "open", "high", "low", "close"])
    # standard column order if present
    cols = [c for c in CANDLES_COLS if c in df.columns]
    return df[cols].reset_index(drop=True)

def to_dataframe(obj: Any) -> pd.DataFrame:
    """
    Accepts:
      - pandas.DataFrame with OHLC columns
      - list[dict] like TwelveData [{'datetime','open','high','low','close',('volume')}]
      - dict arrays like Finnhub {'t','o','h','l','c',('v')}
      - list[list] or list[tuple] [time,open,high,low,close,(volume)]
    Returns a pandas DataFrame with columns time,open,high,low,close,(volume)
    """
    # Already a DataFrame
    if isinstance(obj, pd.DataFrame):
        df = obj.copy()
        # unify a few common time column spellings
        if "datetime" in df.columns and "time" not in df.columns:
            df = df.rename(columns={"datetime": "time"})
        return _finalize(_coerce_numeric(df))

    # TwelveData style: list of dicts
    if isinstance(obj, list) and (len(obj) == 0 or isinstance(obj[0], dict)):
        df = pd.DataFrame(obj)
        rename = {}
        if "datetime" in df.columns: rename["datetime"] = "time"
        if "t" in df.columns:        rename["t"] = "time"
        if "o" in df.columns:        rename["o"] = "open"
        if "h" in df.columns:        rename["h"] = "high"
        if "l" in df.columns:        rename["l"] = "low"
        if "c" in df.columns:        rename["c"] = "close"
        if "v" in df.columns:        rename["v"] = "volume"
        df = df.rename(columns=rename)
        return _finalize(_coerce_numeric(df))

    # Finnhub style: dict of arrays {t,o,h,l,c,(v)}
    if isinstance(obj, dict) and all(k in obj for k in ("t", "o", "h", "l", "c")):
        data = {
            "time":   obj.get("t", []),
            "open":   obj.get("o", []),
            "high":   obj.get("h", []),
            "low":    obj.get("l", []),
            "close":  obj.get("c", []),
        }
        if "v" in obj:
            data["volume"] = obj.get("v", [])
        df = pd.DataFrame(data)
        return _finalize(_coerce_numeric(df))

    # Generic: list of lists/tuples [time, open, high, low, close, (volume)]
    if isinstance(obj, list) and len(obj) and isinstance(obj[0], (list, tuple)):
        width = len(obj[0])
        cols = CANDLES_COLS[:width]
        df = pd.DataFrame(obj, columns=cols)
        return _finalize(_coerce_numeric(df))

    # Empty list → empty valid frame
    if isinstance(obj, list) and len(obj) == 0:
        return pd.DataFrame(columns=CANDLES_COLS)

    raise TypeError(f"Unrecognized bars payload type: {type(obj)}")

def get_df(providers_mod, pair: str, tf: str, bars: int = 200) -> Tuple[pd.DataFrame, str]:
    """
    Wrapper around providers.get_ohlc(...) that guarantees a DataFrame.
    Returns (df, source)
    """
    raw, source = providers_mod.get_ohlc(pair, tf, bars)
    df = to_dataframe(raw)
    return df, source
