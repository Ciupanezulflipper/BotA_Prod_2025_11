#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
news_log.py — fetch news-bias for your WATCHLIST and append to CSV logs.

What it does
------------
- Reads WATCHLIST from env (e.g., "EURUSD,XAUUSD").
- Calls tools.news.news_for_symbols(watchlist) to get per-symbol bias/score/why.
- Appends rows to ~/bot-a/logs/news-YYYYMMDD.csv (creates header if new).
- Prints pretty one-liners to stdout, and can emit JSON with --json.
- Safe to cron; robust to transient errors; never throws on normal failures.

CLI
---
  --watchlist EURUSD,XAUUSD   Override env WATCHLIST just for this run
  --json                      Also print a JSON array of results
  --dry                       Print only; do not write CSV

CSV schema
----------
run_id,time_utc,asof_utc,symbol,score,bias,why,event_risk,version
"""

from __future__ import annotations
import os, sys, csv, json, uuid, argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any

# ---- small helpers ---------------------------------------------------------

def utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def env(name: str, default: str) -> str:
    v = os.getenv(name)
    return v if v is not None and str(v).strip() != "" else default

def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)

def run_id() -> str:
    return uuid.uuid4().hex[:8]

# ---- import your existing news engine --------------------------------------
# NOTE: This relies on tools/news.py you already created.
try:
    from tools.news import news_for_symbols
except Exception as e:  # keep running; explain and exit gracefully
    print(f"ERROR: cannot import tools.news.news_for_symbols: {e}", file=sys.stderr)
    sys.exit(0)

# ---- core ------------------------------------------------------------------

HEADERS = [
    "run_id",
    "time_utc",
    "asof_utc",
    "symbol",
    "score",
    "bias",
    "why",
    "event_risk",
    "version",
]

VERSION = "news_v1"

def parse_watchlist(override: str | None) -> List[str]:
    if override and override.strip():
        src = override
    else:
        src = env("WATCHLIST", "EURUSD,XAUUSD")
    wl = [s.strip().upper() for s in src.split(",") if s.strip()]
    # de-dup while preserving order
    seen = set()
    uniq = []
    for s in wl:
        if s not in seen:
            uniq.append(s); seen.add(s)
    return uniq

def format_oneliner(r: Dict[str, Any]) -> str:
    sym = f"{r.get('symbol',''):<7}"
    sc  = int(r.get("score", 0))
    bias = r.get("bias", "")
    why  = r.get("why", "")
    return f"{sym} | news {sc:+d} | {bias:<7} | {why}"

def write_rows(rows: List[List[Any]], logs_dir: Path, dry: bool=False) -> Path | None:
    if dry or not rows:
        return None
    ensure_dir(logs_dir)
    fpath = logs_dir / f"news-{datetime.now(timezone.utc).strftime('%Y%m%d')}.csv"
    is_new = not fpath.exists()
    # Write with UTF-8 and minimal quoting
    with fpath.open("a", encoding="utf-8", newline="") as f:
        w = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
        if is_new:
            w.writerow(HEADERS)
        for row in rows:
            # ensure row length matches header; truncate or pad
            row = (row + [""] * len(HEADERS))[:len(HEADERS)]
            w.writerow(row)
    return fpath

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--watchlist", help="Override watchlist, e.g. EURUSD,XAUUSD", default=None)
    ap.add_argument("--json", action="store_true", help="Also print JSON array of results")
    ap.add_argument("--dry", action="store_true", help="Dry run: do not write CSV")
    args = ap.parse_args()

    wl = parse_watchlist(args.watchlist)
    if not wl:
        print("INFO: Empty watchlist; nothing to do.")
        return 0

    try:
        results: List[Dict[str, Any]] = news_for_symbols(wl)
    except Exception as e:
        print(f"WARN: news_for_symbols failed: {e}", file=sys.stderr)
        results = []

    if not results:
        print("INFO: No news results.")
        return 0

    # Print pretty oneliners for terminal visibility
    for r in results:
        print(format_oneliner(r))

    if args.json:
        print("\nJSON:")
        # ensure_ascii=False so you see proper punctuation if any
        print(json.dumps(results, ensure_ascii=False))

    # Compose CSV rows
    rid  = run_id()
    nowz = utcnow_iso()
    out_rows: List[List[Any]] = []
    for r in results:
        out_rows.append([
            rid,
            nowz,
            r.get("asof_utc", nowz),
            r.get("symbol", ""),
            int(r.get("score", 0)),
            r.get("bias", ""),
            r.get("why", ""),
            r.get("event_risk", ""),
            VERSION,
        ])

    # Write
    logs_dir = Path.home() / "bot-a" / "logs"
    out_file = write_rows(out_rows, logs_dir, dry=args.dry)
    if out_file:
        print(f"LOG: appended {len(out_rows)} rows -> {out_file}")
    else:
        print("DRY: skipped file write.")

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
