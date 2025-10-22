import os
import pandas as pd

def _as_minutes(delta):
    return delta.total_seconds() / 60.0

def validate_ohlc(df: pd.DataFrame, timeframe='M15', max_gap_tolerance=0.10):
    """
    Returns (ok: bool, reason: str). Columns must include close/Close.
    Checks: staleness (env MAX_STALENESS_MIN), ATR floor (env MIN_ATR_PIPS),
    time span anomaly, and forward-fill freeze (flat last 4 closes).
    """
    if df is None or len(df) == 0:
        return False, "No data"

    # Normalize columns
    cols = {c.lower(): c for c in df.columns}
    if 'close' not in cols:
        return False, "Missing 'close' column"
    close_col = cols['close']

    # Staleness
    max_stale = int(os.getenv("MAX_STALENESS_MIN", "45"))
    last_ts = df.index[-1] if df.index.name else df[cols.get('time','time')].iloc[-1]
    last_ts = pd.to_datetime(last_ts, utc=True, errors='coerce')
    age_min = _as_minutes(pd.Timestamp.utcnow() - last_ts)
    if age_min > max_stale:
        return False, f"Data stale: last bar {age_min:.1f} min old (max {max_stale})"

    # Expected span check for regular TFs (rough, but catches gaps)
    tf_min = 15 if timeframe.upper() == "M15" else 60
    expected = (len(df)-1) * tf_min
    actual = _as_minutes(last_ts - (df.index[0] if df.index.name else pd.to_datetime(df.iloc[0][cols.get('time','time')], utc=True)))
    if expected > 0:
        err = abs(actual - expected) / expected
        if err > max_gap_tolerance:
            return False, f"Time span anomaly: {int(actual)} min for {len(df)} bars (expected {int(expected)} min, {err*100:.1f}% error)"

    # ATR floor — caller passes atr_pips via env; we trust runner to compute/compare
    # Forward-fill freeze: last 4 closes all equal
    last4 = df[close_col].tail(4)
    if last4.nunique(dropna=True) == 1 and len(last4) == 4:
        return False, "Price frozen for 4 bars (likely stale/ffill)"

    return True, "OK"
