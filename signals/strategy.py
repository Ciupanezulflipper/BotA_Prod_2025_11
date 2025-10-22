# Lightweight multi-indicator scorer for scalping confluence
# No heavy deps; simple math on close prices

from math import sqrt
from data.ohlcv import fetch

def ema(series, period):
    if not series: return []
    k = 2/(period+1)
    out = [series[0]]
    for x in series[1:]:
        out.append(out[-1] + k*(x - out[-1]))
    return out

def rsi(series, period=14):
    if len(series) < period+1: return []
    gains, losses = [], []
    for i in range(1, period+1):
        ch = series[i] - series[i-1]
        gains.append(max(ch,0)); losses.append(max(-ch,0))
    avg_g, avg_l = sum(gains)/period, sum(losses)/period
    rsis = []
    for i in range(period+1, len(series)):
        ch = series[i] - series[i-1]
        g, l = (max(ch,0), max(-ch,0))
        avg_g = (avg_g*(period-1)+g)/period
        avg_l = (avg_l*(period-1)+l)/period
        rs = avg_g/(avg_l if avg_l else 1e-9)
        rsis.append(100 - 100/(1+rs))
    return [None]*(period+1) + rsis

def stoch_rsi(series, period=14, k=3, d=3):
    rs = rsi(series, period)
    vals = []
    for i in range(len(series)):
        if i < period*2: vals.append(None); continue
        win = [x for x in rs[i-period+1:i+1] if x is not None]
        if not win: vals.append(None); continue
        mn, mx = min(win), max(win)
        s = 0 if mx==mn else (win[-1]-mn)/(mx-mn)*100
        vals.append(s)
    # %K simple MA(k), %D MA(d) of %K
    def sma(a, p):
        out=[None]*len(a); s=0; q=[]
        for i,x in enumerate(a):
            if x is None: out[i]=None; continue
            q.append(x); s+=x
            if len(q)>p: s-=q.pop(0)
            out[i] = s/len(q)
        return out
    K = sma(vals, k)
    D = sma(K, d)
    return K, D

def macd(series, fast=5, slow=13, sig=9):
    if len(series)<slow+sig: return [],[],[]
    ef, es = ema(series, fast), ema(series, slow)
    mac = [ (a-b) for a,b in zip(ef, es) ]
    # simple EMA for signal on mac
    s = []
    k = 2/(sig+1)
    for i,x in enumerate(mac):
        if i==0: s.append(x)
        else: s.append(s[-1] + k*(x - s[-1]))
    hist = [a-b for a,b in zip(mac,s)]
    return mac, s, hist

def atr(high, low, close, period=14):
    if len(close)<period+1: return []
    trs=[high[0]-low[0]]
    for i in range(1,len(close)):
        tr = max(high[i]-low[i], abs(high[i]-close[i-1]), abs(low[i]-close[i-1]))
        trs.append(tr)
    out=[trs[0]]
    k=2/(period+1)
    for x in trs[1:]:
        out.append(out[-1]+k*(x-out[-1]))
    return out

def bbands(series, period=20, mult=2):
    if len(series)<period: return [],[],[]
    means=[]; stds=[]
    from collections import deque
    q=deque(); s=0; s2=0
    for x in series:
        q.append(x); s+=x; s2+=x*x
        if len(q)>period:
            y=q.popleft(); s-=y; s2-=y*y
        if len(q)==period:
            m=s/period; v=max(s2/period - m*m, 0); sd=sqrt(v)
            means.append(m); stds.append(sd)
        else:
            means.append(None); stds.append(None)
    upper=[ m+mult*sd if m is not None else None for m,sd in zip(means,stds)]
    lower=[ m-mult*sd if m is not None else None for m,sd in zip(means,stds)]
    return lower, means, upper

