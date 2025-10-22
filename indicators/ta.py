#!/usr/bin/env python3
import math

def ema(series, period):
    k = 2/(period+1)
    ema_vals=[]
    s=None
    for i,x in enumerate(series):
        if s is None: s=x
        else: s = x*k + s*(1-k)
        ema_vals.append(s)
    return ema_vals

def rsi(close, period=14):
    gains=[0]; losses=[0]
    for i in range(1,len(close)):
        ch=close[i]-close[i-1]
        gains.append(max(ch,0)); losses.append(max(-ch,0))
    ema_g = ema(gains, period)
    ema_l = ema(losses, period)
    out=[]
    for g,l in zip(ema_g, ema_l):
        if l==0: out.append(100.0)
        else: out.append(100.0 - 100.0/(1.0+g/l))
    return out

def macd(close, fast=5, slow=13, signal=9):
    ema_f = ema(close, fast)
    ema_s = ema(close, slow)
    macd_line=[f-s for f,s in zip(ema_f, ema_s)]
    sig = ema(macd_line, signal)
    hist=[m-s for m,s in zip(macd_line, sig)]
    return macd_line, sig, hist

def atr(high, low, close, period=14):
    trs=[0.0]
    for i in range(1,len(close)):
        tr = max(high[i]-low[i], abs(high[i]-close[i-1]), abs(low[i]-close[i-1]))
        trs.append(tr)
    return ema(trs, period)

def stoch_rsi(close, period=14, k=3, d=3):
    rs = rsi(close, period)
    out=[]
    for i in range(len(rs)):
        start=max(0, i-period+1)
        window=rs[start:i+1]
        mn=min(window); mx=max(window)
        val=0.0 if mx==mn else (rs[i]-mn)/(mx-mn)*100.0
        out.append(val)
    k_line=ema(out, k)
    d_line=ema(k_line, d)
    return k_line, d_line
