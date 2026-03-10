import csv

def _read_ohlc(path):
    with open(path, "r", newline="") as f:
        rows = list(csv.reader(f))
    # detect header
    header_lower = [h.lower() for h in rows[0]] if rows else []
    start = 1 if ("close" in header_lower and "open" in header_lower and "high" in header_lower and "low" in header_lower) else 0
    o,h,l,c = [],[],[],[]
    for row in rows[start:]:
        if len(row) < 5: 
            continue
        try:
            o.append(float(row[1])); h.append(float(row[2])); l.append(float(row[3])); c.append(float(row[4]))
        except: 
            continue
    return o,h,l,c

def _ema(series, period):
    k = 2.0/(period+1.0)
    out=[]; e=None
    for x in series:
        e = x if e is None else (x-e)*k + e
        out.append(e)
    return out

def macd_12269(close):
    slow,fast,signal=26,12,9
    if len(close) < slow+signal+5: return None
    ema_f = _ema(close, fast)
    ema_s = _ema(close, slow)
    macd_line = [a-b for a,b in zip(ema_f[-len(ema_s):], ema_s)]
    sig = _ema(macd_line, signal)
    hist = [m-s for m,s in zip(macd_line[-len(sig):], sig)]
    return macd_line[-1], sig[-1], hist[-1]

def rsi_14(close):
    p=14
    if len(close) < p+5: return None
    gains, losses = [], []
    for i in range(1,len(close)):
        ch = close[i]-close[i-1]
        gains.append(max(ch,0.0)); losses.append(max(-ch,0.0))
    avg_g = sum(gains[:p])/p
    avg_l = sum(losses[:p])/p
    for i in range(p, len(gains)):
        avg_g = (avg_g*(p-1)+gains[i])/p
        avg_l = (avg_l*(p-1)+losses[i])/p
    rs = (avg_g/avg_l) if avg_l!=0 else float('inf')
    return 100.0 - (100.0/(1.0+rs))

def adx_14(high, low, close):
    p=14; n=len(close)
    if n < p*3: return None
    tr=[]; pdm=[]; mdm=[]
    for i in range(1,n):
        up = high[i]-high[i-1]
        dn = low[i-1]-low[i]
        pdm.append(up if (up>dn and up>0) else 0.0)
        mdm.append(dn if (dn>up and dn>0) else 0.0)
        tr_i = max(high[i]-low[i], abs(high[i]-close[i-1]), abs(low[i]-close[i-1]))
        tr.append(tr_i)
    def wilder(seq, p):
        s=sum(seq[:p]); out=[s]
        for x in seq[p:]:
            s = s - (s/p) + x
            out.append(s)
        return out
    trp = wilder(tr, p)
    pdp = wilder(pdm, p)
    mdp = wilder(mdm, p)
    dip = [ (pval/t)*100.0 if t>0 else 0.0 for pval,t in zip(pdp,trp) ]
    dim = [ (mval/t)*100.0 if t>0 else 0.0 for mval,t in zip(mdp,trp) ]
    dx = [ (abs(a-b)/(a+b))*100.0 if (a+b)>0 else 0.0 for a,b in zip(dip,dim) ]
    if len(dx) < p: return None
    adx = sum(dx[:p])/p
    for x in dx[p:]:
        adx = (adx*(p-1)+x)/p
    return adx

def latest_indicators(path):
    o,h,l,c = _read_ohlc(path)
    m = macd_12269(c)
    r = rsi_14(c)
    a = adx_14(h,l,c)
    return {"macd": m, "rsi": r, "adx": a, "rows": len(c)}