def score_symbol(symbol="EURUSD", tf="5min"):
    candles = fetch(symbol, tf, limit=220)
    if len(candles)<60:
        return {"ok":False, "text": f"{symbol}: not enough data"}

    c = [x["c"] for x in candles]
    h = [x["h"] for x in candles]
    l = [x["l"] for x in candles]

    ema9  = ema(c, 9)
    ema21 = ema(c, 21)
    rsi14 = rsi(c, 14)
    K, D  = stoch_rsi(c, 14, 3, 3)
    mac, sig, hist = macd(c, 5, 13, 9)
    atr14 = atr(h, l, c, 14)
    bbl, bbm, bbu = bbands(c, 20, 2)

    i = len(c)-1  # latest index
    last = c[i]

    # ---- Scoring (simplified weights from PRD; total 100) ----
    score = 0; notes=[]

    # Trend (25)
    trend_pts=0
    if last > (bbm[i] or last) and ema9[i] > ema21[i]:
        if last > ema9[i] > ema21[i]:
            trend_pts = 25; notes.append("Trend: perfect bull")
        else:
            trend_pts = 15; notes.append("Trend: moderate bull")
    elif last < (bbm[i] or last) and ema9[i] < ema21[i]:
        trend_pts = -25; notes.append("Trend: perfect bear")
    else:
        trend_pts = 10; notes.append("Trend: neutral/VWAP proxy")
    score += max(0, trend_pts)

    # Momentum (20)
    mom = 0
    if mac[i] > sig[i] and hist[i] > 0: mom += 8
    if rsi14[i] is not None:
        if rsi14[i] < 30 or (30 <= rsi14[i] <= 50 and rsi14[i] > rsi14[i-1]): mom += 6
    if K[i] is not None and D[i] is not None and K[i-1] is not None and D[i-1] is not None:
        if K[i-1] < D[i-1] and K[i] > D[i] and (K[i] < 20): mom += 6
    score += mom
    notes.append(f"Momentum:+{mom}")

    # Volume proxy (20) – no true volume for FX; use range/ATR as activity proxy
    vol = 0
    rng = (h[i]-l[i])
    if atr14[i] and rng > 1.5*atr14[i]: vol += 8
    # OBV/MFI not available -> simple proxy: 2nd condition on hist growth
    if hist[i] > hist[i-1] > 0: vol += 6
    if bbu[i] and last > bbu[i] or (bbl[i] and last < bbl[i]):  # expansion
        vol += 6
    score += vol; notes.append(f"VolProxy:+{vol}")

    # Structure (15) – BB mid as S/R proxy
    stru = 0
    if bbm[i] and abs(last-bbm[i]) < (atr14[i] or 1e-6)*0.3: stru += 8
    # round-number magnet
    if abs((last*100)%50) < 2: stru += 7
    score += stru; notes.append(f"Structure:+{stru}")

    # Trend strength (10) – MACD hist magnitude proxy
    ts = 5 if abs(hist[i]) > abs(hist[i-3]) else 0
    ts += 5 if abs(ema9[i]-ema21[i]) > abs(ema9[i-3]-ema21[i-3]) else 0
    score += ts; notes.append(f"Strength:+{ts}")

    # Volatility context (10)
    volctx = 0
    if atr14[i] > atr14[i-5]: volctx += 5
    if bbu[i] and bbl[i] and (bbu[i]-bbl[i])/(bbm[i] or last) < 0.01:  # squeeze small
        volctx += 5
    score += volctx; notes.append(f"VolCtx:+{volctx}")

    # Classification
    if score >= 75: cls, risk = "STRONG", 1.5
    elif score >= 60: cls, risk = "MODERATE", 1.0
    elif score >= 45: cls, risk = "WEAK", 0.5
    else: cls, risk = "HOLD", 0.0

    # ATR-based SL/TP
    atrp = atr14[i] or (rng if rng>0 else 0.001)
    sl = atrp*2.0   # default majors
    tp1 = atrp*1.5; tp2 = atrp*2.5

    direction = "BUY" if trend_pts>=0 and mom>=6 else ("SELL" if trend_pts<0 and mom>=6 else "HOLD")

    text = (
        f"📊 {symbol} {direction} | score {score}/100 ({cls})\n"
        f"• price: {last:.5f}\n"
        f"• ATR14: {atrp:.5f}\n"
        f"• SL≈ {sl:.5f} | TP1≈ {tp1:.5f} | TP2≈ {tp2:.5f}\n"
        f"• notes: " + "; ".join(notes)
    )

    return {
        "ok": True, "symbol": symbol, "tf": tf, "price": last,
        "score": score, "class": cls, "direction": direction,
        "risk_pct": risk, "sl": sl, "tp1": tp1, "tp2": tp2, "text": text
    }
