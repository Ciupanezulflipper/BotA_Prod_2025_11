# Minimal EMA + RSI with safety rails
def ema(values, period):
    if len(values) < period: return None
    k = 2/(period+1)
    e = values[0]
    for v in values[1:]:
        e = v*k + e*(1-k)
    return e

def rsi(values, period=14):
    if len(values) <= period: return None
    gains=0.0; losses=0.0
    for i in range(1, period+1):
        ch = values[i]-values[i-1]
        if ch>=0: gains+=ch
        else: losses-=ch
    avg_gain=gains/period; avg_loss=losses/period if losses>0 else 0.0
    if avg_loss==0: return 100.0
    rs=avg_gain/avg_loss
    rsi_val=100-(100/(1+rs))
    for i in range(period+1, len(values)):
        ch = values[i]-values[i-1]
        gain = max(ch,0.0); loss = max(-ch,0.0)
        avg_gain = (avg_gain*(period-1)+gain)/period
        avg_loss = (avg_loss*(period-1)+loss)/period
        rs = avg_gain/avg_loss if avg_loss>0 else 999.0
        rsi_val = 100-(100/(1+rs))
    return rsi_val

def decide_signal(closes):
    """
    Input: list of close floats (oldest->newest)
    Output: dict(action, entry, sl, tp, conf, reason)
    """
    if len(closes) < 30:
        return {"action":"HOLD","entry":closes[-1],
                "sl":0,"tp":0,"conf":0.0,"reason":"NOT_ENOUGH_BARS"}

    shortE = ema(closes[-30:], 9)
    longE  = ema(closes[-30:], 21)
    r      = rsi(closes[-30:], 14)
    price  = closes[-1]

    if shortE is None or longE is None or r is None:
        return {"action":"HOLD","entry":price,"sl":0,"tp":0,"conf":0.0,"reason":"INDICATOR_NA"}

    # Simple rules
    if shortE>longE and r>52:
        action="BUY"; conf = min(0.95, 0.55 + (r-52)/100 + (shortE/longE-1)*10)
    elif shortE<longE and r<48:
        action="SELL"; conf = min(0.95, 0.55 + (48-r)/100 + (longE/shortE-1)*10)
    else:
        action="HOLD"; conf = 0.35

    # Generic SL/TP: 20/40 pips (for majors) — adjust later per pair ATR
    pip = 0.0001
    sl = round(price - 0.0020, 5) if action=="BUY" else round(price + 0.0020, 5)
    tp = round(price + 0.0040, 5) if action=="BUY" else round(price - 0.0040, 5)
    if action=="HOLD": sl=tp=0

    return {"action":action,"entry":price,"sl":sl,"tp":tp,"conf":round(conf,2),
            "reason":f"EMA9/21 & RSI14 (r={round(r,1)})"}
