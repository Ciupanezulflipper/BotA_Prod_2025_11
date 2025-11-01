#!/usr/bin/env python3
# FILE: tools/ta_calc.py
# PURPOSE: Pure-Python TA engine: EMA9/EMA21, RSI14, MACD(12,26,9) → JSON verdict/score
# NOTE: No external deps. Safe for Termux.

import argparse, json
from urllib.request import Request, urlopen

def ema(series, period):
    k = 2.0/(period+1.0)
    out=[]; prev=None
    for v in series:
        prev = v if prev is None else (v-prev)*k + prev
        out.append(prev)
    return out

def rsi(series, period=14):
    gains=0.0; losses=0.0
    rsis=[50.0]*len(series)
    for i in range(1,len(series)):
        ch=series[i]-series[i-1]
        g = ch if ch>0 else 0.0
        l = -ch if ch<0 else 0.0
        if i<=period:
            gains += g; losses += l
            rs  = (gains/period) / ((losses/period) + 1e-12)
            rsis[i] = 100.0 - 100.0/(1.0+rs)
        else:
            gains = (gains*(period-1)+g)/period
            losses= (losses*(period-1)+l)/period
            rs    = gains/(losses+1e-12)
            rsis[i]= 100.0 - 100.0/(1.0+rs)
    return rsis

def macd(series, fast=12, slow=26, signal=9):
    f=ema(series, fast); s=ema(series, slow)
    line=[a-b for a,b in zip(f,s)]
    sig = ema(line, signal)
    hist=[a-b for a,b in zip(line,sig)]
    return line, sig, hist

def yahoo_fetch(pair, interval):
    sym=f"{pair}=X"
    url=f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval={interval}&range=3mo"
    req=Request(url, headers={"User-Agent":"Mozilla/5.0"})
    with urlopen(req, timeout=8) as r:
        data=json.loads(r.read().decode())
    res=(data.get("chart",{}).get("result") or [{}])[0]
    q=(res.get("indicators",{}).get("quote") or [{}])[0]
    def filt(a): return [x for x in (a or []) if isinstance(x,(int,float))]
    o=filt(q.get("open")); h=filt(q.get("high")); l=filt(q.get("low")); c=filt(q.get("close"))
    return o,h,l,c

def parse_cache(path):
    try:
        with open(path,"r") as f:
            raw=f.read().strip()
            if not raw: return None
            data=json.loads(raw)
    except Exception:
        return None

    o=h=l=c=None
    if isinstance(data,list) and data and isinstance(data[0],dict):
        o=[float(x["o"]) for x in data if "o" in x]
        h=[float(x["h"]) for x in data if "h" in x]
        l=[float(x["l"]) for x in data if "l" in x]
        c=[float(x["c"]) for x in data if "c" in x]
    elif isinstance(data,dict):
        if "candles" in data and isinstance(data["candles"],list):
            arr=data["candles"]
            o=[float(x["o"]) for x in arr if "o" in x]
            h=[float(x["h"]) for x in arr if "h" in x]
            l=[float(x["l"]) for x in arr if "l" in x]
            c=[float(x["c"]) for x in arr if "c" in x]
        else:
            o=[float(x) for x in (data.get("o") or []) if x is not None]
            h=[float(x) for x in (data.get("h") or []) if x is not None]
            l=[float(x) for x in (data.get("l") or []) if x is not None]
            c=[float(x) for x in (data.get("c") or []) if x is not None]
    if c and o and h and l and len(c)>=3:
        return o,h,l,c
    return None

