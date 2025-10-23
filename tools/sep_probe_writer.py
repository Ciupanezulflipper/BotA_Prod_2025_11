import os, re, csv, time, sys

# Read the last "strong" message you just sent (paste content if you want manual test)
text = """[SEP TEST] ✅ Strong example (expect ALLOW)
=== GBPUSD snapshot ===
H1: ... RSI14=38.2 ... vote=-1
H4: ... RSI14=41.0 ... vote=-1
D1: ... RSI14=40.4 ... vote=-1

Signal: SELL
Entry: 1.33333
SL: 1.34151
TP: 1.32133
ATR: 0.0061
RR: 1:1.67
Votes: {'H1': -1, 'H4': -1, 'D1': -1}
"""

def grab(pat):
    m = re.search(pat, text, re.I)
    return m.group(1) if m else None

pair = grab(r"===\s*([A-Z]{6}|[A-Z]+/[A-Z]+)\s*snapshot")
direction = grab(r"\bSignal:\s*(BUY|SELL)\b")
entry = grab(r"\bEntry:\s*([0-9]+\.[0-9]+)")
tp = grab(r"\bTP:\s*([0-9]+\.[0-9]+)")
sl = grab(r"\bSL:\s*([0-9]+\.[0-9]+)")
atr = grab(r"\bATR:\s*([0-9]+\.[0-9]+)") or ""
weighted = "-6"  # example

row = [time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), pair or "", direction or "", entry or "", tp or "", sl or "", atr, weighted]

path=os.path.expanduser('~/BotA/trades.csv')
os.makedirs(os.path.dirname(path), exist_ok=True)
with open(path,'a',newline='') as f:
    csv.writer(f).writerow(row)

print("WROTE:", row)
