#!/usr/bin/env python3
"""
sanitize_csv.py — normalize and fix signals-*.csv files so audits never break.

What it does
------------
- Scans ~/bot-a/logs for files named signals-*.csv
- Reads each file forgivingly (skips obviously bad lines)
- Normalizes to the canonical header:
    run_id,time_utc,symbol,tf,type,score,bias,side,entry,stop,target,why,cadence,watchlist,engine
- For rows with too many columns: trails are merged into 'why'
- For rows with missing columns: fills empty values
- Quotes text where needed so commas/newlines in 'why' don't break CSV
- Writes to a .tmp, backs up original to .bak, then atomically replaces

Usage
-----
  python tools/sanitize_csv.py          # fix all logs
  python tools/sanitize_csv.py --dry    # show summary, don't write
"""

from __future__ import annotations
import argparse, csv, sys
from pathlib import Path
from typing import List, Dict

CANON = [
    "run_id","time_utc","symbol","tf","type",
    "score","bias","side","entry","stop","target",
    "why","cadence","watchlist","engine"
]
CANON_SET = {c.lower() for c in CANON}

LOGS = Path.home() / "bot-a" / "logs"

def find_files() -> List[Path]:
    return sorted(LOGS.glob("signals-*.csv"))

def read_header(line: str) -> List[str]:
    # Simple split is OK only for header line (no quotes expected there)
    cols = [c.strip() for c in line.strip().split(",")]
    return cols

def map_columns(header: List[str]) -> Dict[int,str]:
    """Map file column positions -> canonical name (or '') if unknown."""
    mapping = {}
    used = set()
    for i, raw in enumerate(header):
        k = raw.strip().lower()
        # accept exact canon names or some common aliases
        alias = {
            "time": "time_utc",
            "timeutc": "time_utc",
            "timestamp": "time_utc",
            "session": "engine",   # legacy 'session' -> 'engine'
        }.get(k, k)
        if alias in CANON_SET and alias not in used:
            mapping[i] = alias
            used.add(alias)
        else:
            mapping[i] = ""  # unknown/extra column -> will be handled later
    return mapping

def coerce_row(cells: List[str], pos2name: Dict[int,str]) -> List[str]:
    """
    Build a canonical row list of length len(CANON).
    - If there are extra cells, merge them into 'why'.
    - If missing, fill "".
    """
    out = {name: "" for name in CANON}
    # First pass: place by mapping
    extras: List[str] = []
    for i, val in enumerate(cells):
        name = pos2name.get(i, "")
        if name:
            # keep first hit only; if duplicates, push to extras
            if out[name] == "":
                out[name] = val
            else:
                extras.append(val)
        else:
            extras.append(val)

    if extras:
        if out["why"]:
            out["why"] = f"{out['why']} | " + " | ".join(extras)
        else:
            out["why"] = " | ".join(extras)

    # Return in canonical order
    return [out[c] for c in CANON]

def sanitize_file(path: Path, dry: bool=False) -> dict:
    """
    Returns summary dict: {'file': str, 'rows_in': int, 'rows_out': int, 'skipped': int}
    """
    text = path.read_text(encoding="utf-8", errors="replace").splitlines()
    if not text:
        return {"file": str(path), "rows_in": 0, "rows_out": 0, "skipped": 0}

    header_line = text[0]
    header_cols = read_header(header_line)
    pos2name = map_columns(header_cols)

    # Build CSV reader for the rest; tolerate broken quoting
    rows_in = 0
    rows_out = 0
    skipped = 0

    out_lines: List[List[str]] = []

    for raw in text[1:]:
        rows_in += 1
        raw = raw.strip()
        if not raw:
            skipped += 1
            continue
        try:
            # Try robust CSV parse first
            reader = csv.reader([raw])
            cells = next(reader)
        except Exception:
            # If CSV parse fails, fallback to plain split (worst case)
            cells = [c.strip() for c in raw.split(",")]

        # Hard guard: sometimes garbage lines come through
        if len(cells) == 0 or all(not c for c in cells):
            skipped += 1
            continue

        canon = coerce_row(cells, pos2name)
        out_lines.append(canon)
        rows_out += 1

    # If header is not canonical, replace with canonical header
    out_header = CANON

    if dry:
        return {"file": str(path), "rows_in": rows_in, "rows_out": rows_out, "skipped": skipped}

    # Write to tmp with quoting for safety
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
        w.writerow(out_header)
        w.writerows(out_lines)

    # Backup original, replace atomic
    bak = path.with_suffix(path.suffix + ".bak")
    try:
        if bak.exists(): bak.unlink()
    except Exception:
        pass
    path.replace(bak)
    tmp.replace(path)

    return {"file": str(path), "rows_in": rows_in, "rows_out": rows_out, "skipped": skipped}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true", help="Dry-run (do not write files)")
    args = ap.parse_args()

    LOGS.mkdir(parents=True, exist_ok=True)
    files = find_files()
    if not files:
        print("No signals-*.csv files found.")
        return 0

    total_in = total_out = total_skip = 0
    for p in files:
        s = sanitize_file(p, dry=args.dry)
        total_in += s["rows_in"]; total_out += s["rows_out"]; total_skip += s["skipped"]
        tag = "DRY" if args.dry else "FIX"
        print(f"[{tag}] {s['file']}: in={s['rows_in']} out={s['rows_out']} skipped={s['skipped']}")

    print(f"Done. Total in={total_in} out={total_out} skipped={total_skip}")
    if not args.dry:
        print("Backups saved as *.bak next to each CSV.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
