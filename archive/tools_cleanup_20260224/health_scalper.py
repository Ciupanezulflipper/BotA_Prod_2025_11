#!/usr/bin/env python3
from __future__ import annotations
import os, sys, json, datetime as dt
from typing import Dict, List, Tuple

ROOT = os.path.expanduser("~/BotA")
LOG_PATH = os.path.join(ROOT, "logs", "signal_run.log")

def parse_expected(spec: str) -> List[Tuple[str,str]]:
    out: List[Tuple[str,str]] = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if ":" in part:
            sym, tf = part.split(":", 1)
        else:
            # fallback: assume TF15 if timeframe missing
            sym, tf = part, "TF15"
        out.append((sym.strip().upper(), tf.strip().upper()))
    return out

def load_last_runs(path: str) -> Dict[Tuple[str,str], dt.datetime]:
    """
    Parse lines like:
    [run] === EURUSD TF15 === 2025-11-04 17:48:36 UTC
    """
    res: Dict[Tuple[str,str], dt.datetime] = {}
    if not os.path.exists(path):
        return res
    import re
    pat = re.compile(
        r"^\[run\]\s+===\s+([A-Z0-9/]+)\s+(TF\d+)\s+===\s+(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s+UTC$"
    )
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.rstrip("\n")
            m = pat.match(line.strip())
            if not m:
                continue
            sym = m.group(1).replace("/", "").upper()
            tf  = m.group(2).upper()
            ts_str = m.group(3)
            try:
                ts = dt.datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
            except Exception:
                continue
            res[(sym, tf)] = ts
    return res

def main() -> int:
    # Which scalper streams we expect to be alive
    expected_spec = os.getenv("BOT_A_SCALPER_EXPECTED", "EURUSD:TF15,GBPUSD:TF15")
    # Max age in minutes for the last scalper run
    max_age_min = float(os.getenv("BOT_A_SCALPER_MAX_AGE_MIN", "60"))

    expected = parse_expected(expected_spec)
    last = load_last_runs(LOG_PATH)
    now = dt.datetime.utcnow()

    rows = []
    overall_ok = True

    for sym, tf in expected:
        key = (sym, tf)
        ts = last.get(key)
        if ts is None:
            rows.append({
                "pair": sym,
                "tf": tf,
                "status": "MISSING",
                "age_min": None,
                "max_age_min": max_age_min,
                "message": "No scalper run found in signal_run.log"
            })
            overall_ok = False
            continue

        age_min = (now - ts).total_seconds() / 60.0
        ok = age_min <= max_age_min
        if not ok:
            overall_ok = False
        rows.append({
            "pair": sym,
            "tf": tf,
            "status": "OK" if ok else "STALE",
            "last_run_utc": ts.strftime("%Y-%m-%d %H:%M:%S"),
            "age_min": round(age_min, 1),
            "max_age_min": max_age_min,
        })

    summary = {
        "log_path": LOG_PATH,
        "now_utc": now.strftime("%Y-%m-%d %H:%M:%S"),
        "max_age_min": max_age_min,
        "expected": [{"pair": s, "tf": tf} for s, tf in expected],
        "results": rows,
        "status": "OK" if overall_ok else "FAIL",
    }
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if overall_ok else 1

if __name__ == "__main__":
    raise SystemExit(main())
