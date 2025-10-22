#!/usr/bin/env python3
# data_quality.py — OHLC sanity checks for runner_confluence

from datetime import datetime, timezone
from typing import Dict, List, Tuple
import pandas as pd

def validate_ohlc(
    rows: List[Dict],
    timeframe: str,
    max_staleness_min: int = 45,
    min_atr_pips: float = 5.0,
    atr_value_pips: float | None = None,
) -> Tuple[bool, List[str]]:
    errors: List[str] = []

    if not rows:
        return False, ["No data returned"]

    df = pd.DataFrame(rows)
    required = ["time", "open", "high", "low", "close"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        return False, [f"Missing columns: {missing}"]

    df["time"] = pd.to_datetime(df["time"], utc=True, errors="coerce")
    df = df.dropna(subset=["time"]).sort_values("time")
    if df.empty:
        return False, ["No valid timestamps"]

    # 1) Staleness
    last_bar_time = df["time"].iloc[-1]
    age_min = (datetime.now(timezone.utc) - last_bar_time).total_seconds() / 60
    if age_min > max_staleness_min:
        errors.append(f"Data stale: last bar {age_min:.1f} min old (max {max_staleness_min})")

    # 2) Duplicates
    if df["time"].duplicated().any():
        errors.append(f"Duplicate timestamps: {int(df['time'].duplicated().sum())} bars")

    # 3) Time gaps (approximate)
    tf_m = _parse_timeframe_minutes(timeframe)
    if tf_m:
        expected_span = (len(df) - 1) * tf_m
        actual_span = (df["time"].iloc[-1] - df["time"].iloc[0]).total_seconds() / 60
        if expected_span > 0:
            err_pct = abs(actual_span - expected_span) / expected_span * 100
            if err_pct > 10:
                errors.append(
                    f"Time span anomaly: {actual_span:.0f} min for {len(df)} bars "
                    f"(expected {expected_span:.0f} min, {err_pct:.1f}% error)"
                )

    # 4) ATR floor (optional)
    if atr_value_pips is not None and atr_value_pips < min_atr_pips:
        errors.append(f"ATR too low: {atr_value_pips:.1f} pips < {min_atr_pips} minimum")

    return (len(errors) == 0), errors

def _parse_timeframe_minutes(tf: str) -> int:
    tf = tf.upper().strip()
    if tf.startswith("M"):
        return int(tf[1:])
    if tf.startswith("H"):
        return int(tf[1:]) * 60
    if tf.startswith("D"):
        return int(tf[1:]) * 1440
    return 0
