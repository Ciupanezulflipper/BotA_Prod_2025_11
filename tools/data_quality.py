from __future__ import annotations
import os
import pandas as pd
from typing import Tuple

# --- TF mapping -------------------------------------------------------------
_TF_MIN = {
    "M1": 1, "M5": 5, "M15": 15, "M30": 30,
    "H1": 60, "H4": 240, "D1": 1440,
}

def tf_to_minutes(tf: str) -> int:
    """Timeframe string -> minutes. Accepts forms like M15, H1, 15m, 1h, 60M."""
    s = (tf or "").strip().upper()
    if not s:
        raise ValueError("timeframe missing")

    if s in _TF_MIN:
        return _TF_MIN[s]

    # numeric forms: 15M, 30M, 1H, 4H, 60M, etc.
    if s.endswith("M") and s[:-1].isdigit():
        return int(s[:-1])
    if s.endswith("H") and s[:-1].isdigit():
        return int(s[:-1]) * 60

    # common alternates
    alt = {"1HOUR": 60, "4HOUR": 240, "15MIN": 15, "30MIN": 30, "1DAY": 1440}
    if s in alt:
        return alt[s]

    raise ValueError(f"unknown timeframe: {tf}")

def _tol() -> float:
    # allow weekend/holiday gaps; default 35%
    try:
        return float(os.environ.get("BOTA_TIMESPAN_TOL_PCT", "0.35"))
    except Exception:
        return 0.35

# --- main check -------------------------------------------------------------
def validate_ohlc(df: pd.DataFrame, tf: str, min_bars: int = 200) -> Tuple[bool, str]:
    """
    Returns (ok, msg). Checks:
      - enough rows
      - total span roughly equals (rows-1)*tf_minutes within tolerance
    """
    if df is None or len(df) == 0:
        return False, "empty dataframe"

    idx = df.index
    if not isinstance(idx, pd.DatetimeIndex):
        try:
            idx = pd.to_datetime(df.index, utc=True, errors="coerce")
        except Exception:
            return False, "index not datetime-like"

    if idx.isna().any():
        return False, "index contains NaT"

    rows = len(idx)
    need = int(os.environ.get("BOTA_MIN_BARS", min_bars))
    if rows < need:
        return False, f"rows[{rows}<{need}] not enough bars"

    tf_min = int(os.environ.get("BOTA_TF_MINUTES", tf_to_minutes(tf)))
    span_min = int((idx.max() - idx.min()).total_seconds() // 60)
    exp_min = max(0, (rows - 1) * tf_min)

    tol = _tol()
    lo = int(exp_min * (1 - tol))
    hi = int(exp_min * (1 + tol))

    if not (lo <= span_min <= hi):
        return False, (
            f"Time span anomaly: {span_min} min for {rows} bars "
            f"(expected ~{exp_min} min ±{int(tol*100)}%)"
        )

    return True, "ok"
