# Extra indicators (pure-Python, list-in/list-out)
# Works with arrays or candle dicts {h,l,c,v}

from typing import List, Tuple, Sequence, Optional

def _arr(x, key=None):
    if not x: return []
    if isinstance(x[0], dict) and key:
        return [float(it.get(key, 0.0)) for it in x]
    return [float(v) for v in x]

def _typ_price(candles):
    h = _arr(candles, "h"); l = _arr(candles, "l"); c = _arr(candles, "c")
    return [(hh+ll+cc)/3.0 for hh,ll,cc in zip(h,l,c)]

def _sma(arr: Sequence[float], n: int):
    n = max(1,int(n)); out=[]; s=0.0
    for i,v in enumerate(arr):
        s += v
        if i>=n: s -= arr[i-n]
        out.append(s/n if i>=n-1 else None)
    return out

def _ema(arr: Sequence[float], n: int):
    n=max(1,int(n)); out=[]; k=2.0/(n+1.0); ema=None
    for v in arr:
        ema = (v if ema is None else (v-ema)*k + ema)
        out.append(ema)
    return out

# ---------------- Trend / Strength ----------------

def vwap(candles, period: Optional[int]=None) -> List[Optional[float]]:
    """Rolling VWAP on candles; if period=None → cumulative session-style."""
    tp = _typ_price(candles)
    v  = _arr(candles, "v")
    out=[]; pv_sum=0.0; v_sum=0.0
    q = int(period) if period else 0
    for i,(p,vol) in enumerate(zip(tp,v)):
        if q:
            # maintain rolling window sums
            pv_sum += p*vol; v_sum += vol
            if i>=q:
                pv_sum -= tp[i-q]*v[i-q]
                v_sum  -= v[i-q]
        else:
            pv_sum += p*vol; v_sum += vol
        out.append(pv_sum/v_sum if v_sum>0 else None)
    return out

def adx(high, low, close, period: int=14) -> Tuple[List[Optional[float]], List[Optional[float]], List[Optional[float]]]:
    """Returns (ADX, +DI, -DI). Inputs can be arrays or candles."""
    if isinstance(high, list) and high and isinstance(high[0], dict):
        c = high; high=_arr(c,"h"); low=_arr(c,"l"); close=_arr(c,"c")
    n=max(1,int(period))
    tr=[]; plus_dm=[]; minus_dm=[]
    for i in range(len(close)):
        if i==0:
            tr.append(None); plus_dm.append(0.0); minus_dm.append(0.0)
            continue
        up = high[i]-high[i-1]; dn = low[i-1]-low[i]
        pDM = up if (up>dn and up>0) else 0.0
        mDM = dn if (dn>up and dn>0) else 0.0
        plus_dm.append(pDM); minus_dm.append(mDM)
        tr_i = max(high[i]-low[i], abs(high[i]-close[i-1]), abs(low[i]-close[i-1]))
        tr.append(tr_i)
    # Wilder's smoothing
    def wilder(src):
        out=[]; sm=None
        for i,v in enumerate(src):
            if i<n:
                sm = (v if sm is None else sm+v)
                out.append(None)
            else:
                if i==n: sm = sum(src[1:n+1])
                sm = sm - (sm/n) + v
                out.append(sm)
        return out
    tr_w = wilder(tr)
    p_w  = wilder(plus_dm)
    m_w  = wilder(minus_dm)
    plus_di=[]; minus_di=[]; dx=[]; adx=[]
    for i in range(len(close)):
        if tr_w[i] is None or tr_w[i]==0:
            plus_di.append(None); minus_di.append(None); dx.append(None); adx.append(None); continue
        pdi = 100.0*(p_w[i]/tr_w[i])
        mdi = 100.0*(m_w[i]/tr_w[i])
        plus_di.append(pdi); minus_di.append(mdi)
        den = (pdi+mdi)
        dx.append(100.0*abs(pdi-mdi)/den if den>0 else 0.0)
    # ADX = EMA of DX with Wilder smoothing
    n=max(1,n)
    ema=None
    for d in dx:
        if d is None: adx.append(None); continue
        ema = d if ema is None else (ema*(n-1)+d)/n
        adx.append(ema)
    return adx, plus_di, minus_di

