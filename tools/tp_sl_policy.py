#!/data/data/com.termux/files/usr/bin/python3
import sys, re, statistics as st

"""
Usage:
  cat <<'TXT' | python3 tools/tp_sl_policy.py SELL
  === GBPUSD snapshot ===
  H1: ... close=1.33356 EMA9=... EMA21=... RSI14=... MACD_hist=... vote=-1 ...
  H4: ... vote=-1 ...
  D1: ... vote=-1 ...
  Signal: SELL
  Entry: 1.33356
  SL: 1.34278
  TP: 1.32126
  ATR: 0.00615
  TXT

It will propose snapped SL/TP to nearest recent swing if within 0.5×ATR of the ATR-based levels.
"""

SIDE = sys.argv[1].upper() if len(sys.argv)>1 else "SELL"
text = sys.stdin.read()

def grab(pat, default=None, cast=float):
    m = re.search(pat, text, re.I)
    if not m: return default
    try: return cast(m.group(1))
    except: return default

entry = grab(r"\bEntry:\s*([0-9]+\.[0-9]+)")
sl0   = grab(r"\bSL:\s*([0-9]+\.[0-9]+)")
tp0   = grab(r"\bTP:\s*([0-9]+\.[0-9]+)")
atr   = grab(r"\bATR:\s*([0-9]+\.[0-9]+)", 0.0)

if not all([entry, sl0, tp0, atr]):
    print("Not enough fields to compute.")
    sys.exit(0)

# crude swing extraction: look for prior "close=" lines and take local maxima/minima
closes = [float(x) for x in re.findall(r"close=([0-9]+\.[0-9]+)", text)]
swings_hi, swings_lo = [], []
# simple three-point swing: c[i-1] < c[i] > c[i+1] or c[i-1] > c[i] < c[i+1]
for i in range(1, len(closes)-1):
    if closes[i] > closes[i-1] and closes[i] > closes[i+1]:
        swings_hi.append(closes[i])
    if closes[i] < closes[i-1] and closes[i] < closes[i+1]:
        swings_lo.append(closes[i])

snap_window = 0.5 * atr

def nearest_level(levels, target):
    if not levels: return None, 999
    d = [(abs(x-target), x) for x in levels]
    d.sort()
    return d[0][1], d[0][0]

sl, tp = sl0, tp0
reason = []

if SIDE=="SELL":
    # SL near swing high?
    lvl, dist = nearest_level(swings_hi, sl0)
    if lvl and dist <= snap_window:
        sl = lvl; reason.append(f"SL snapped to swing high {lvl:.5f}")
    # TP near swing low?
    lvl, dist = nearest_level(swings_lo, tp0)
    if lvl and dist <= snap_window:
        tp = lvl; reason.append(f"TP snapped to swing low {lvl:.5f}")
else:
    # BUY
    lvl, dist = nearest_level(swings_lo, sl0)
    if lvl and dist <= snap_window:
        sl = lvl; reason.append(f"SL snapped to swing low {lvl:.5f}")
    lvl, dist = nearest_level(swings_hi, tp0)
    if lvl and dist <= snap_window:
        tp = lvl; reason.append(f"TP snapped to swing high {lvl:.5f}")

rr = abs((tp-entry)/(entry-sl)) if entry!=sl else float('nan')

print("=== TP/SL Policy Suggestion ===")
print(f"Side: {SIDE}")
print(f"Entry: {entry:.5f}")
print(f"ATR: {atr:.5f}  (snap window ±{snap_window:.5f})")
print(f"Original SL/TP: {sl0:.5f} / {tp0:.5f}")
print(f"Suggested SL/TP: {sl:.5f} / {tp:.5f}   RR≈{rr:.2f}")
if reason:
    print("Notes:", "; ".join(reason))
else:
    print("Notes: ATR levels left unchanged (no nearby swing within 0.5×ATR).")
