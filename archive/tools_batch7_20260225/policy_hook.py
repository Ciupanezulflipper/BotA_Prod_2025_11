import os, csv, math, statistics
from pathlib import Path
from datetime import datetime, timezone
from news_sentiment import fetch_and_score

DATA_DIR = Path.home() / "bot-a" / "data" / "candles"

def _read_tail(csv_path, n=200):
    rows=[]
    if not csv_path.exists(): return rows
    with open(csv_path) as f:
        r=csv.reader(f)
        header=next(r,None)
        for row in r: rows.append(row)
    return rows[-n:]

def _ema(vals, p):
    k = 2/(p+1)
    ema=None
    out=[]
    for v in vals:
        if ema is None: ema=v
        else: ema = v*k + ema*(1-k)
        out.append(ema)
    return out

def _macd_close(closes, f=12, s=26, sig=9):
    ema_f=_ema(closes,f)
    ema_s=_ema(closes,s)
    macd=[a-b for a,b in zip(ema_f,ema_s)]
    signal=_ema(macd,sig)
    diff=[a-b for a,b in zip(macd,signal)]
    return macd, signal, diff

def _rsi(closes, p=14):
    gains=[0]; losses=[0]
    for i in range(1,len(closes)):
        d=closes[i]-closes[i-1]
        gains.append(max(0,d)); losses.append(max(0,-d))
    avg_gain=sum(gains[:p])/p if len(gains)>=p else 0
    avg_loss=sum(losses[:p])/p if len(losses)>=p else 0
    rs = (avg_gain / avg_loss) if avg_loss>0 else 1e9
    rsi=[100-(100/(1+rs))]
    for i in range(p,len(closes)):
        avg_gain = (avg_gain*(p-1)+gains[i])/p
        avg_loss = (avg_loss*(p-1)+losses[i])/p
        rs = (avg_gain / avg_loss) if avg_loss>0 else 1e9
        rsi.append(100-(100/(1+rs)))
    # pad front
    while len(rsi)<len(closes): rsi=[rsi[0]]+rsi
    return rsi

def _adx(closes, highs, lows, p=14):
    # simple ADX proxy (not full DI calc to keep it light)
    # use ATR-ish range / price for trend strength
    trs=[h-l for h,l in zip(highs,lows)]
    atr=_ema(trs,p)
    pct=[(a/max(1e-6,c))*10000 for a,c in zip(atr,closes)]
    # scale into classic-ish 0..50 band
    return [min(50, max(0, x/6)) for x in pct]

def compute_signal(pair, tf):
    # === load M15 ===
    base = DATA_DIR / f"{pair}_{tf}.csv"
    r = _read_tail(base, 300)
    if len(r) < 50: 
        return {"send":False, "score":0, "tags":["NO_DATA"]}

    def _cols(rows):
        o,h,l,c = [],[],[],[]
        for row in rows:
            o.append(float(row[1])); h.append(float(row[2])); l.append(float(row[3])); c.append(float(row[4]))
        return o,h,l,c

    o,h,l,c = _cols(r)
    macd, sig, diff = _macd_close(c)
    rsi = _rsi(c)
    adx = _adx(c,h,l)

    last = -1
    last_macd_diff = diff[last]
    last_rsi = rsi[last]
    last_adx = adx[last]

    # === MACD momentum weighting ===
    dmin = float(os.getenv("MACD_DIFF_MIN","0.0002"))
    dfull= float(os.getenv("MACD_DIFF_FULL","0.0008"))
    if last_macd_diff <= dmin: macd_pts = 0.0
    elif last_macd_diff >= dfull: macd_pts = 1.2
    else:
        macd_pts = 1.2 * ( (last_macd_diff - dmin) / (dfull - dmin) )

    # === RSI / ADX gates ===
    adx_pts = 0.0
    if last_adx >= 18: adx_pts += 0.6
    if last_adx >= 22: adx_pts += 0.3
    rsi_pts = 0.0
    if last_rsi >= 60: rsi_pts += 0.3
    if last_rsi >= 70: rsi_pts += 0.2

    # === HTF bias (H1 + H4 agree) ===
    bias_pts = 0.0
    htfw = float(os.getenv("HTF_BIAS_WEIGHT","0.6"))
    def _htf_ok(tffile):
        rr=_read_tail(DATA_DIR/f"{pair}_{tffile}.csv", 200)
        if len(rr)<50: return 0
        _o,_h,_l,_c = _cols(rr)
        _m,_s,_d = _macd_close(_c)
        _r = _rsi(_c)
        return 1 if (_d[-1] > 0 and _r[-1] >= 55) else 0
    ok_h1 = _htf_ok("H1")
    ok_h4 = _htf_ok("H4")
    if ok_h1 + ok_h4 >= 2: bias_pts += htfw
    elif ok_h1 + ok_h4 == 1: bias_pts += htfw*0.4

    # === M5 Blend (optional) ===
    m5_pts = 0.0
    if os.getenv("M5_BLEND","1") == "1":
        rr=_read_tail(DATA_DIR/f"{pair}_M5.csv", 200)
        if len(rr)>=50:
            _o,_h,_l,_c = _cols(rr)
            _m,_s,_d = _macd_close(_c)
            # simple M5 boost if MACD rising + last close above 20-EMA
            ema20 = _ema(_c, 20)
            if _d[-1] > 0 and _c[-1] > ema20[-1]:
                m5_pts = float(os.getenv("M5_WEIGHT","0.8"))

    # === News sentiment ===
    news_pts = 0.0
    news_meta = {}
    if os.getenv("NEWS_ON","1") == "1":
        sent, meta = fetch_and_score(pair)
        news_meta = meta
        # map [-1..+1] to [-NEWS_WEIGHT..+NEWS_WEIGHT]
        w = float(os.getenv("NEWS_WEIGHT","1.0"))
        news_pts = max(-w, min(w, sent * w))

    # Final score
    score = macd_pts + adx_pts + rsi_pts + bias_pts + m5_pts + news_pts

    tags=[]
    if last_macd_diff>0: tags.append("MACD↑")
    if last_rsi>=60: tags.append(f"RSI{int(round(last_rsi))}")
    if last_adx>=18: tags.append("ADX")
    if ok_h1 or ok_h4: tags.append("HTF✓" if (ok_h1 and ok_h4) else "HTF~")
    if m5_pts>0: tags.append("M5+")
    if news_pts>0: tags.append("NEWS+")
    if news_pts<0: tags.append("NEWS-")

    return {
        "send": score >= float(os.getenv("CONF_MIN","3.0")),
        "score": round(score,2),
        "components": {
            "macd": round(macd_pts,2),
            "adx": round(adx_pts,2),
            "rsi": round(rsi_pts,2),
            "htf": round(bias_pts,2),
            "m5": round(m5_pts,2),
            "news": round(news_pts,2),
        },
        "telemetry": {
            "last_macd_diff": last_macd_diff,
            "last_rsi": last_rsi,
            "last_adx": last_adx
        },
        "news_meta": news_meta,
        "tags": tags
    }
