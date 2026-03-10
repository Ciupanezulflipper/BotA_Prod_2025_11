import csv, math, sys
from collections import deque

PATH = sys.argv[1] if len(sys.argv) > 1 else "/data/data/com.termux/files/home/bot-a/data/candles/EURUSD_M15.csv"

def read_csv(path):
    with open(path, "r", newline="") as f:
        r = csv.reader(f)
        rows = list(r)
    # Detect header
    header = [h.lower() for h in rows[0]]
    start = 1
    if "close" not in header or "open" not in header or "high" not in header or "low" not in header:
        # assume no header; synthesize
        header = ["timestamp","open","high","low","close","volume"]
        start = 0
    o,h,l,c = [],[],[],[]
    for row in rows[start:]:
        if len(row) < 5: 
            continue
        try:
            o.append(float(row[1])); h.append(float(row[2])); l.append(float(row[3])); c.append(float(row[4]))
        except:
            continue
    return o,h,l,c

def ema(series, period):
    k = 2.0/(period+1.0)
    out=[]; ema_val=None
    for x in series:
        ema_val = x if ema_val is None else (x - ema_val)*k + ema_val
        out.append(ema_val)
    return out

def macd(close, fast=12, slow=26, signal=9):
    if len(close) < slow+signal+5: return None
    ema_fast = ema(close, fast)
    ema_slow = ema(close, slow)
    macd_line = [a-b for a,b in zip(ema_fast[-len(ema_slow):], ema_slow)]
    sig = ema(macd_line, signal)
    hist = [m-s for m,s in zip(macd_line[-len(sig):], sig)]
    return macd_line[-1], sig[-1], hist[-1]

def rsi(close, period=14):
    if len(close) < period+5: return None
    gains, losses = [], []
    for i in range(1,len(close)):
        ch = close[i]-close[i-1]
        gains.append(max(ch,0.0)); losses.append(max(-ch,0.0))
    # Wilder smoothing
    avg_g = sum(gains[:period])/period
    avg_l = sum(losses[:period])/period
    for i in range(period, len(gains)):
        avg_g = (avg_g*(period-1) + gains[i]) / period
        avg_l = (avg_l*(period-1) + losses[i]) / period
    rs = (avg_g / avg_l) if avg_l != 0 else float('inf')
    rsi_val = 100.0 - (100.0/(1.0+rs))
    return rsi_val

def adx(high, low, close, period=14):
    n=len(close)
    if n < period*3: return None
    tr=[]; plus_dm=[]; minus_dm=[]
    for i in range(1,n):
        up = high[i]-high[i-1]
        dn = low[i-1]-low[i]
        plus_dm.append(up if (up>dn and up>0) else 0.0)
        minus_dm.append(dn if (dn>up and dn>0) else 0.0)
        tr_i = max(high[i]-low[i], abs(high[i]-close[i-1]), abs(low[i]-close[i-1]))
        tr.append(tr_i)
    # Wilder smoothing
    def wilder(sm, period):
        s=sum(sm[:period]); out=[s]
        for x in sm[period:]:
            s = s - (s/period) + x
            out.append(s)
        return out
    tr14 = wilder(tr, period)
    plus14 = wilder(plus_dm, period)
    minus14 = wilder(minus_dm, period)
    di_plus = [ (p/t)*100.0 if t>0 else 0.0 for p,t in zip(plus14, tr14) ]
    di_minus= [ (m/t)*100.0 if t>0 else 0.0 for m,t in zip(minus14, tr14) ]
    dx = [ (abs(p-m)/(p+m))*100.0 if (p+m)>0 else 0.0 for p,m in zip(di_plus, di_minus) ]
    # Smooth DX into ADX
    if len(dx) < period: return None
    adx_val = sum(dx[:period])/period
    for x in dx[period:]:
        adx_val = (adx_val*(period-1)+x)/period
    return adx_val

o,h,l,c = read_csv(PATH)
print("rows:", len(c))
m = macd(c)
r = rsi(c)
a = adx(h,l,c)
print("MACD(12,26,9):", m)
print("RSI(14):", r)
print("ADX(14):", a)
