#!/usr/bin/env python3
import os, json, sys
from pathlib import Path

CFG = Path(os.path.expanduser("~/bot-a/config/policy.json"))
if not CFG.exists():
    print("No policy.json found at", CFG)
    sys.exit(0)

with CFG.open("r", encoding="utf-8") as f:
    j = json.load(f)

print("=== Active policy.json ===")
print(json.dumps(j, indent=2, sort_keys=True))
print("\nNotes:")
print("- Keys must match exactly (DECAY_HALF_LIFE_SEC, VOL_WINDOW_SEC, etc.)")
print("- Per-pair overrides are under PAIRS, e.g. XAUUSD")
