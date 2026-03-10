#!/usr/bin/env python3
"""Build FILE_REGISTRY.md from all .py and .sh files in BotA."""
import os, subprocess, re
from pathlib import Path

ROOT = Path.home() / "BotA"
OUT  = ROOT / "docs" / "FILE_REGISTRY.md"

CATS = {
    "ENTRY":     ["runner","start","boot","launch","entrypoint","main"],
    "SIGNAL":    ["signal","watcher","scoring","score","fusion","quality","filter"],
    "PROVIDER":  ["provider","fetch","yahoo","twelve","alpha","finnhub","stooq","ohlc"],
    "TELEGRAM":  ["tele","telegram","tg_","send","card","alert","notify"],
    "INDICATOR": ["indicator","ema","rsi","macd","atr","ta_","build_ind"],
    "ACCURACY":  ["accuracy","audit","trade","backtest","replay","journal","trades"],
    "INFRA":     ["cron","rotate","log","health","heartbeat","status","daemon","daemonctl"],
    "ENV":       ["env","config","token","chat_id","fix_token"],
    "SMOKE":     ["smoke","test","probe","accept","sanity","check","proof","verify","diag"],
    "DOCS":      ["prd","rulebook","blueprint","readme","map","step"],
}

def categorize(name: str) -> str:
    nl = name.lower()
    for cat, keys in CATS.items():
        if any(k in nl for k in keys):
            return cat
    return "OTHER"

def get_docstring(path: Path) -> str:
    try:
        lines = path.read_text(errors="ignore").splitlines()
        # First comment or docstring
        for i, line in enumerate(lines[:20]):
            l = line.strip()
            if l.startswith('"""') or l.startswith("'''"):
                # grab rest of docstring
                rest = " ".join(lines[i:i+3])
                clean = re.sub(r'[\'\"]{3}', '', rest).strip()
                return clean[:120]
            if l.startswith("#") and len(l) > 5 and i < 10:
                return l.lstrip("#").strip()[:120]
    except Exception:
        pass
    return ""

files = []
for p in sorted(ROOT.rglob("*.py")) + sorted(ROOT.rglob("*.sh")):
    if any(x in str(p) for x in ["__pycache__",".bak",".old",".gold","node_modules"]):
        continue
    rel = p.relative_to(ROOT)
    cat = categorize(p.name)
    doc = get_docstring(p)
    files.append((cat, str(rel), p.name, doc))

files.sort(key=lambda x: (x[0], x[1]))

lines = ["# BotA File Registry\n",
         f"_Auto-generated. {len(files)} files. Edit descriptions manually as needed._\n\n"]

cur_cat = None
for cat, rel, name, doc in files:
    if cat != cur_cat:
        lines.append(f"\n## {cat}\n")
        lines.append(f"| File | Description |\n|---|---|\n")
        cur_cat = cat
    lines.append(f"| `{rel}` | {doc or '—'} |\n")

OUT.write_text("".join(lines))
print(f"Written: {OUT} ({len(files)} files across {len(set(f[0] for f in files))} categories)")
