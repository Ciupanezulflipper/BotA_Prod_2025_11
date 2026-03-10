#!/usr/bin/env python3
"""
signal_journal.py

Creates/repairs the signal journal CSV so downstream tools (accuracy_eval.py,
signals_card.py, etc.) never choke on missing files or bad headers.

- Ensures ~/bot-a/data/signal_journal.csv exists
- Ensures the header matches EXPECTED_HEADERS exactly
- If the file exists but has a wrong header, it is backed up with a timestamp
  and a fresh file with the correct header is created.
- Can optionally append a row via CLI for quick testing.

Usage:
  python3 signal_journal.py                # just ensure/repair file
  python3 signal_journal.py --append-test  # append a dummy row (for sanity check)
  python3 signal_journal.py --append \
      --ts "2025-09-21T00:00:00Z" --event "SIGNAL" --pair "EURUSD" --tf "M15" \
      --score 42 --conf 6.5 --reason "demo" --signal-id "abc123" --source "unit" --line 1
"""

from __future__ import annotations
import argparse
import csv
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Dict, Any

# === Configuration ===
HOME = Path.home()
DATA_DIR = HOME / "bot-a" / "data"
JOURNAL_PATH = DATA_DIR / "signal_journal.csv"

EXPECTED_HEADERS = [
    "ts_utc",        # ISO8601 UTC timestamp
    "event",         # SIGNAL / CANCEL / UPDATE / etc.
    "pair",          # e.g., EURUSD
    "tf",            # timeframe, e.g., M15, H1
    "score",         # model / composite score (number)
    "conf",          # confidence 0..10 (float)
    "reason",        # short reason / justification
    "signal_id",     # unique id that ties updates/cancels
    "source",        # which module/source emitted the row
    "log_line_no",   # optional, line number in a log (int)
]

BACKUP_SUFFIX = ".bak"

def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)

def read_first_line(path: Path) -> str:
    try:
        with path.open("r", encoding="utf-8") as f:
            return f.readline().strip()
    except Exception:
        return ""

def write_header(path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(EXPECTED_HEADERS)

def ensure_journal() -> str:
    """
    Ensure the journal exists with the correct header.
    If a wrong header is detected, back it up and recreate.
    Returns a short status string describing what was done.
    """
    ensure_dir(DATA_DIR)

    if not JOURNAL_PATH.exists():
        write_header(JOURNAL_PATH)
        return f"created {JOURNAL_PATH}"

    # File exists – check header
    first = read_first_line(JOURNAL_PATH)
    good = first == ",".join(EXPECTED_HEADERS)

    if good:
        return f"ok {JOURNAL_PATH}"

    # Wrong/missing header: back up and recreate
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = JOURNAL_PATH.with_suffix(JOURNAL_PATH.suffix + f".{ts}{BACKUP_SUFFIX}")
    try:
        JOURNAL_PATH.replace(backup_path)
    except Exception as e:
        return f"error backing up old journal: {e}"

    write_header(JOURNAL_PATH)
    return f"repaired header (backup -> {backup_path.name})"

def append_row(row: Dict[str, Any]) -> None:
    """
    Append a row dict with keys matching EXPECTED_HEADERS.
    Missing keys are filled with empty strings.
    """
    out = [str(row.get(k, "")) for k in EXPECTED_HEADERS]
    with JOURNAL_PATH.open("a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(out)

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Ensure/append to signal_journal.csv")
    p.add_argument("--append-test", action="store_true", help="Append a dummy test row")
    p.add_argument("--append", action="store_true", help="Append a row via args")

    # Fields for --append
    p.add_argument("--ts", dest="ts_utc")
    p.add_argument("--event")
    p.add_argument("--pair")
    p.add_argument("--tf")
    p.add_argument("--score", type=float)
    p.add_argument("--conf", type=float)
    p.add_argument("--reason")
    p.add_argument("--signal-id", dest="signal_id")
    p.add_argument("--source")
    p.add_argument("--line", dest="log_line_no")
    return p.parse_args()

def main() -> int:
    status = ensure_journal()
    print(f"Journal {status}")

    args = parse_args()

    if args.append_test:
        append_row({
            "ts_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "event": "TEST",
            "pair": "EURUSD",
            "tf": "M15",
            "score": 0,
            "conf": 0.0,
            "reason": "append-test",
            "signal_id": "test-" + datetime.now(timezone.utc).strftime("%H%M%S"),
            "source": "signal_journal.py",
            "log_line_no": 0,
        })
        print("Appended test row.")
        return 0

    if args.append:
        row = {
            "ts_utc": args.ts_utc or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "event": args.event or "SIGNAL",
            "pair": args.pair or "",
            "tf": args.tf or "",
            "score": args.score if args.score is not None else "",
            "conf": args.conf if args.conf is not None else "",
            "reason": args.reason or "",
            "signal_id": args.signal_id or "",
            "source": args.source or "manual",
            "log_line_no": args.log_line_no or "",
        }
        append_row(row)
        print("Appended 1 row.")
        return 0

    return 0

if __name__ == "__main__":
    sys.exit(main())
