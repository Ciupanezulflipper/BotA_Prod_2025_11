#!/usr/bin/env python3
"""
Bot A — Phase 3: Cache population runner

Usage:
  python3 tools/cache_update.py [PAIRS...]
Default pairs: EURUSD GBPUSD

Behavior:
- For each pair, runs tools/run_pair.sh to append a fresh snapshot to run.log
- Then calls tools/data_fetch.py {PAIR} to parse the latest block and update cache
- Prints a compact PASS/FAIL summary
"""
from __future__ import annotations
import os, sys, subprocess, shlex

ROOT = os.path.expanduser("~/BotA")
TOOLS = os.path.join(ROOT, "tools")
RUN_PAIR = os.path.join(TOOLS, "run_pair.sh")
DATA_FETCH = os.path.join(TOOLS, "data_fetch.py")
RUN_LOG = os.path.join(ROOT, "run.log")

def run(cmd: list[str]) -> tuple[int, str, str]:
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    out, err = p.communicate()
    return p.returncode, out, err

def ensure_exec(path: str) -> None:
    if not os.path.exists(path):
        print(f"[FAIL] missing: {path}")
        sys.exit(2)

def process_pair(sym: str) -> tuple[bool, str]:
    # 1) emit snapshot into run.log
    rc, out, err = run([RUN_PAIR, sym])
    if rc != 0:
        return False, f"{sym}: run_pair rc={rc} err={err.strip()}"
    # 2) update cache via data_fetch
    rc, out, err = run(["python3", DATA_FETCH, sym])
    if rc != 0:
        return False, f"{sym}: data_fetch rc={rc} err={err.strip()}"
    # basic heuristic: data_fetch prints a line starting with the pair name or H1:
    ok = ("H1:" in out) or ("H4:" in out) or ("D1:" in out) or (sym in out)
    if not ok and "No snapshot block found" in out:
        return False, f"{sym}: data_fetch did not find snapshot block"
    return True, f"{sym}: cache updated"

def main() -> None:
    ensure_exec(RUN_PAIR)
    ensure_exec(DATA_FETCH)
    pairs = sys.argv[1:] or ["EURUSD", "GBPUSD"]
    passed = 0
    failed = 0
    notes: list[str] = []
    for s in pairs:
        ok, msg = process_pair(s.upper())
        if ok:
            passed += 1
            print(f"[OK] {msg}")
        else:
            failed += 1
            print(f"[FAIL] {msg}")
        notes.append(msg)
    print(f"summary: pass={passed} fail={failed}")
    sys.exit(0 if failed == 0 else 1)

if __name__ == "__main__":
    main()
