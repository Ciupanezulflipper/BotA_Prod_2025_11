# PRD v5.0 demo scorer (append-only). Uses indicators to produce 0..100 score.
from data.indicators import ema, rsi, stoch_rsi, macd, atr, bbands

WEIGHTS = {
    "trend": 25, "momentum": 20, "volume": 20,  # volume placeholder (0)
    "structure": 15, "strength": 10, "volatility": 10
}

def clamp(v,a,b): return max(a, min(b, v))

def score_series(ohlcv):
    # ohlcv: dict with lists 't','o','h','l','c','v'
    c=ohlcv["c"]; h=ohlcv["h"]; l=ohlcv["l"]
    e9=ema(c,9); e21=ema(c,21)
    k,d = stoch_rsi(c); r = rsi(c); m,ms,hh = macd(c)
    a14=atr(h,l,c,14); mid,up,dn = bbands(c)
    out=[]
    for i in range(len(c)):
        # Trend
        trend=0
        if c[i] and e9[i] and e21[i]:
            if c[i]>e9[i]>e21[i]: trend=+WEIGHTS["trend"]
            elif c[i]>e9[i] or c[i]>e21[i]: trend=+15
            elif c[i]<e9[i]<e21[i]: trend=-WEIGHTS["trend"]
            else: trend=-10
        # Momentum
        mom=0
        if m[i] is not None and ms[i] is not None:
            mom += 8 if m[i]>ms[i] and (hh[i] or 0)>0 else -8
        if r[i] is not None:
            mom += 6 if r[i]<30 or (30<=r[i]<=50 and (r[i]-(r[i-1] if i else r[i]))>0) else 0
            mom -= 6 if r[i]>70 else 0
        if k[i] is not None and d[i] is not None:
            if k[i]<20 and k[i]>d[i]: mom+=6
            if k[i]>80 and k[i]<d[i]: mom-=6
        mom = clamp(mom, -WEIGHTS["momentum"], WEIGHTS["momentum"])
        # Strength (ADX placeholder -> infer from MACD hist magnitude)
        strength = 0
        if hh[i] is not None:
            mag = abs(hh[i])
            strength = 5 if mag> (sum(abs(v or 0) for v in hh[max(0,i-9):i+1])/max(1,(i+1)-(max(0,i-9)))) else 0
        # Volatility context via BB/ATR
        vol = 0
        if a14[i] and mid[i] and up[i] and dn[i]:
            band_w = (up[i]-dn[i])/(mid[i] or 1)
            vol += 5 if band_w>0.01 else 0
            vol += 5 if a14[i] and a14[i]>(sum(v for v in a14[max(0,i-14):i+1] if v)/max(1,(i+1)-(max(0,i-14)))) else 0
        # Volume & Structure placeholders (0). Extend later with POC/VA, OBV/MFI.
        total = clamp(trend, -25,25) + mom + strength + vol
        total = clamp(total + 0 + 0, 0, 100)
        out.append(total)
    return out
