#!/usr/bin/env python3
"""
Connectivity & stability audit (read-only).
Reports:
- age of latest TF timestamp in run.log
- count of TF lines and provider_error lines
- count of HTTP 429/404 sightings
- alert loop heartbeat age (seconds since alert.log write)
"""
from __future__ import annotations
import os, re, json
from datetime import datetime, timezone

ROOT = os.path.expanduser("~/BotA")
RUN  = os.path.join(ROOT, "run.log")
ALERT= os.path.join(ROOT, "alert.log")

TF  = re.compile(r"^(H1|H4|D1):\s+t=([0-9:-]+\s?[0-9:]*)Z")
ERR = re.compile(r"provider_error=", re.I)
HTTP429 = re.compile(r"\b429\b")
HTTP404 = re.compile(r"\b404\b")

def read(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read().splitlines()
    except FileNotFoundError:
        return []

def ts_age_sec(ts_str: str) -> int:
    try:
        dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
        dt = dt.replace(tzinfo=timezone.utc)
        return int((datetime.now(timezone.utc) - dt).total_seconds())
    except Exception:
        return -1

def audit():
    lines = read(RUN)
    last_ts = None; tfc=0; errs=0; e429=0; e404=0
    for ln in lines:
        if ERR.search(ln): errs += 1
        if HTTP429.search(ln): e429 += 1
        if HTTP404.search(ln): e404 += 1
        m = TF.match(ln.strip())
        if m:
            tfc += 1
            ts = m.group(2)
            if ts and (last_ts is None or ts > last_ts):
                last_ts = ts
    age = ts_age_sec(last_ts) if last_ts else None

    try:
        mtime = os.path.getmtime(ALERT)
        beat_age = int(datetime.now(timezone.utc).timestamp() - mtime)
    except Exception:
        beat_age = None

    return {
        "runlog_last_tf_age_sec": age,
        "runlog_tf_lines": tfc,
        "runlog_provider_error_lines": errs,
        "runlog_http_429": e429,
        "runlog_http_404": e404,
        "alertlog_heartbeat_age_sec": beat_age
    }

if __name__ == "__main__":
    print(json.dumps(audit(), indent=2))
