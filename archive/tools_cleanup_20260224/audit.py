#!/usr/bin/env python3
"""
audit.py — quick post-trade audit for recent signals.
"""

from __future__ import annotations
import argparse, csv, os, datetime as dt
from pathlib import Path
from typing import List, Optional, Tuple
import pandas as pd
from data import providers

UTC = dt.timezone.utc

def _logs_dir() -> Path:
    return Path(os.getenv("JOURNAL_DIR", str(Path.home() / "bot-a" / "logs"))).expanduser()

def _today_utc_ymd() -> str:
    return dt.datetime.now(UTC).strftime("%Y%m%d")

def _csv_path_for(date_ymd: str) -> Path:
    return _logs_dir() / f"signals-{date_ymd}.csv"

def _find_latest_csvs(max_days: int = 3) -> List[Path]:
    now = dt.datetime.now(UTC).date()
    return [
        _csv_path_for((now - dt.timedelta(days=i)).strftime("%Y%m%d"))
        for i in range(max_days)
        if _csv_path_for((now - dt.timedelta(days=i)).strftime("%Y%m%d")).exists()
    ]

def _parse_iso_utc(s: str) -> dt.datetime:
    s = s.strip().rstrip("Z").replace("T"," ")
    return dt.datetime.strptime(s, "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC)

def _pick_latest_signals(df: pd.DataFrame, n: int) -> pd.DataFrame:
    def _is_num(x):
        try: float(x); return True
        except: return False
    keep = (df["type"] == "ok") & df["score"].apply(_is_num) & df["side"].astype(str).str.len().gt(0)
    sub = df[keep].copy()
    if "time_utc" in sub.columns:
        sub["t"] = sub["time_utc"].apply(_parse_iso_utc)
        sub = sub.sort_values("t")
    return sub.tail(n).drop(columns=["t"], errors="ignore")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=3)
    ap.add_argument("--lookahead", type=int, default=12)
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    csvs = _find_latest_csvs()
    if not csvs:
        print("No signal CSVs found yet."); return 0

    frames = []
    for p in csvs:
        try:
            df = pd.read_csv(p, on_bad_lines="skip", quoting=csv.QUOTE_MINIMAL)
            frames.append(df)
        except Exception as e:
            print(f"WARN: failed to read {p}: {e}")
    if not frames:
        print("No readable CSVs."); return 0

    df = pd.concat(frames, ignore_index=True)
    needed = ["run_id","time_utc","symbol","tf","type","score","bias","side","entry","stop","target"]
    for c in needed:
        if c not in df.columns: df[c] = ""

    pick = _pick_latest_signals(df, args.n)
    if pick.empty:
        print("No recent posted signals to audit."); return 0

    print(pick[["time_utc","symbol","tf","side","score","bias","entry","stop","target"]].to_string(index=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
