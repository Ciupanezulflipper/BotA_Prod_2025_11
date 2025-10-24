# -*- coding: utf-8 -*-
import os, csv, time
from collections import defaultdict

HOME = os.path.expanduser("~")
CSV = os.path.join(HOME, "BotA", "trades.csv")
PAUSE_FILE = os.path.join(HOME, ".sep.pause")

if not os.path.exists(CSV):
    print("no trades.csv yet"); raise SystemExit

rows = []
with open(CSV) as f:
    for r in csv.reader(f):
        if r: rows.append(r)

def parse_outcome(r):
    # Extended rows have outcome and R at positions ~10/12 in your sample
    try:
        outcome = r[10].strip().upper()
        R = float(r[12])
        pair = r[1].replace("/","")
        day  = r[0][:10]
        return dict(day=day, pair=pair, outcome=outcome, R=R)
    except Exception:
        return None

outs = [x for x in map(parse_outcome, rows) if x]
if not outs:
    print("No outcome rows found; nothing to pause yet.")
    raise SystemExit

today = time.strftime("%Y-%m-%d", time.gmtime())
by_pair_R = defaultdict(float)
for o in outs:
    if o["day"] == today:
        by_pair_R[o["pair"]] += o["R"]

to_pause = [p for p,r in by_pair_R.items() if r <= -3.0]
tooth = to_pause
if not tooth:
    print("No pairs exceed -3R today.")
else:
    # write pause file with all pairs that need pausing; keep others if already present
    existing = {}
    if os.path.exists(PAUSE_FILE):
        with open(PAUSE_FILE) as f:
            for line in f:
                line=line.strip()
                if line.startswith("export PAUSE_"):
                    k,v = line.replace("export ","").split("=")
                    existing[k]=v
    for p in to_pause:
        existing[f"PAUSE_{p}"]="1"
    with open(PAUSE_FILE,"w") as f:
        for k,v in sorted(existing.items()):
            f.write(f"export {k}={v}\n")
    print("Paused:", ", ".join(to_pause))
