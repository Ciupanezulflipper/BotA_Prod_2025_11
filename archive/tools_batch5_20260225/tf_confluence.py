#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Merge per-timeframe tech points + sentiment into one final decision and
emit ~/bot-a/data/confluence_signal.json for confluence_card.py to send.

Inputs (choose one):
  A) --in ~/bot-a/data/tf_snapshot.json
     {
       "symbol":"EURUSD",
       "entry":1.10000, "sl":1.10120, "tp1":1.09850, "tp2":1.09720,
       "tech_points":{"m5":1,"h1":3,"h5":2,"h4":4,"d1":3},  # 0..4 each
       "tf_bias":{"m5":"SELL","h1":"SELL","h5":"SELL","h4":"BUY","d1":"BUY"},
       "sent_score":4,  # 0..6
       "reasons":["EMA stack down M5/H1","RSI cooling","News risk-on fade"]
     }

  B) CLI quick test:
     python3 tools/tf_confluence.py --symbol EURUSD --entry 1.1853 --sl 1.1862 --tp1 1.1838 --tp2 1.1825 \
       --points m5=3,h1=3,h5=2,h4=1,d1=0 --bias m5=SELL,h1=SELL,h5=SELL,h4=BUY,d1=NEUTRAL --sent 4 \
       --why "Rejection @ 1.1860" --why "Volume spike" --why "OB easing"

Output:
  ~/bot-a/data/confluence_signal.json  (consumed by confluence_card.py)
"""

import os, json, argparse
from datetime import datetime

OUT_PATH = os.path.expanduser("~/bot-a/data/confluence_signal.json")

WEIGHTS = {"d1":3.0, "h4":2.5, "h5":1.8, "h1":1.6, "m15":1.2, "m5":1.0}
ORDER   = ["m5","m15","h1","h5","h4","d1"]  # display order

def parse_kv(s):
    out={}
    if not s: return out
    for kv in s.split(","):
        k,v = kv.split("=",1)
        out[k.strip().lower()] = v.strip()
    return out

def as_int_dict(d):
    return {k:int(v) for k,v in d.items()}

def score_bias(tf_bias, tf_points):
    """Weighted vote: BUY=+w*pts, SELL=-w*pts, NEUTRAL=0."""
    total = 0.0
    wsum  = 0.0
    for tf, b in tf_bias.items():
        p = float(tf_points.get(tf, 0))
        w = WEIGHTS.get(tf, 1.0)
        if b.upper().startswith("BU"):
            total += w * p
            wsum  += w * p
        elif b.upper().startswith("SE"):
            total -= w * p
            wsum  += w * p
    return total, wsum

def derive_final_bias(total):
    if total >= 3.5:  return "BUY"
    if total <= -3.5: return "SELL"
    if total >= 1.5:  return "BUY (weak)"
    if total <= -1.5: return "SELL (weak)"
    return "NEUTRAL"

def confidence_0_10(tf_points, sent_score):
    tech_total = sum(min(4,int(v)) for v in tf_points.values())  # max 4 each TF
    # Normalize tech to 0..10 assuming 5 TFs *4 = 20 -> scale to 0..8, then add up to +2 from sentiment(0..6)
    tech_part = min(10.0, (tech_total/20.0)*8.0)
    sent_part = min(2.0, (sent_score/6.0)*2.0)
    return round(tech_part + sent_part, 1)

def countertrend_note(final_bias, tf_bias):
    """If final bias opposes higher TF (h4/d1), flag counter-trend."""
    hi = [tf_bias.get("h4","NEUTRAL").upper(), tf_bias.get("d1","NEUTRAL").upper()]
    if final_bias.startswith("BUY") and ("SELL" in hi):
        return "Counter-trend — use tight SL & quick TP."
    if final_bias.startswith("SELL") and ("BUY" in hi):
        return "Counter-trend — use tight SL & quick TP."
    return "Aligned with higher timeframe."

def to_card_payload(args, tf_points, tf_bias):
    # Build timeframes section with emojis
    emoji_map = {"BUY":"🔴","SELL":"🟢","NEUTRAL":"🟡"}
    tfs={}
    for tf in ORDER:
        if tf in tf_bias:
            b = tf_bias[tf].upper()
            key = "NEUTRAL"
            if b.startswith("BU"): key="BUY"
            elif b.startswith("SE"): key="SELL"
            tfs[tf] = {
                "bias": tf_bias[tf],
                "reason": "points="+str(tf_points.get(tf,0)),
                "emoji": emoji_map[key]
            }
    total, wsum = score_bias(tf_bias, tf_points)
    final_bias = derive_final_bias(total)
    note = countertrend_note(final_bias, tf_bias)
    conf = confidence_0_10(tf_points, args.sent)

    payload = {
        "symbol": args.symbol,
        "time": datetime.utcnow().strftime("%H:%M UTC"),
        "entry": args.entry, "sl": args.sl, "tp1": args.tp1, "tp2": args.tp2,
        "timeframes": tfs,
        "final_bias": final_bias,
        "confidence": str(conf),
        "note": note,
        "reasons": args.why or []
    }
    return payload

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="infile", help="tf_snapshot.json")
    ap.add_argument("--symbol", default="EURUSD")
    ap.add_argument("--entry", type=float, default=0.0)
    ap.add_argument("--sl",    type=float, default=0.0)
    ap.add_argument("--tp1",   type=float, default=0.0)
    ap.add_argument("--tp2",   type=float, default=0.0)
    ap.add_argument("--points", help="m5=2,h1=3,h5=1,h4=4,d1=3")
    ap.add_argument("--bias",   help="m5=SELL,h1=SELL,h5=SELL,h4=BUY,d1=BUY")
    ap.add_argument("--sent",   type=int, default=0, help="0..6")
    ap.add_argument("--why", action="append", help="reason bullet; repeatable")
    args = ap.parse_args()

    if args.infile:
        with open(os.path.expanduser(args.infile),"r",encoding="utf-8") as f:
            j = json.load(f)
        args.symbol = j.get("symbol", args.symbol)
        args.entry  = float(j.get("entry", args.entry))
        args.sl     = float(j.get("sl", args.sl))
        args.tp1    = float(j.get("tp1", args.tp1))
        args.tp2    = float(j.get("tp2", args.tp2))
        tf_points   = {k:int(v) for k,v in j.get("tech_points",{}).items()}
        tf_bias     = {k:str(v) for k,v in j.get("tf_bias",{}).items()}
        args.sent   = int(j.get("sent_score", args.sent))
        args.why    = j.get("reasons", args.why)
    else:
        tf_points = as_int_dict(parse_kv(args.points or ""))
        tf_bias   = parse_kv(args.bias or "")

    payload = to_card_payload(args, tf_points, tf_bias)

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH,"w",encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"Wrote {OUT_PATH}")
    print(json.dumps(payload, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
