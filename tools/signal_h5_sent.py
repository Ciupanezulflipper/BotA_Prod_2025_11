#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
signal_h5_sent.py
Single-file runner that:
- Pulls multi-timeframe OHLC (5m, 1h, 5h, 1d) with simple provider rotation
- Scores tech (EMA 9/21, RSI, MACD, ADX) => 0..4 per TF => 0..16 total
- Reads news cache from ~/bot-a/data/news_cache.json and adds Sentiment 0..6
- Prints a Telegram-style card (and can send if env BOT_TOKEN/CHAT_ID set)
- Sends only if decision flips OR tech >= 80% OR tech == 16/16 (with cooldown)

Minimal deps: pandas, numpy, requests
"""

import os, sys, time, json, math, warnings
from datetime import datetime, timezone, timedelta

import numpy as np
import pandas as pd
import requests

warnings.filterwarnings("ignore", category=FutureWarning)

# ---------------- Config ----------------
SYMBOL_DISPLAY = "EUR/USD"          # for card
SYMBOL_AV = ("EUR","USD")           # AlphaVantage split
SYMBOL_TD = "EURUSD"                # TwelveData compact
TIMEFRAMES = ["5m", "1h", "5h", "1d"]
OUTPUTSIZE = {"5m":120, "1h":200, "5h":400, "1d":200}

# gates
MAX_TECH = 16
GATE_80 = math.ceil(MAX_TECH * 0.8)     # 80%
COOLDOWN_SEC = 20 * 60                  # 20 minutes

# sentiment cache
NEWS_PATH = os.path.expanduser("~/bot-a/data/news_cache.json")
NEWS_STALE_MIN = 120                    # consider news stale after 2h

# env
TD_KEY   = os.getenv("TWELVE_API_KEY", os.getenv("TWELVEDATA_KEY", ""))
AV_KEY   = os.getenv("ALPHA_API_KEY", os.getenv("ALPHA_VANTAGE_KEY", ""))
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
CHAT_ID   = os.getenv("CHAT_ID", "")

# state
STATE_PATH = os.path.expanduser("~/bot-a/state/signal_h5_state.json")
os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
os.makedirs(os.path.expanduser("~/bot-a/data"), exist_ok=True)

# ------------- Helpers ------------------
def utcnow():
    return datetime.now(timezone.utc)

def clamp(v,a,b):
    return max(a, min(b, v))

def load_state():
    if not os.path.exists(STATE_PATH):
        return {"last_decision":"HOLD", "last_alert_ts":0.0}
    try:
        with open(STATE_PATH,"r") as f:
            return json.load(f)
    except:
        return {"last_decision":"HOLD", "last_alert_ts":0.0}

def save_state(st):
    try:
        with open(STATE_PATH,"w") as f:
            json.dump(st, f)
    except:
        pass

# ----------- Providers (simple) ----------
def td_interval(tf: str) -> str:
    return {"5m":"5min","1h":"1h","1d":"1day"}.get(tf, "")

def fetch_twelvedata(symbol: str, tf: str, size: int) -> pd.DataFrame | None:
    if not TD_KEY: return None
    td_tf = td_interval(tf)
    if not td_tf: return None
    url = "https://api.twelvedata.com/time_series"
    params = {"symbol":symbol,"interval":td_tf,"outputsize":size,"apikey":TD_KEY}
    r = requests.get(url, params=params, timeout=12)
    j = r.json()
    if "values" not in j: return None
    df = pd.DataFrame(j["values"])
    df["datetime"] = pd.to_datetime(df["datetime"], utc=True)
    df = df.sort_values("datetime")
    for c in ["open","high","low","close","volume"]:
        if c in df: df[c] = df[c].astype(float)
        else: df[c] = 0.0
    return df[["datetime","open","high","low","close","volume"]].reset_index(drop=True)

def fetch_av_daily(from_sym: str, to_sym: str, size: int) -> pd.DataFrame | None:
    if not AV_KEY: return None
    url = "https://www.alphavantage.co/query"
    params = {"function":"FX_DAILY","from_symbol":from_sym,"to_symbol":to_sym,"apikey":AV_KEY}
    r = requests.get(url, params=params, timeout=12)
    j = r.json()
    key = next((k for k in j.keys() if "Time Series" in k), None)
    if not key: return None
    ts = j[key]
    rows = []
    for t,vals in ts.items():
        rows.append([pd.to_datetime(t, utc=True),
                     float(vals["1. open"]), float(vals["2. high"]),
                     float(vals["3. low"]),  float(vals["4. close"]), 0.0])
    df = pd.DataFrame(rows, columns=["datetime","open","high","low","close","volume"]).sort_values("datetime")
    return df.tail(size).reset_index(drop=True)

def get_df(tf: str) -> tuple[pd.DataFrame|None, str]:
    """
    Returns (df, provider). For 5h we aggregate 1h to 5H.
    """
    if tf in ("5m","1h"):
        df = fetch_twelvedata(SYMBOL_TD, tf, OUTPUTSIZE[tf])
        if df is not None and len(df) >= 50: return df, "twelvedata"
        return None, "fail"

    if tf == "1d":
        # try TD daily first, fallback AV
        df = fetch_twelvedata(SYMBOL_TD, "1d", OUTPUTSIZE["1d"])
        if df is not None and len(df) >= 50: return df, "twelvedata"
        df = fetch_av_daily(SYMBOL_AV[0], SYMBOL_AV[1], OUTPUTSIZE["1d"])
        if df is not None and len(df) >= 50: return df, "alphavantage"
        return None, "fail"

    if tf == "5h":
        # get 1h then resample
        df1h, prov = get_df("1h")
        if df1h is None: return None, "fail"
        x = df1h.copy().set_index("datetime").resample("5H").agg(
            {"open":"first","high":"max","low":"min","close":"last","volume":"sum"}
        ).dropna().reset_index()
        if len(x) < 30: return None, "fail"
        return x, f"{prov}->resample"
    return None, "fail"

# ---------- Indicators & scoring ----------
def ema(s, n): return s.ewm(span=n, adjust=False).mean()

def rsi(close, period=14):
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100/(1+rs))

def macd(close, f=12, s=26, sig=9):
    m = ema(close, f) - ema(close, s)
    sg = ema(m, sig)
    return m, sg, m - sg

def true_range(h,l,c):
    return pd.concat([h-l,(h-c.shift()).abs(),(l-c.shift()).abs()], axis=1).max(axis=1)

def adx(h,l,c, period=14):
    tr = true_range(h,l,c)
    atr = tr.rolling(period).mean()
    up = h.diff()
    dn = (-l.diff())
    plus = np.where((up>dn)&(up>0), up, 0.0)
    minus = np.where((dn>up)&(dn>0), dn, 0.0)
    di_plus = 100 * pd.Series(plus, index=h.index).rolling(period).mean() / atr
    di_minus= 100 * pd.Series(minus,index=h.index).rolling(period).mean() / atr
    dx = 100 * (di_plus - di_minus).abs() / (di_plus + di_minus)
    return dx.rolling(period).mean()

def score_tf(df: pd.DataFrame) -> int:
    """0..4 by simple rules: EMA alignment, MACD align, RSI zone, ADX strength."""
    if df is None or len(df) < 50: return 0
    c = df["close"]
    h = df["high"]; l = df["low"]
    ema9  = ema(c,9)
    ema21 = ema(c,21)
    r = rsi(c,14)
    m, sg, _ = macd(c)
    a = adx(h,l,c,14)

    pts = 0
    if c.iloc[-1] > ema9.iloc[-1] > ema21.iloc[-1]: pts += 1
    if (m.iloc[-1] > sg.iloc[-1]) and (m.iloc[-1] > 0): pts += 1
    if 45 <= r.iloc[-1] <= 70: pts += 1           # neutral-to-bull zone
    if a.iloc[-1] >= 25: pts += 1
    return int(pts)

# ------------- Sentiment reader ----------
def read_sentiment(path=NEWS_PATH, pair_hint="EURUSD") -> tuple[int, str]:
    """
    Accepts any of:
      {"pair":"EURUSD","score_0_6":4,"why":"...","updated_utc":"..."}
      {"pair":"EUR/USD","sent_score":5,...}
      {"score":3,...}
    Staleness check: NEWS_STALE_MIN.
    """
    if not os.path.exists(path):
        return 0, "no_news_cache"
    try:
        with open(path,"r") as f:
            j = json.load(f)
    except Exception:
        return 0, "bad_json"

    score = j.get("score_0_6", j.get("sent_score", j.get("score", 0)))
    try:
        score = int(score)
    except:
        score = 0
    score = clamp(score, 0, 6)

    why = j.get("why", "n/a")

    # optional pair check (non-fatal)
    pair = j.get("pair","").replace("/","").upper()
    ok_pair = (not pair) or (pair == pair_hint.upper())

    # staleness
    up = j.get("updated_utc") or j.get("updated") or ""
    fresh = True
    if up:
        try:
            t = datetime.fromisoformat(up.replace("Z","+00:00"))
            age_min = (utcnow() - t).total_seconds()/60.0
            fresh = (age_min <= NEWS_STALE_MIN)
        except Exception:
            fresh = True

    if not ok_pair:
        return 0, "pair_mismatch"
    if not fresh:
        return 0, "news_stale"

    return score, why if why else "no_reason"

# -------------- Risk (ATR-based) ---------
def atr_distance(df_ref: pd.DataFrame, mult_sl=1.2, rr=1.5) -> tuple[float,float]:
    """Return (sl_dist, tp1_dist) in price units using 1h ATR."""
    if df_ref is None or len(df_ref) < 50:
        return 0.0000, 0.0000
    h,l,c = df_ref["high"], df_ref["low"], df_ref["close"]
    atr = true_range(h,l,c).rolling(14).mean().iloc[-1]
    sl = mult_sl * atr
    tp = rr * sl
    return float(sl), float(tp)

# -------------- Telegram -----------------
def send_telegram(text: str):
    if not BOT_TOKEN or not CHAT_ID: return
    try:
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                      data={"chat_id":CHAT_ID, "text":text, "parse_mode":"Markdown"},
                      timeout=8)
    except Exception:
        pass

# -------------- Main logic ---------------
def main(send=True):
    dfs = {}
    prov = {}
    points = {}

    # fetch all TFs
    for tf in TIMEFRAMES:
        df, provider = get_df(tf)
        dfs[tf] = df
        prov[tf] = provider
        points[tf] = score_tf(df)

    tech_total = sum(points.values())
    tech_pct = (tech_total / MAX_TECH) * 100.0

    # decision (simple majority on EMA/momentum proxy → use total as strength)
    decision = "HOLD"
    if tech_total >= GATE_80:
        # decide side by faster TF EMA stacking if possible
        d1 = points.get("1h",0)
        d5 = points.get("5h",0)
        dD = points.get("1d",0)
        bias = (d1>0) + (d5>0) + (dD>0)
        if bias >= 2: decision = "BUY"
        elif bias == 0: decision = "SELL"
        else: decision = "HOLD"

    # sentiment
    sent, sent_why = read_sentiment(NEWS_PATH, pair_hint="EURUSD")

    # entry/tp/sl from 1h reference
    ref = dfs.get("1h")
    entry = float(ref["close"].iloc[-1]) if ref is not None and len(ref)>0 else 0.0
    sl_d, tp_d = atr_distance(ref, mult_sl=1.2, rr=1.5)
    if decision == "BUY":
        tp1 = entry + tp_d
        sl  = entry - sl_d
    elif decision == "SELL":
        tp1 = entry - tp_d
        sl  = entry + sl_d
    else:
        tp1 = sl = 0.0

    # Compose card
    tf_line = " | ".join(f"{tf}={points[tf]}" for tf in TIMEFRAMES)
    msg = (
        f"*{SYMBOL_DISPLAY}*  UTC {utcnow().strftime('%H:%M')}\n\n"
        f"Decision: *{decision}*\n"
        f"Votes (per TF): {tf_line}\n"
        f"Tech: *{tech_total}/{MAX_TECH}* ({tech_pct:.0f}%)\n"
        f"Sent: *{sent}/6*\n"
        f"Entry≈ {entry:.5f}   TP1: {tp1:.5f}   SL: {sl:.5f}\n"
        f"Prov: " + ", ".join([f"{k}:{prov[k]}" for k in TIMEFRAMES]) + "\n"
        f"_Why (sent)_: {sent_why}"
    )

    # Alert policy
    st = load_state()
    now = time.time()
    flip = decision in ("BUY","SELL") and decision != st.get("last_decision")
    maxed = tech_total == MAX_TECH
    high  = tech_total >= GATE_80
    cool  = (now - float(st.get("last_alert_ts", 0))) > COOLDOWN_SEC

    should = False
    if flip or maxed or high:
        if flip or cool:
            should = True

    print(msg)  # always print

    if send and should:
        send_telegram(msg)
        st["last_alert_ts"] = now
        st["last_decision"] = decision
        save_state(st)

# -------- Entry ----------
if __name__ == "__main__":
    send = True
    if len(sys.argv) > 1 and sys.argv[1] == "--no-send":
        send = False
    main(send=send)
