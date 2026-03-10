#!/usr/bin/env python3
"""
signal_accuracy.py  (Option A fix)

Parses BotA logs/alerts.csv robustly across both:
  (1) legacy 9-column rows:
      timestamp,pair,tf,direction,score,confidence,reasons,price,provider
  (2) current rows (>=12 columns, with tail reasons):
      timestamp,pair,tf,direction,score,confidence,entry,sl,tp,provider,rejected,filter_str,reasons...

Key Fix:
  In current rows, provider is column 10 (1-based) => row[9] (0-based).
  Previously mis-read due to stale header logic, causing TP float
  (row[8]) to be mistaken as provider.

Reasons quoting edge case:
  - If reasons are properly quoted (single CSV field containing commas),
    csv.reader returns it as ONE column.
  - If reasons spill into extra columns (CSV quoting bug), we reconstruct
    reasons by joining the tail columns with commas.

Option B header (derived from your example row):
  If you insist on matching the *currently broken* 15-column reality (3 reason columns):
    timestamp,pair,tf,direction,score,confidence,entry,sl,tp,provider,rejected,filter_str,reason_1,reason_2,reason_3

Recommendation:
  Prefer Option A (this file) because it is surgical and does NOT rewrite historical logs.
  For long-term correctness, fix the writer upstream so "reasons" is always one properly-quoted field,
  then standardize on a 13-column header:
    timestamp,pair,tf,direction,score,confidence,entry,sl,tp,provider,rejected,filter_str,reasons
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from collections import Counter
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


def _is_number(s: str) -> bool:
    try:
        float(s)
        return True
    except Exception:
        return False


def _to_float(s: str) -> Optional[float]:
    try:
        return float(s)
    except Exception:
        return None


def _to_bool(s: str) -> Optional[bool]:
    if s is None:
        return None
    v = s.strip().lower()
    if v in {"true", "1", "yes", "y", "t"}:
        return True
    if v in {"false", "0", "no", "n", "f"}:
        return False
    return None


def _looks_like_header(row: List[str]) -> bool:
    if not row:
        return False
    r0 = (row[0] or "").strip().lower()
    return r0 in {"timestamp", "time", "ts", "datetime"} or r0.startswith("timestamp")


@dataclass
class AlertRecord:
    schema: str  # "legacy9" | "current" | "unknown"
    raw_ncols: int
    timestamp: str = ""
    pair: str = ""
    tf: str = ""
    direction: str = ""
    score: Optional[float] = None
    confidence: Optional[float] = None
    entry: Optional[float] = None
    sl: Optional[float] = None
    tp: Optional[float] = None
    provider: str = ""
    rejected: Optional[bool] = None
    filter_str: str = ""
    reasons: str = ""
    price: Optional[float] = None
    raw: Optional[List[str]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema": self.schema,
            "raw_ncols": self.raw_ncols,
            "timestamp": self.timestamp,
            "pair": self.pair,
            "tf": self.tf,
            "direction": self.direction,
            "score": self.score,
            "confidence": self.confidence,
            "entry": self.entry,
            "sl": self.sl,
            "tp": self.tp,
            "provider": self.provider,
            "rejected": self.rejected,
            "filter_str": self.filter_str,
            "reasons": self.reasons,
            "price": self.price,
        }


def parse_alert_row(row_in: List[str], strict: bool = False) -> Optional["AlertRecord"]:
    row = [(c or "").strip() for c in row_in]
    if not row or all(c == "" for c in row):
        return None
    if _looks_like_header(row):
        return None

    n = len(row)

    # Current schema heuristic:
    # >=12 cols AND score/conf/entry numeric-ish at indices 4/5/6
    if n >= 12 and _is_number(row[4]) and _is_number(row[5]) and _is_number(row[6]):
        return AlertRecord(
            schema="current",
            raw_ncols=n,
            timestamp=row[0],
            pair=row[1],
            tf=row[2],
            direction=row[3],
            score=_to_float(row[4]),
            confidence=_to_float(row[5]),
            entry=_to_float(row[6]),
            sl=_to_float(row[7]) if n > 7 else None,
            tp=_to_float(row[8]) if n > 8 else None,
            provider=row[9] if n > 9 else "",  # OPTION A FIX (provider col 10 => idx 9)
            rejected=_to_bool(row[10]) if n > 10 else None,
            filter_str=row[11] if n > 11 else "",
            reasons=",".join(row[12:]) if n > 12 else "",
            raw=row_in,
        )

    # Legacy schema: >=9 cols, score numeric at index 4
    if n >= 9 and _is_number(row[4]) and _is_number(row[5]):
        return AlertRecord(
            schema="legacy9",
            raw_ncols=n,
            timestamp=row[0],
            pair=row[1],
            tf=row[2],
            direction=row[3],
            score=_to_float(row[4]),
            confidence=_to_float(row[5]),
            reasons=row[6] if n > 6 else "",
            price=_to_float(row[7]) if n > 7 else None,
            provider=row[8] if n > 8 else "",
            raw=row_in,
        )

    if strict:
        raise ValueError(f"Unrecognized row format (ncols={n}): {row!r}")
    return AlertRecord(schema="unknown", raw_ncols=n, raw=row_in)


def read_alerts(path: str, strict: bool = False) -> List[AlertRecord]:
    if not os.path.exists(path):
        raise FileNotFoundError(f"alerts file not found: {path}")
    records: List[AlertRecord] = []
    with open(path, "r", newline="", encoding="utf-8") as f:
        for row in csv.reader(f):
            rec = parse_alert_row(row, strict=strict)
            if rec is not None:
                records.append(rec)
    return records


def summarize(records: List[AlertRecord]) -> str:
    # Exclude synthetic HOLD rows from summary metrics (safe identifier: pair == HOLD).
    records = [
        r for r in records
        if not ((r.pair or "").strip().upper() == "HOLD")
    ]
    total = len(records)
    by_schema = Counter(r.schema for r in records)
    current = [r for r in records if r.schema == "current"]

    rejected_counts: Counter = Counter()
    for r in current:
        if r.rejected is True:
            rejected_counts["rejected_true"] += 1
        elif r.rejected is False:
            rejected_counts["rejected_false"] += 1
        else:
            rejected_counts["rejected_unknown"] += 1

    provider_counts = Counter(
        (r.provider or "").strip() for r in records
        if r.provider and (r.provider or "").strip()
    )
    pair_tf = Counter((r.pair, r.tf) for r in records if r.pair and r.tf)

    numeric_provider = sum(
        1 for r in records
        if (r.provider or "").strip() and _is_number((r.provider or "").strip())
    )

    lines = [
        "=== signal_accuracy.py summary ===",
        f"total_rows_parsed: {total}",
        f"schema_counts: {dict(by_schema)}",
        f"current_rejected_counts: {dict(rejected_counts)}",
        "top_providers:",
    ]
    if provider_counts:
        for prov, cnt in provider_counts.most_common(10):
            lines.append(f"  - {prov}: {cnt}")
    else:
        lines.append("  - (none detected)")

    lines.append("top_pair_tf:")
    for (pair, tf), cnt in pair_tf.most_common(10):
        lines.append(f"  - {pair} {tf}: {cnt}")

    unknown_count = by_schema.get("unknown", 0)
    if unknown_count:
        lines.append(f"unknown_rows: {unknown_count} (use --strict to fail on these)")

    if numeric_provider:
        lines.append(
            f"WARNING provider_looks_numeric: {numeric_provider} rows "
            f"— still indicates upstream/header/index issues"
        )

    return "\n".join(lines) + "\n"


def write_json(records: List[AlertRecord], out_path: str) -> None:
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump([r.to_dict() for r in records], f, indent=2, ensure_ascii=False)


def write_normalized_csv(records: List[AlertRecord], out_path: str) -> None:
    fieldnames = [
        "timestamp", "pair", "tf", "direction", "score", "confidence",
        "entry", "sl", "tp", "provider", "rejected", "filter_str",
        "reasons", "price", "schema", "raw_ncols",
    ]
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for r in records:
            d = r.to_dict()
            d["schema"] = r.schema
            d["raw_ncols"] = r.raw_ncols
            w.writerow(d)


def run_self_test() -> int:
    # Spill case (broken quoting -> reasons split)
    sample_spill = [
        "2026-02-23T12:49:42+0200", "USDJPY", "M15", "BUY",
        "63.30", "63.30", "154.81100", "154.65649", "155.06853",
        "engine_A2", "false", "macro6=3 | H1_trend_neutral",
        "reasonA", "reasonB", "reasonC",
    ]
    rec1 = parse_alert_row(sample_spill, strict=True)
    assert rec1 is not None
    assert rec1.schema == "current"
    assert rec1.provider == "engine_A2", f"provider parse failed: {rec1.provider!r}"
    assert rec1.tp == 155.06853
    assert rec1.rejected is False
    assert rec1.reasons == "reasonA,reasonB,reasonC"

    # Quoted case (csv.reader would keep commas inside ONE field)
    sample_quoted = [
        "2026-02-23T12:49:42+0200", "USDJPY", "M15", "BUY",
        "63.30", "63.30", "154.81100", "154.65649", "155.06853",
        "engine_A2", "false", "macro6=3 | H1_trend_neutral",
        "reason1,reason2,reason3",
    ]
    rec2 = parse_alert_row(sample_quoted, strict=True)
    assert rec2 is not None
    assert rec2.schema == "current"
    assert rec2.provider == "engine_A2"
    assert rec2.reasons == "reason1,reason2,reason3"

    print("SELF_TEST=PASS")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Parse BotA alerts.csv and summarize provider/rejection stats.")
    p.add_argument("--alerts", default="logs/alerts.csv")
    p.add_argument("--strict", action="store_true")
    p.add_argument("--emit", choices=["summary", "json", "csv"], default="summary")
    p.add_argument("--out", default="")
    p.add_argument("--self-test", action="store_true")
    args = p.parse_args(argv)

    if args.self_test:
        try:
            return run_self_test()
        except Exception as e:
            print(f"SELF_TEST_FAIL: {e}", file=sys.stderr)
            return 2

    try:
        records = read_alerts(args.alerts, strict=args.strict)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    if args.emit == "summary":
        sys.stdout.write(summarize(records))
        return 0

    if not args.out:
        print("ERROR: --out required for json/csv emit", file=sys.stderr)
        return 1

    try:
        if args.emit == "json":
            write_json(records, args.out)
        elif args.emit == "csv":
            write_normalized_csv(records, args.out)
    except Exception as e:
        print(f"ERROR writing {args.emit} to {args.out}: {e}", file=sys.stderr)
        return 1

    print(f"OK: wrote {args.emit} -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
