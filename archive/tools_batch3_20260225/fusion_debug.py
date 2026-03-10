#!/usr/bin/env python3
"""
fusion_debug.py
Inspect the latest tilted-YYYYMMDD.csv and explain why rows are used or skipped
by the fusion step (time cutoff, decision missing/HOLD, parse issues, etc.).
"""

import os, sys, csv, argparse, glob, datetime as dt
from pathlib import Path

LOG_DIR = os.path.expanduser("~/bot-a/logs")

DECISIONS = {"BUY", "SELL", "HOLD", "WAIT"}

def now_utc() -> dt.datetime:
    # timezone-aware UTC
    return dt.datetime.now(dt.timezone.utc)

def parse_iso_utc(s: str):
    """Return timezone-aware UTC datetime from various '...Z' forms; None on failure."""
    if not s:
        return None
    s = s.strip()
    # Accept ...Z or +00:00 etc.
    try:
        if s.endswith("Z"):
            # fromisoformat can't parse Z; replace with +00:00
            return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
        # Try plain fromisoformat (may already include offset)
        t = dt.datetime.fromisoformat(s)
        # If naive, assume UTC
        if t.tzinfo is None:
            t = t.replace(tzinfo=dt.timezone.utc)
        return t.astimezone(dt.timezone.utc)
    except Exception:
        return None

def find_tilted_csv(day_str: str | None) -> Path | None:
    """Find logs/tilted-YYYYMMDD.csv. If day_str is None, try today, then yesterday."""
    if day_str:
        p = Path(LOG_DIR) / f"tilted-{day_str}.csv"
        return p if p.exists() else None
    today = now_utc().strftime("%Y%m%d")
    p = Path(LOG_DIR) / f"tilted-{today}.csv"
    if p.exists():
        return p
    y = (now_utc() - dt.timedelta(days=1)).strftime("%Y%m%d")
    p = Path(LOG_DIR) / f"tilted-{y}.csv"
    return p if p.exists() else None

def pick_time_from_row(row_fields: list[str]) -> dt.datetime | None:
    """Rows sometimes have two ISO times and no header. Grab the last ISO-UTC-looking one."""
    t = None
    for f in row_fields:
        f = f.strip()
        if len(f) >= 20 and "T" in f and (f.endswith("Z") or "+" in f):
            cand = parse_iso_utc(f)
            if cand:
                t = cand  # keep last one
    return t

def pick_decision_from_row(row_fields: list[str]) -> str | None:
    """Find first BUY/SELL/HOLD/WAIT token (case-insensitive)."""
    for f in row_fields:
        u = (f or "").strip().upper()
        if u in DECISIONS:
            return u
    return None

def symbol_from_row(row_fields: list[str]) -> str:
    """Best-effort symbol; in your tilted rows it is column 3, but we fall back if short."""
    if len(row_fields) >= 4:
        return (row_fields[3] or "").strip().upper()
    # Fallback: first all-letters symbol-ish token
    for f in row_fields:
        u = (f or "").strip().upper()
        if 5 <= len(u) <= 8 and u.isalpha():
            return u
    return "?"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since-min", type=int, default=120, help="Lookback window in minutes")
    ap.add_argument("--day", type=str, default=None, help="YYYYMMDD (optional)")
    ap.add_argument("--show", type=int, default=0, help="Max rows to print (0=all)")
    args = ap.parse_args()

    csv_path = find_tilted_csv(args.day)
    if not csv_path:
        print("No tilted CSV found (today or yesterday).")
        sys.exit(1)

    cutoff = now_utc() - dt.timedelta(minutes=args.since_min)
    print(f"File: {csv_path}")
    print(f"UTC now: {now_utc().isoformat()}   Cutoff: {cutoff.isoformat()}")
    print(f"since-min: {args.since_min}\n")

    total = used = 0
    reasons = {
        "OK": 0,
        "older_than_cutoff": 0,
        "no_time": 0,
        "no_decision": 0,
        "hold_wait": 0,
        "parse_error": 0,
    }

    # We can't rely on headers; read as plain rows
    with open(csv_path, newline="") as f:
        rdr = csv.reader(f)
        for row in rdr:
            total += 1
            try:
                fields = [c.strip() for c in row]
                t = pick_time_from_row(fields)
                dec = pick_decision_from_row(fields)
                sym = symbol_from_row(fields)

                reason = "OK"
                if t is None:
                    reason = "no_time"
                elif t < cutoff:
                    reason = "older_than_cutoff"
                elif dec is None:
                    reason = "no_decision"
                elif dec in ("HOLD", "WAIT"):
                    reason = "hold_wait"

                reasons[reason] = reasons.get(reason, 0) + 1
                if reason == "OK":
                    used += 1

                # Print line-by-line verdict (optional cap with --show)
                if args.show == 0 or used + sum(v for k, v in reasons.items() if k != "OK") <= args.show:
                    t_str = t.isoformat() if t else "—"
                    print(f"{t_str}  {sym:7}  {dec or '—':5}  -> {reason}")

            except Exception:
                reasons["parse_error"] = reasons.get("parse_error", 0) + 1
                if args.show == 0 or sum(reasons.values()) <= args.show:
                    print("—  ?       ?     -> parse_error")

    print("\n=== Summary ===")
    print(f"Rows: {total}")
    for k in ["OK", "older_than_cutoff", "hold_wait", "no_decision", "no_time", "parse_error"]:
        print(f"{k:18}: {reasons.get(k,0)}")

    print("\nInterpretation:")
    print("- If most rows are 'older_than_cutoff': increase --since-min or check timestamps.")
    print("- If many are 'no_decision': the BUY/SELL token isn’t in the row where we expect.")
    print("- If many are 'no_time': the ISO time wasn’t found; check tilted CSV format.")
    print("- If many are 'hold_wait': fusion intentionally ignores HOLD/WAIT.")
    print("- If mostly 'OK' but fusion still sends nothing: gating/dedup logic is suppressing.")

if __name__ == "__main__":
    sys.exit(main())
