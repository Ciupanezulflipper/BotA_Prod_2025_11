#!/data/data/com.termux/files/usr/bin/python3
import os, re, time, sys, math, json
from urllib.parse import urlencode
import requests

# --- config via env ---
BOT_TOKEN   = os.getenv("TG_BOT_TOKEN","")
CHAT_ID     = os.getenv("TG_CHAT_ID","")
PAIRS       = os.getenv("SCOUT_PAIRS","EURUSD,GBPUSD").split(",")
ACTIVE_START= os.getenv("TRADE_UTC_START","06:00")
ACTIVE_END  = os.getenv("TRADE_UTC_END","20:00")
NEWS_PAUSE  = os.getenv("NEWS_PAUSE","0") == "1"
BLACKOUT_MIN= int(os.getenv("NEWS_BLACKOUT_MINUTES","30"))
# Early trigger rules
W_MIN       = int(os.getenv("SCOUT_WEIGHTED_MIN","4"))   # need strong HTF bias
RSI_LO      = float(os.getenv("SCOUT_RSI_LO","45"))
RSI_HI      = float(os.getenv("SCOUT_RSI_HI","55"))
# M15 micro trigger: require EMA9 vs EMA21 alignment + candle body >= 50% range or MACD flip
BODY_PCT    = float(os.getenv("SCOUT_BODY_PCT","0.50"))

RUNLOG      = os.path.expanduser("~/BotA/run.log")
COOLDOWN_MIN= int(os.getenv("SCOUT_COOLDOWN_MIN","20"))
STATE_PATH  = os.path.expanduser("~/BotA/logs/scout_state.json")

def in_window(now_utc):
    sH,sM = map(int, ACTIVE_START.split(":"))
    eH,eM = map(int, ACTIVE_END.split(":"))
    nowH,nowM = now_utc.tm_hour, now_utc.tm_min
    start = sH*60+sM; end = eH*60+eM; cur = nowH*60+nowM
    return start <= cur <= end

def load_state():
    try:
        with open(STATE_PATH,"r") as f: return json.load(f)
    except: return {}

def save_state(s):
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    with open(STATE_PATH,"w") as f: json.dump(s,f)

def send_watch(pair, side, reason, weighted):
    if not (BOT_TOKEN and CHAT_ID): return
    text = f"🟡 *WATCH* {pair} {side}\nReason: {reason}\nWeighted={weighted}\n(Scout layer: consider early entry on M15; wait H1 confirm for full size.)"
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {"chat_id":CHAT_ID,"text":text,"parse_mode":"Markdown"}
    try:
        requests.post(url, data=data, timeout=10)
    except Exception as e:
        pass

def parse_block(lines, pair):
    # Find the latest block for this PAIR like "=== EURUSD snapshot ===" with H1/H4/D1 and (optionally) M15 lines
    # We’ll scan backwards and collect lines up to next blank.
    idx = len(lines)-1
    while idx>=0:
        if lines[idx].strip().startswith(f"=== {pair} snapshot ==="):
            start = idx
            # collect until next "[RUN" or "===" for other pair
            end = min(len(lines), start+20)
            return lines[start:end]
        idx -= 1
    return []

def grab_vote(s):
    m = re.search(r"vote=([+\-]?\d)", s)
    return int(m.group(1)) if m else 0

def grab_timeframe(line):
    # H1/H4/D1/M15 detection
    m = re.match(r"(H1|H4|D1|M15):\s", line.strip())
    return m.group(1) if m else ""

def body_ok(line):
    # crude body>=50% proxy: we use RSI/MACD + implicit "strong" from text
    # For better: parse open/high/low/close, but your snapshot prints close only.
    # We'll use MACD sign + RSI distance as proxy.
    rsi = re.search(r"RSI14=([0-9.]+)", line)
    macd = re.search(r"MACD_hist=([\-0-9.]+)", line)
    if not (rsi and macd): return False
    rsi_v = float(rsi.group(1)); macd_v = float(macd.group(1))
    # If trend down: rsi well below 45 or macd negative suggests impulse
    # If trend up: rsi well above 55 or macd positive suggests impulse
    return (rsi_v <= (RSI_LO-3) or rsi_v >= (RSI_HI+3) or abs(macd_v) > 0)

def ema_slope_ok(line, want_side):
    e9 = re.search(r"EMA9=([0-9.]+)", line)
    e21= re.search(r"EMA21=([0-9.]+)", line)
    c  = re.search(r"close=([0-9.]+)", line)
    if not (e9 and e21 and c): return False
    ema9=float(e9.group(1)); ema21=float(e21.group(1))
    if want_side=="SELL": return ema9 < ema21
    if want_side=="BUY":  return ema9 > ema21
    return False

def main():
    now = time.gmtime()
    if not in_window(now): return
    if NEWS_PAUSE: return

    try:
        with open(RUNLOG,"r") as f:
            lines = f.readlines()[-500:]
    except:
        return

    st = load_state()
    for pair in PAIRS:
        block = parse_block(lines, pair.strip())
        if not block: continue

        # collect votes
        v = {"H1":0,"H4":0,"D1":0}
        m15_line=None
        for L in block:
            tf = grab_timeframe(L)
            if tf in v: v[tf]=grab_vote(L)
            if tf=="M15": m15_line=L

        weighted = v["H1"]*1 + v["H4"]*2 + v["D1"]*3
        if abs(weighted) < W_MIN: 
            continue

        side = "BUY" if weighted>0 else "SELL"

        # need an M15 proxy: if absent, reuse H1 for micro-check
        micro_line = m15_line
        if not micro_line:
            for L in block:
                if grab_timeframe(L)=="H1": micro_line=L; break
        if not micro_line: continue

        # micro trigger: EMA alignment + body proxy
        if not ema_slope_ok(micro_line, side): 
            continue
        if not body_ok(micro_line):
            continue

        # cooldown per side/pair
        key = f"{pair}:{side}"
        last = st.get(key, 0)
        if now[0]*525600 + now[7]*1440 + now[3]*60 + now[4] - last < COOLDOWN_MIN:
            continue

        reason = []
        reason.append(f"HTF weighted={weighted} ({v})")
        reason.append("M15/H1 micro impulse + EMA alignment")
        send_watch(pair, side, "; ".join(reason), weighted)

        st[key] = now[0]*525600 + now[7]*1440 + now[3]*60 + now[4]  # minutes since epoch-ish
    save_state(st)

if __name__=="__main__":
    main()
