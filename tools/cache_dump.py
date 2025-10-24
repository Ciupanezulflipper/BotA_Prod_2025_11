#!/usr/bin/env python3
"""
Bot A — cache_dump.py (Phase 3.1)
Reads $HOME/BotA/cache/{PAIR}.txt and prints H1/H4/D1 lines.
If cache missing, prints '(missing)' placeholders.
"""
from __future__ import annotations
import os, sys

ROOT = os.path.expanduser("~/BotA")
CACHE_DIR = os.path.join(ROOT, "cache")

def dump_pair(sym: str) -> None:
    p = os.path.join(CACHE_DIR, f"{sym}.txt")
    print(f"== {sym} ==")
    if not os.path.exists(p):
        print("  H1: (missing)")
        print("  H4: (missing)")
        print("  D1: (missing)")
        return
    try:
        with open(p, "r", encoding="utf-8") as f:
            lines = [l.rstrip("\n") for l in f.readlines()]
    except Exception:
        lines = []
    def get_line(prefix: str) -> str:
        for l in lines:
            if l.startswith(prefix + ":"):
                return l
        return f"{prefix}: (missing)"
    print("  " + get_line("H1"))
    print("  " + get_line("H4"))
    print("  " + get_line("D1"))

def main() -> int:
    syms = [s.upper() for s in sys.argv[1:]] or ["EURUSD", "GBPUSD"]
    for s in syms:
        dump_pair(s)
    return 0

if __name__ == "__main__":
    sys.exit(main())