def psar(high, low, step:float=0.02, max_step:float=0.2):
    """Parabolic SAR; returns list of SAR values and trend dir (+1/-1)."""
    if isinstance(high, list) and high and isinstance(high[0], dict):
        c = high; high=_arr(c,"h"); low=_arr(c,"l")
    out=[]; dirn=1  # start uptrend
    af=step; ep=high[0]; sar=low[0]
    dirs=[]
    for i in range(len(high)):
        if i<2:
            out.append(None); dirs.append(None); continue
        sar = sar + af*(ep - sar)
        # For uptrend, SAR cannot exceed prior two lows; for downtrend, prior two highs
        if dirn==1:
            sar = min(sar, low[i-1], low[i-2])
            if high[i]>ep: ep = high[i]; af = min(af+step, max_step)
            if low[i] < sar:
                dirn=-1; sar=ep; ep=low[i]; af=step
        else:
            sar = max(sar, high[i-1], high[i-2])
            if low[i]<ep: ep = low[i]; af = min(af+step, max_step)
            if high[i] > sar:
                dirn=1; sar=ep; ep=high[i]; af=step
        out.append(sar); dirs.append(dirn)
    return out, dirs

# ---------------- Momentum / Volume ----------------

def stoch_rsi(close, period:int=14, k:int=3, d:int=3):
    """Stochastic RSI: returns (%K, %D)."""
    c = _arr(close,"c") if isinstance(close,list) and close and isinstance(close[0],dict) else _arr(close)
    # RSI
    gains=[]; losses=[]
    for i in range(len(c)):
        if i==0: gains.append(0.0); losses.append(0.0); continue
        ch = c[i]-c[i-1]
        gains.append(max(ch,0.0)); losses.append(max(-ch,0.0))
    n=max(1,int(period))
    def rma(arr):
        out=[]; avg=None
        for v in arr:
            if avg is None: avg=v
            else: avg = (avg*(n-1)+v)/n
            out.append(avg)
        return out
    rs=[]
    ag=rma(gains); al=rma(losses)
    for i in range(len(c)):
        if al[i]==0: rs.append(100.0)
        else: rs.append(100.0 - (100.0/(1.0 + ag[i]/al[i])))
    # Stoch of RSI
    k_raw=[]; k_period=max(1,int(period))
    for i in range(len(rs)):
        lo = min(rs[max(0,i-k_period+1):i+1])
        hi = max(rs[max(0,i-k_period+1):i+1])
        k_raw.append( 0.0 if hi==lo else ( (rs[i]-lo)/(hi-lo) )*100.0 )
    k_line=_sma(k_raw, max(1,int(k)))
    d_line=_sma([v if v is not None else 0.0 for v in k_line], max(1,int(d)))
    return k_line, d_line

def obv(close, volume):
    c = _arr(close,"c") if isinstance(close,list) and close and isinstance(close[0],dict) else _arr(close)
    v = _arr(volume,"v") if isinstance(volume,list) and volume and isinstance(volume[0],dict) else _arr(volume)
    out=[]; cur=0.0
    for i in range(len(c)):
        if i==0: out.append(0.0); continue
        if c[i]>c[i-1]: cur += v[i]
        elif c[i]<c[i-1]: cur -= v[i]
        out.append(cur)
    return out

def mfi(high, low, close, volume, period:int=14):
    if isinstance(high, list) and high and isinstance(high[0], dict):
        c = high; high=_arr(c,"h"); low=_arr(c,"l"); close=_arr(c,"c"); volume=_arr(c,"v")
    tp=[(h+l+c)/3.0 for h,l,c in zip(high,low,close)]
    pmf=[0.0]; nmf=[0.0]
    for i in range(1,len(tp)):
        mf = tp[i]*volume[i]
        if tp[i]>tp[i-1]: pmf.append(mf); nmf.append(0.0)
        else: pmf.append(0.0); nmf.append(mf)
    out=[]; n=max(1,int(period))
    for i in range(len(tp)):
        a=max(0,i-n+1); sp=sum(pmf[a:i+1]); sn=sum(nmf[a:i+1])
        if sn==0: out.append(100.0)
        else:
            mr = sp/sn
            out.append(100.0 - (100.0/(1.0+mr)))
    return out

def volume_spike(volume, lookback:int=50, threshold:float=1.5):
    v = _arr(volume,"v") if isinstance(volume,list) and volume and isinstance(volume[0],dict) else _arr(volume)
    if not v: return None, False
    lb=max(1,int(lookback))
    avg = sum(v[-lb:])/min(len(v),lb)
    ratio = (v[-1]/avg) if avg>0 else 0.0
    return ratio, (ratio>=threshold)
