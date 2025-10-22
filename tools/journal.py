#!/usr/bin/env python3
"""
journal.py — single place to write signal rows in a consistent CSV schema.

- Ensures logs dir exists
- Creates today's CSV with a fixed header (same order, every time)
- Appends rows safely (no extra commas, all fields present)
"""

from __future__ import annotations
import os, csv, datetime as dt
from pathlib import Path
from typing import Dict, List, Iterable, Optional

# ---------- config ----------
JOURNAL_DIR = Path(os.environ.get("JOURNAL_DIR", str(Path.home() / "bot-a" / "logs")))
CSV_PREFIX  = "signals-"
CSV_FIELDS: List[str] = [
    # keep this order STABLE – audit/sanitize depend on it
    "run_id",
    "time_utc",
    "symbol",
    "tf",
    "side",        # "BUY"/"SELL"/"HOLD" or ""
    "score",       # int or ""
    "bias",        # "Bullish"/"Bearish"/"Neutral" or ""
    "entry",       # float or ""
    "stop",        # float or ""
    "target",      # float or ""
    "why",         # free text (short)
    "posted",      # 1/0  or ""
    "watchlist",   # e.g., "EURUSD,XAUUSD"
    "engine",      # e.g., "v2b"
]
# ----------------------------

def _ensure_dir():
    JOURNAL_DIR.mkdir(parents=True, exist_ok=True)

def _today_path() -> Path:
    utc = dt.datetime.utcnow().strftime("%Y%m%d")
    return JOURNAL_DIR / f"{CSV_PREFIX}{utc}.csv"

def _ensure_header(path: Path):
    if not path.exists() or path.stat().st_size == 0:
        with path.open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(CSV_FIELDS)

def _clean(value) -> str:
    # normalize to string, strip newlines/commas that break CSV
    if value is None:
        return ""
    s = str(value)
    return s.replace("\n", " ").replace("\r", " ").replace(",", " ")

def append_row(row: Dict[str, object]) -> Path:
    """
    Append a row dict to today's CSV, filling missing fields with "".
    Returns the CSV path.
    """
    _ensure_dir()
    path = _today_path()
    _ensure_header(path)

    out = [_clean(row.get(k, "")) for k in CSV_FIELDS]
    with path.open("a", newline="") as f:
        w = csv.writer(f)
        w.writerow(out)
    return path

def header() -> List[str]:
    return list(CSV_FIELDS)

if __name__ == "__main__":
    # tiny self-test
    p = append_row({
        "run_id": "test123",
        "time_utc": dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%SZ"),
        "symbol": "EURUSD",
        "tf": "5min",
        "side": "HOLD",
        "score": 42,
        "bias": "Bullish",
        "entry": 1.17123,
        "stop": "",
        "target": "",
        "why": "self-test",
        "posted": 0,
        "watchlist": "EURUSD",
        "engine": "v2b",
    })
    print("wrote:", p)
