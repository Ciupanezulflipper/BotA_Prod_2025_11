#!/usr/bin/env python3
"""
early_watch.py — HTF bias from cache (robust to missing/invalid cache).

Usage:
  python3 tools/early_watch.py [--ignore-session]

Bias rule:
  H1(sign)*1 + H4(sign)*2 + D1(sign)*3
  sign(TF) from EMA alignment + RSI(>55/<45) + MACD_hist(>0/<0)
"""
import os, json, sys, time
from pathlib import Path

ROOT = Path.home()/ "BotA"
CACHE = ROOT / "cache"

def within_session():
    if "--ignore-session" in sys.argv:
        return True
    start = os.getenv("TRADE_UTC_START","06:00")
    end   = os.getenv("TRADE_UTC_END","20:00")
    t = time.gmtime()
    now = f"{t.tm_hour:02d}:{t.tm_min:02d}"
    return (start <= now <= end)

def load_tf(base: str, tf: str):
    p = CACHE / f"{base}_{tf}.json"
    if not p.exists(): 
        return None
    try:
        d = json.loads(p.read_text())
        # validate required fields
        for k in ("ema9","ema21","rsi14","macd_hist"):
            if k not in d or d[k] is None:
                return None
        return d
    except Exception:
        return None

def tf_vote(d):
    if not d: 
        return 0
    try:
        ema_v = 1 if d["ema9"]>d["ema21"] else (-1 if d["ema9"]<d["ema21"] else 0)
        rsi_v = 1 if d["rsi14"]>55 else (-1 if d["rsi14"]<45 else 0)
        macd_v= 1 if d["macd_hist"]>0 else (-1 if d["macd_hist"]<0 else 0)
        s = ema_v + rsi_v + macd_v
        return 1 if s>0 else (-1 if s<0 else 0)
    except Exception:
        return 0

def weighted_bias(base: str):
    h1 = load_tf(base, "H1")
    h4 = load_tf(base, "H4")
    d1 = load_tf(base, "D1")
    v1, v4, vD = tf_vote(h1), tf_vote(h4), tf_vote(d1)
    w = v1*1 + v4*2 + vD*3
    return w, (v1, v4, vD)

def main():
    pairs = ["EURUSD","GBPUSD"]
    if not within_session():
        for p in pairs:
            print(f"[early_watch] {p} -> outside session; skip WATCH ping")
        return

    for p in pairs:
        base = p.replace("/","").upper()
        w, (v1, v4, vD) = weighted_bias(base)
        bias = "BUY" if w>=3 else ("SELL" if w<=-3 else "NEUTRAL")
        print(f"[early_watch] {p} weighted={w} bias={bias}")
        if bias in ("BUY","SELL"):
            print(f"[early_watch] {p}: HTF votes H1={v1} H4={v4} D1={vD}")
        else:
            print(f"[early_watch] {p}: bias too weak for WATCH")

if __name__ == "__main__":
    main()
