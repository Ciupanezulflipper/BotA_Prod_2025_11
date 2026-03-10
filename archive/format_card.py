#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tools/format_card.py — Forex Profit Lab (Pro-Card C-3)
Parses JSON or legacy [run] lines and outputs Telegram-ready HTML.
"""

import sys, json, re, html

# ---------- helpers ----------
def _read_stdin():
    return sys.stdin.read().strip()

def _safe_float(x):
    try: return float(x)
    except: return None

def _fmt_price(x):
    v = _safe_float(x)
    if v is None: return "n/a"
    return f"{v:.5f}" if abs(v) < 1000 else f"{v:.2f}"

def _rr(entry, sl, tp):
    e, s, t = map(_safe_float, (entry, sl, tp))
    if None in (e, s, t) or e == s: return None
    return abs(t - e) / abs(e - s)

# ---------- legacy [run] ----------
def _parse_run(line:str):
    # example: [run] EURUSD TF15 decision=BUY score=82 weak=false provider=test age=0.2 price=1.1666 conf=78
    m = re.match(r"\[run\]\s+([A-Z]{3,6})\s+TF?(\d+)\s+(.*)", line, re.I)
    pair = m.group(1) if m else "UNKNOWN"
    tf = f"M{m.group(2)}" if m else "M15"
    rest = m.group(3) if m else line
    kv = dict(re.findall(r"(\w+)=([\w\.\-]+)", rest))
    return {
        "pair": pair,
        "tf": tf,
        "direction": kv.get("decision","HOLD").upper(),
        "entry": kv.get("price"),
        "sl": kv.get("sl"),
        "tp_list": [kv[k] for k in ("tp","tp1","tp2") if k in kv],
        "score": int(kv.get("score",0)),
        "confidence": int(kv.get("conf",kv.get("confidence",0))),
        "volatility": kv.get("vol"),
        "reason": kv.get("reason",""),
        "provider": kv.get("provider","")
    }

# ---------- JSON ----------
def _parse_json(txt:str):
    try:
        obj = json.loads(txt)
        if isinstance(obj,list) and obj: obj=obj[0]
    except Exception:
        return _parse_run(txt)
    tp=obj.get("tp") or obj.get("take_profit")
    tps=[]
    if isinstance(tp,list): tps=tp
    elif tp: tps=[tp]
    for k in ("tp1","tp2","tp3"):
        if obj.get(k): tps.append(obj[k])
    return {
        "pair": obj.get("pair") or obj.get("symbol") or "UNKNOWN",
        "tf": obj.get("tf") or obj.get("timeframe") or "M15",
        "direction": (obj.get("direction") or obj.get("decision") or "HOLD").upper(),
        "entry": obj.get("entry") or obj.get("price"),
        "sl": obj.get("sl") or obj.get("stop_loss"),
        "tp_list": tps,
        "score": int(obj.get("score",0)),
        "confidence": int(obj.get("confidence",obj.get("conf",0))),
        "volatility": obj.get("volatility"),
        "reason": obj.get("reason",""),
        "provider": obj.get("provider","")
    }

# ---------- main ----------
def main():
    raw=_read_stdin()
    if not raw:
        print("⚠️ no stdin input"); return
    data=_parse_json(raw) if raw.lstrip().startswith("{") else _parse_run(raw)
    p=data

    # icons
    strength="🟢" if p["score"]>=80 and p["confidence"]>=70 else "🟡" if p["score"]>=60 else "🟠"
    vol_icon=""
    if p["volatility"]:
        v=p["volatility"].lower()
        vol_icon="⚡" if "high" in v else "🌤️" if "med" in v else "🟢"

    # build message
    lines=[]
    lines.append(f"📣 <b>Forex Profit Lab</b> — {p['pair']} {p['tf']}")
    lines.append(f"{strength} <b>{p['direction']}</b> (score {p['score']}/100 conf {p['confidence']}/100 {vol_icon})")
    if p["entry"]: lines.append(f"🔹 <b>Entry:</b> {_fmt_price(p['entry'])}")
    if p["sl"]: lines.append(f"🔻 <b>Stop-Loss:</b> {_fmt_price(p['sl'])}")

    tps=p["tp_list"]
    if tps:
        if len(tps)==1:
            lines.append(f"🎯 <b>Take-Profit:</b> {_fmt_price(tps[0])}")
            r=_rr(p["entry"],p["sl"],tps[0])
            if r: lines.append(f"⚖️ <b>R/R:</b> {r:.2f}")
        else:
            for i,t in enumerate(tps,1):
                lines.append(f"🎯 <b>TP{i}:</b> {_fmt_price(t)}")
            if p["sl"]:
                vals=[_rr(p["entry"],p["sl"],t) for t in tps]
                rrtext=", ".join(f"{x:.2f}" if x else "?" for x in vals)
                lines.append(f"⚖️ <b>R/R:</b> {rrtext}")

    if p["reason"]: lines.append(f"🧠 <b>Bias / Notes:</b> {html.escape(p['reason'])}")
    if p["provider"]: lines.append(f"📡 <b>Provider:</b> {html.escape(p['provider'])}")
    lines.append("⚖️ <i>Not financial advice. Confirm on your chart.</i>")

    sys.stdout.write("\n".join(lines))

if __name__=="__main__":
    main()
