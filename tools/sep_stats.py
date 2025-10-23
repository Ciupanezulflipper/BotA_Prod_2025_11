import csv, os, sys, math, statistics as st
p = os.path.expanduser('~/BotA/trades.csv')
if not os.path.exists(p):
    print("No trades.csv yet"); sys.exit(0)

rows = []
with open(p) as f:
    for r in csv.reader(f):
        rows.append(r)

# Try to autodetect format (your file has both test-injection rows and SEP rows)
# SEP rows look like: ts, pair, dir, entry, tp, sl, atr, weighted
def parse_sep(r):
    try:
        ts, pair, side, entry, tp, sl, atr, weighted = r[:8]
        return {'ts':ts,'pair':pair,'side':side,'entry':float(entry),'tp':float(tp),
                'sl':float(sl),'atr':float(atr or '0'), 'weighted':float(weighted)}
    except Exception:
        return None

sep = [x for x in map(parse_sep, rows) if x]

print(f"Total rows: {len(rows)} | SEP rows detected: {len(sep)}")
if sep:
    last = sep[-1]
    rr = abs((last['tp']-last['entry'])/(last['entry']-last['sl'])) if last['entry']!=last['sl'] else float('nan')
    print(f"Last SEP: {last['ts']} {last['pair']} {last['side']}  ATR={last['atr']}  weighted={last['weighted']}  RR≈{rr:.2f}")

# Basic counts by side
from collections import Counter
by_pair = Counter([s['pair'] for s in sep])
print("By pair:", dict(by_pair))

# Rolling R estimates (theoretical) just to eyeball sizing consistency
def rr_est(s):
    try:
        return abs((s['tp']-s['entry'])/(s['entry']-s['sl']))
    except ZeroDivisionError:
        return float('nan')

rrs = [rr_est(s) for s in sep if not math.isnan(rr_est(s))]
if rrs:
    print(f"RR mean={st.mean(rrs):.2f}  median={st.median(rrs):.2f}  n={len(rrs)}")

# Show last 5 SEP rows for quick inspection
print("\nLast 5 SEP rows:")
for s in sep[-5:]:
    print(f"{s['ts']} {s['pair']} {s['side']} entry={s['entry']} tp={s['tp']} sl={s['sl']} atr={s['atr']} weighted={s['weighted']}")
