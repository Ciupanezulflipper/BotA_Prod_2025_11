# -*- coding: utf-8 -*-
import os, csv

SRC = os.path.expanduser('~/BotA/trades.csv')
SEP_OUT = os.path.expanduser('~/BotA/trades_sep.csv')
HIST_OUT = os.path.expanduser('~/BotA/trades_hist.csv')

if not os.path.exists(SRC):
    print("no trades.csv"); raise SystemExit

sep_rows = []
hist_rows = []
with open(SRC, newline='') as f:
    for r in csv.reader(f):
        if not r: 
            continue
        # SEP short row schema: 8 columns
        if len(r) == 8:
            # quick sanity: entry/tp/sl numeric?
            try:
                float(r[3]); float(r[4]); float(r[5])
                sep_rows.append(r)
            except Exception:
                hist_rows.append(r)
        else:
            hist_rows.append(r)

# de-dupe SEP rows on exact tuple
seen = set(); dedup = []
for r in sep_rows:
    key = tuple(r)
    if key in seen: 
        continue
    seen.add(key); dedup.append(r)

with open(SEP_OUT, 'w', newline='') as f:
    csv.writer(f).writerows(dedup)

with open(HIST_OUT, 'w', newline='') as f:
    csv.writer(f).writerows(hist_rows)

print(f"Wrote {len(dedup)} SEP rows -> {SEP_OUT}")
print(f"Wrote {len(hist_rows)} HIST rows -> {HIST_OUT}")
