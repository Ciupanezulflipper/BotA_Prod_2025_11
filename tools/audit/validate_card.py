#!/usr/bin/env python3
from __future__ import annotations
import sys, re, json

REQ = [
  r"^📊 [A-Z]{3}/[A-Z]{3} \((M1|M5|M15|M30|H1|H4|D1)\)$",
  r"^🕒 Signal Time: \d{4}-\d{2}-\d{2} \d{2}:\d{2} UTC$",
  r"^📈 Action: (✅ BUY|❌ SELL|⏸️ WAIT)$",
  r"^📊 Score: \d{1,2}/16 \+ \d{1,2}/6$",
  r"^🧠 Reason: .+",
  r"^⚠️ Risk: .+",
  r"^📉 Spread: (n/a|\d+(\.\d+)? pips)$"
]

def main():
    text = sys.stdin.read().strip().splitlines()
    if len(text) < 7:
        print(json.dumps({"ok": False, "error": "too few lines", "got": text}, indent=2))
        sys.exit(1)
    results = []
    for i,pat in enumerate(REQ):
        ok = bool(re.match(pat, text[i]))
        results.append({"line": i+1, "ok": ok, "expected": pat, "got": text[i] if i < len(text) else ""})
    ok_all = all(r["ok"] for r in results)
    print(json.dumps({"ok": ok_all, "results": results}, indent=2))
    sys.exit(0 if ok_all else 2)

if __name__ == "__main__":
    main()
