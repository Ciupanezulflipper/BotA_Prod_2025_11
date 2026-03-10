#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Append a signal to a per-day CSV and prune old files.
Usage: python3 csv_writer.py "2025-09-20T11:45:50+00:00" EURUSD BUY 7.0 6 5 hash
"""

import sys, csv
from pathlib import Path
from lib_utils import rotate_csv_daily, utcdate

BASE = Path(__file__).resolve().parent.parent
DATA_DIR = BASE / "data"
CSV_BASE = DATA_DIR / "signals.csv"

def main():
    if len(sys.argv) < 8:
        print("args: ts pair side conf s6 tf hash")
        sys.exit(2)
    _, ts, pair, side, conf, s6, tfv, h = sys.argv
    today = utcdate()
    dated = rotate_csv_daily(str(CSV_BASE), today, keep_days=30)
    with open(dated, "a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow([ts, pair, side, conf, s6, tfv, h])
    print("[CSV_OK]", dated)

if __name__ == "__main__":
    main()
