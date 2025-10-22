# Lightweight indicator pack (append-only module)
# Inputs: lists of floats; returns same-length lists (None for warmup)

def sma(x, n):
    out=[]; s=0.0; q=[]
    for v in x:
        q.append(v); s+=v
        if len(q)>n: s-=q.pop(0)
        out.append(s/len(q) if len(q)==n else None)
    return out

def ema(x, n):
    out=[]; k=2/(n+1); e=None
    for v in x:
        e = v if e is None else (v*k + e*(1-k))
        out.append(e)
    return out

def rsi(x, n=14):
    out=[]; up=0.0; dn=0.0; upq=[]; dnq=[]; prev=None
    for v in x:
        if prev is None:
            out.append(None); prev=v; continue
        ch=v-prev; prev=v
        upq.append(max(ch,0.0)); dnq.append(max(-ch,0.0))
        if len(upq)>n: upq.pop(0); dnq.pop(0)
        if len(upq)<n: out.append(None); continue
        up=sum(upq)/n; dn=sum(dnq)/n
        rs = (up/dn) if dn>0 else 100.0
        out.append(100-100/(1+rs))
    return out

def stoch_rsi(x, n=14, k=3, d=3):
    r = rsi(x, n)
    # raw stoch of RSI
    sr=[]; win=[]
    for v in r:
        win.append(v)
        if len(win)>n: win.pop(0)
        if None in win or len(win)<n: sr.append(None); continue
        lo=min(win); hi=max(win); sr.append(0 if hi==lo else (v-lo)/(hi-lo)*100)
    # %K, %D
    def ma(seq, m):
        o=[]; w=[]
        for v in seq:
            w.append(v)
            if len(w)>m: w.pop(0)
            o.append(None if (len(w)<m or None in w) else sum(w)/m)
        return o
    kline=ma(sr,k); dline=ma(kline,d)
    return kline, dline

def macd(x, fast=5, slow=13, sig=9):
    ef=ema(x, fast); es=ema(x, slow)
    mac=[(a-b) if a is not None and b is not None else None for a,b in zip(ef,es)]
    sigl=ema([v if v is not None else 0 for v in mac], sig)
    hist=[(m-s) if m is not None else None for m,s in zip(mac,sigl)]
    return mac, sigl, hist

def atr(h, l, c, n=14):
    trs=[]; prev=None
    for hi,lo,cl in zip(h,l,c):
        if prev is None:
            tr=hi-lo
        else:
            tr=max(hi-lo, abs(hi-prev), abs(lo-prev))
        trs.append(tr); prev=cl
    # SMA ATR
    out=[]; q=[]; s=0.0
    for v in trs:
        q.append(v); s+=v
        if len(q)>n: s-=q.pop(0)
        out.append(s/len(q) if len(q)==n else None)
    return out

def bbands(x, n=20, mult=2):
    out_mid=[]; out_up=[]; out_dn=[]
    win=[]
    for v in x:
        win.append(v)
        if len(win)>n: win.pop(0)
        if len(win)<n: out_mid.append(None); out_up.append(None); out_dn.append(None); continue
        m=sum(win)/n
        var=sum((w-m)**2 for w in win)/n
        sd=var**0.5
        out_mid.append(m); out_up.append(m+mult*sd); out_dn.append(m-mult*sd)
    return out_mid, out_up, out_dn
