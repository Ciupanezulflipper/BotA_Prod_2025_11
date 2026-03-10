#!/usr/bin/env python3
"""
Signal actionability metrics (read-only).
Computes how often recent early_watch weights meet/exceed MIN_WEIGHT
and counts alert pushes seen in alert.log. No trade P/L is inferred.

Env:
  WINDOW_H=48        # hours to inspect from alert.log (approximate by file tail)
  MIN_WEIGHT=2       # threshold for "actionable"
"""
from __future__ import annotations
import os, re, json, statistics, subprocess
from datetime import datetime, timezone, timedelta
from typing import List

ROOT = os.path.expanduser("~/BotA")
ALERT = os.path.join(ROOT, "alert.log")
TOOLS = os.path.join(ROOT, "tools")

EW_RE   = re.compile(r'^\[early_watch\]\s+([A-Z/]+)\s+weighted=([\-0-9]+)\s+bias=', re.I)
PUSH_RE = re.compile(r'^📣 <b>BotA Alerts</b>', re.I)

def utcnow():
    return datetime.now(timezone.utc)

def read_alert_tail() -> List[str]:
    # Read entire file; alert.log is small. If missing, return empty.
    try:
        with open(ALERT, "r", encoding="utf-8", errors="replace") as f:
            return f.read().splitlines()
    except FileNotFoundError:
        return []

def parse_alert_log(lines: List[str], hours: int):
    cutoff = utcnow() - timedelta(hours=hours)
    # We don't have per-line timestamps; use whole file window (best-effort)
    ew_lines, pushes = [], 0
    for ln in lines:
        if EW_RE.search(ln):
            ew_lines.append(ln.rstrip())
        if PUSH_RE.search(ln):
            pushes += 1
    return ew_lines, pushes

def replay_live_candidates() -> int:
    # Snapshot of current pipeline (best-effort)
    try:
        p = subprocess.run(
            ["python3", os.path.join(TOOLS, "early_watch.py"), "--ignore-session"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=20
        )
        q = subprocess.run(
            ["python3", os.path.join(TOOLS, "alert_rules.py")],
            input=p.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=20
        )
        data = json.loads(q.stdout or "[]")
        return len(data) if isinstance(data, list) else 0
    except Exception:
        return 0

def compute_actionable(min_weight: int, window_h: int):
    lines = read_alert_tail()
    ew_lines, pushes = parse_alert_log(lines, window_h)

    weights = []
    actionable = 0
    for ln in ew_lines:
        m = EW_RE.search(ln)
        if not m:
            continue
        try:
            w = int(m.group(2))
        except Exception:
            continue
        weights.append(w)
        if abs(w) >= min_weight:
            actionable += 1

    hist_total = len(ew_lines)
    hist_rate = (actionable / hist_total * 100.0) if hist_total else 0.0
    median_w = statistics.median(weights) if weights else 0
    p95_w = statistics.quantiles(weights, n=20)[18] if len(weights) >= 20 else median_w

    return {
        "window_h": window_h,
        "hist_ew_count": hist_total,
        "hist_actionable_count": actionable,
        "hist_actionable_rate_pct": round(hist_rate, 2),
        "hist_median_weight": median_w,
        "hist_p95_weight": p95_w,
        "recent_live_candidates": replay_live_candidates(),
        "alert_push_messages_seen": pushes
    }

def main():
    window_h = int(os.getenv("WINDOW_H", "48"))
    min_weight = int(os.getenv("MIN_WEIGHT", "2"))
    stats = compute_actionable(min_weight=min_weight, window_h=window_h)
    print(json.dumps(stats, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