def score_and_verdict(pair, tf, o,h,l,c, wtrend, wmom, wrsi, wfilt):
    ema9 = ema(c,9); ema21=ema(c,21)
    rsi14=rsi(c,14)
    mline, msign, mhist = macd(c,12,26,9)

    px=c[-1]; e9=ema9[-1]; e21=ema21[-1]; r=rsi14[-1]; ml=mline[-1]; mh=mhist[-1]

    trend_pts=0
    if e9>e21: trend_pts += int(wtrend*0.60)
    if px>e21: trend_pts += int(wtrend*0.25)
    if px>e9 : trend_pts += int(wtrend*0.15)

    mom_pts=0
    if ml>0:  mom_pts += int(wmom*0.50)
    if mh>0:  mom_pts += int(wmom*0.50)

    rsi_pts=0
    if 55 < r <= 70: rsi_pts += int(wrsi*0.75)
    elif r>70:       rsi_pts += int(wrsi*0.60)
    elif 45 <= r <=55: rsi_pts += int(wrsi*0.20)
    elif 30 < r <45: rsi_pts += int(wrsi*0.40)
    else:            rsi_pts += int(wrsi*0.50)

    filt_pts=0
    if abs(px-e21)/max(1e-9,px) < 0.02:               filt_pts += int(wfilt*0.4)
    if (h[-1]-l[-1])/max(1e-9,px) < 0.02:             filt_pts += int(wfilt*0.3)
    if (max(h[-5:]) - min(l[-5:]))/max(1e-9,px) < .05:filt_pts += int(wfilt*0.3)

    score = max(0, min(100, trend_pts+mom_pts+rsi_pts+filt_pts))

    bullish = (e9>e21) and (r>55) and (mh>0)
    bearish = (e9<e21) and (r<45) and (mh<0)

    if bullish and score>=60: verdict="BUY"
    elif bearish and score>=60: verdict="SELL"
    else: verdict="HOLD"

    conf=50
    if verdict!="HOLD":
        conf=55
        if abs(e9-e21)/max(1e-9,px) > .002: conf+=10
        if abs(mh) > .03:                   conf+=10
        if verdict=="BUY" and r>60:         conf+=10
        if verdict=="SELL" and r<40:        conf+=10
    conf=max(0,min(95,conf))

    reasons = [
        f"EMA9{'>' if e9>e21 else '<'}EMA21",
        f"RSI14={r:.1f}",
        f"MACD_hist={mh:.4f}",
        f"breakdown={trend_pts}/{mom_pts}/{rsi_pts}/{filt_pts}"
    ]
    return {
        "pair": pair, "timeframe": tf,
        "verdict": verdict, "score": int(score), "confidence": int(conf),
        "reasons": ";".join(reasons), "price": round(px,5)
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--pair", required=True)
    ap.add_argument("--timeframe", required=True)
    ap.add_argument("--cache", required=True)
    ap.add_argument("--min-bars", type=int, default=120)
    ap.add_argument("--map-h1", default="1h")
    ap.add_argument("--map-h4", default="1h")
    ap.add_argument("--map-d1", default="1d")
    ap.add_argument("--w-trend", type=int, default=40)
    ap.add_argument("--w-mom",   type=int, default=30)
    ap.add_argument("--w-rsi",   type=int, default=20)
    ap.add_argument("--w-filt",  type=int, default=10)
    args=ap.parse_args()

    tf=args.timeframe.upper()
    interval={"H1":args.map_h1, "H4":args.map_h4, "D1":args.map_d1}.get(tf,"1h")

    parsed=parse_cache(args.cache)
    if parsed is None:
        try:
            parsed=yahoo_fetch(args.pair, interval)
        except Exception:
            print(json.dumps({"verdict":"HOLD","score":50,"confidence":50,"reasons":"no_data","price":0}), end="")
            return

    o,h,l,c=parsed
    # Try to top-up series if too short
    if len(c) < args.min_bars:
        try:
            o2,h2,l2,c2 = yahoo_fetch(args.pair, interval)
            if len(c2) > len(c): o,h,l,c = o2,h2,l2,c2
        except Exception:
            pass

    if len(c) < max(26+9+5, args.min_bars//2):
        print(json.dumps({"verdict":"HOLD","score":50,"confidence":50,"reasons":"insufficient_bars","price":(c[-1] if c else 0)}), end="")
        return

    out=score_and_verdict(args.pair, tf, o,h,l,c, args.w_trend, args.w_mom, args.w_rsi, args.w_filt)
    print(json.dumps(out), end="")

if __name__=="__main__":
    main()
