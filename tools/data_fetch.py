#!/usr/bin/env python3
"""
Bot A — data_fetch.py (Phase 3.1)
Parses the latest snapshot block for a given PAIR from run.log and writes cache.

Input:
  python3 tools/data_fetch.py EURUSD

Behavior:
- Scans $HOME/BotA/run.log for the last block:
    === {PAIR} snapshot ===
    H1: ...
    H4: ...
    D1: ...
- Validates lines and writes cache file:
    $HOME/BotA/cache/{PAIR}.txt
    (three lines starting with H1:/H4:/D1:)
- Prints a compact summary to STDOUT.
- Exit codes:
    0 on success, 1 if block not found or incomplete.

Note: This does NOT change your emit format — it only reads run.log.
"""
from __future__ import annotations
import os, sys, re

ROOT = os.path.expanduser("~/BotA")
RUN_LOG = os.path.join(ROOT, "run.log")
CACHE_DIR = os.path.join(ROOT, "cache")

HEADER_RE = re.compile(r"^===\s+([A-Z/]+)\s+snapshot\s+===$")
TF_RE = re.compile(r"^(H1|H4|D1):\s+.*")

def read_log(path: str) -> list[str]:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read().splitlines()
    except FileNotFoundError:
        return []

def find_latest_block(lines: list[str], pair: str) -> tuple[int, dict[str,str]] | None:
    """
    Returns (header_index, tf_dict) where tf_dict has keys 'H1','H4','D1'
    for the most recent block of the requested pair.
    """
    pair_u = pair.upper()
    header_idxs: list[int] = []
    for i, line in enumerate(lines):
        m = HEADER_RE.match(line.strip())
        if not m: 
            continue
        sym = m.group(1).replace("/", "")  # normalize EUR/USD -> EURUSD for compare
        if sym == pair_u:
            header_idxs.append(i)
    if not header_idxs:
        return None
    start = header_idxs[-1]
    tf: dict[str, str] = {}
    # Collect subsequent lines until next header or end
    i = start + 1
    while i < len(lines):
        s = lines[i].strip()
        if HEADER_RE.match(s):
            break
        m = TF_RE.match(s)
        if m:
            lbl = m.group(1)
            # keep only the first occurrence per TF (the block's line)
            if lbl not in tf:
                tf[lbl] = s
        i += 1
    # Require all three
    if all(k in tf for k in ("H1","H4","D1")):
        return start, tf
    return None

def write_cache(pair: str, tf: dict[str,str]) -> str:
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = os.path.join(CACHE_DIR, f"{pair.upper()}.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(tf["H1"] + "\n")
        f.write(tf["H4"] + "\n")
        f.write(tf["D1"] + "\n")
    return path

def main() -> int:
    if len(sys.argv) < 2:
        print("usage: data_fetch.py EURUSD", file=sys.stderr)
        return 1
    pair = sys.argv[1].upper()

    lines = read_log(RUN_LOG)
    if not lines:
        print(f"[data_fetch] ❌ run.log not found at {RUN_LOG}")
        return 1

    found = find_latest_block(lines, pair)
    if not found:
        print(f"[data_fetch] ❌ No snapshot block found for {pair}.")
        print("[data_fetch] Tip: ensure your runner prints:\n  === EURUSD snapshot ===\n  H1: ...\n  H4: ...\n  D1: ...")
        return 1

    _, tf = found

    # Write cache
    cache_path = write_cache(pair, tf)

    # Emit compact summary
    print(f"== {pair} ==")
    print("  " + tf["H1"])
    print("  " + tf["H4"])
    print("  " + tf["D1"])
    print(f"[data_fetch] ✅ cache -> {cache_path}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
