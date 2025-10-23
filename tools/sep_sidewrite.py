import os, sys, csv, time

def is_num(x):
    try:
        float(x); return True
    except Exception:
        return False

if len(sys.argv) < 8:
    print("[SITE] sidewrite skipped: not enough args", file=sys.stderr)
    sys.exit(2)

pair, side, entry, tp, sl, atr, weighted = sys.argv[1:8]

# sanity check
if not (pair and side and all(map(is_num, [entry, tp, sl, atr]))):
    with open(os.path.expanduser('~/BotA/run.log'), 'a') as lf:
        lf.write(f"[SITE] sidewrite skipped: bad fields "
                 f"pair={pair} side={side} E={entry} TP={tp} SL={sl} ATR={atr}\n")
    sys.exit(0)

ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
row = [ts, pair, side, entry, tp, sl, atr, weighted]

path = os.path.expanduser('~/BotA/trades.csv')
os.makedirs(os.path.dirname(path), exist_ok=True)

with open(path, 'a', newline='') as f:
    csv.writer(f).writerow(row)

with open(os.path.expanduser('~/BotA/run.log'), 'a') as lf:
    lf.write(f"[SITE] sidewrite ok: {row}\n")
