import os, time
from datetime import datetime, timezone
import pandas as pd
from tools.fetch_data import get_ohlc

# Provider order: env ROTATOR_ORDER or default
DEFAULT_ORDER = ["twelvedata", "alphavantage", "finnhub", "eodhd", "yahoo"]
ORDER = [p.strip() for p in os.environ.get("ROTATOR_ORDER", ",".join(DEFAULT_ORDER)).split(",") if p.strip()]

# Rate limits (per minute) read at import; fall back to sane defaults
RATES = {
    "twelvedata": int(os.environ.get("TWELVEDATA_RATE_PER_MIN", "1") or "1"),
    "alphavantage": int(os.environ.get("ALPHAVANTAGE_RATE_PER_MIN", "4") or "4"),
    "finnhub": int(os.environ.get("FINNHUB_RATE_PER_MIN", "2") or "2"),
    "eodhd": int(os.environ.get("EODHD_RATE_PER_MIN", "2") or "2"),
    "yahoo": 99,
}

# New: soft health gate – skip a provider if it failed >= N times this minute
FAIL_TOLERANCE = int(os.environ.get("ROTATOR_FAIL_TOLERANCE", "2"))
_fail_counts = {}           # {(minute_str, provider): count}
_last_minute = None

def _minute_key():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")

def _bump_fail(p):
    global _last_minute
    m = _minute_key()
    if _last_minute != m:
        # new minute -> decay the old counters
        _last_minute = m
    key = (m, p)
    _fail_counts[key] = _fail_counts.get(key, 0) + 1

def _too_many_fails(p):
    m = _minute_key()
    return _fail_counts.get((m, p), 0) >= FAIL_TOLERANCE

def _log(msg):
    utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    print(f"LOG UTC {utc} | {msg}", flush=True)

def get_ohlc_rotating(symbol: str, interval: str, limit: int = 20):
    last_error = None
    for p in ORDER:
        if _too_many_fails(p):
            _log(f"SKIP {p} rate/health: exceeded fail tolerance this minute")
            continue
        try:
            _log(f"Trying {p.upper()} {symbol} interval={interval} size~{limit}")
            df = get_ohlc(symbol, interval, limit=limit, provider=p)
            _log(f"{p.upper()} OK {symbol} rows={len(df)} last={df.index[-1]}")
            return df, p
        except Exception as e:
            _bump_fail(p)
            last_error = e
            _log(f"{p.upper()} FAIL {p}: {e.__class__.__name__}: {e}")
    raise RuntimeError(f"All providers failed/empty for {symbol} {interval} (order={ORDER}) | last_error={last_error!r}")
