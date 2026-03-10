# -*- coding: utf-8 -*-
import os, csv, math, statistics as st
from collections import defaultdict

P = os.environ.get("SEP_CSV_PATH", os.path.expanduser("~/BotA/trades_sep.csv"))
if not os.path.exists(P):
    print("No SEP CSV found at", P); raise SystemExit

rows = []
with open(P) as f:
    for r in csv.reader(f):
        if r: rows.append(r)

def parse_sep(r):
    # ts,pair,side,entry,tp,sl,atr,weighted
    try:
        ts, pair, side, entry, tp, sl, atr, weighted = r[:8]
        return dict(ts=ts, pair=pair, side=side, entry=float(entry), tp=float(tp),
                    sl=float(sl), atr=float(atr or 0), weighted=float(weighted or 0))
    except Exception:
        return None

sep = [x for x in map(parse_sep, rows) if x]

print(f"SEP rows: {len(sep)}  (from {P})")

def rr(s):
    try:
        return abs((s['tp']-s['entry'])/(s['entry']-s['sl']))
    except ZeroDivisionError:
        return float('nan')

rrs = [rr(s) for s in sep if not math.isnan(rr(s))]
if rrs:
    print(f"RR: mean={st.mean(rrs):.2f}  median={st.median(rrs):.2f}  n={len(rrs)}")

from collections import Counter
by_pair = Counter([s['pair'] for s in sep])
print("By pair:", dict(by_pair))

print("\nLast 5:")
for s in sep[-5:]:
    print(f"{s['ts']} {s['pair']} {s['side']} E={s['entry']} TP={s['tp']} SL={s['sl']} ATR={s['atr']} W={s['weighted']}  RR≈{rr(s):.2f}")
