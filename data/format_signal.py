#!/usr/bin/env python3
# data/format_signal.py  — build luxury caption + generate chart PNG
import os, math, io, datetime as dt
from typing import List, Dict, Tuple, Optional

import matplotlib
matplotlib.use("Agg")  # headless
import matplotlib.pyplot as plt
import mplfinance as mpf

# ---------- helpers ----------

def _ema(vals: List[float], n: int) -> List[float]:
    if not vals or n <= 1: return vals[:]
    k = 2.0/(n+1.0)
    ema = []
    s = None
    for v in vals:
        if s is None: s = v
        else: s = v*k + s*(1-k)
        ema.append(s)
    return ema

def _atr(candles: List[Dict], n: int=14) -> float:
    if len(candles) < 2: return 0.0
    trs = []
    for i in range(1, len(candles)):
        h = float(candles[i]["h"]); l = float(candles[i]["l"])
        c1 = float(candles[i-1]["c"])
        trs.append(max(h-l, abs(h-c1), abs(l-c1)))
    if not trs: return 0.0
    n = min(n, len(trs))
    # simple MA for robustness
    return sum(trs[-n:])/n

def _fmt_price(sym: str, x: float) -> str:
    # coarse tick sizes (good enough for free-tier test)
    if sym.endswith("USD") and sym != "XAUUSD":
        return f"{x:.5f}"
    if sym == "XAUUSD":
        return f"{x:.2f}"
    return f"{x:.5f}"

def _class_color(score_class: str) -> Tuple[str,str]:
    # returns (word, emoji)
    d = {
        "STRONG": ("Bullish","🟢"),
        "MODERATE": ("Bullish","🟢"),
        "WEAK": ("Bearish","🔴"),
        "HOLD": ("—","⚪"),
    }
    return d.get(score_class.upper(), ("—","⚪"))

# ---------- chart ----------

def _chart_png(symbol: str,
               candles: List[Dict],
               entry: float, stop: float, target: float,
               outdir: str) -> str:
    """
    Save a nice chart with EMA9/21 and entry/SL/TP lines. Returns PNG path.
    """
    os.makedirs(outdir, exist_ok=True)

    # Build DataFrame-like structure for mplfinance
    import pandas as pd
    idx = []
    o,h,l,c,v = [],[],[],[],[],[]
    for cndl in candles:
        # cndl: {"t":ts,"o":,"h":,"l":,"c":,"v":}
        ts = cndl.get("t")
        if isinstance(ts, (int,float)):
            ts = dt.datetime.utcfromtimestamp(ts/1000.0 if ts>10**12 else ts)
        elif isinstance(ts, str):
            try: ts = dt.datetime.fromisoformat(ts.replace("Z",""))
            except: ts = dt.datetime.utcnow()
        idx.append(ts)
        o.append(float(cndl["o"])); h.append(float(cndl["h"]))
        l.append(float(cndl["l"])); c.append(float(cndl["c"]))
        v.append(float(cndl.get("v",0.0)))

    import numpy as np
    df = pd.DataFrame({"Open":o,"High":h,"Low":l,"Close":c,"Volume":v}, index=pd.DatetimeIndex(idx))

    close = df["Close"].tolist()
    ema9  = _ema(close, 9)
    ema21 = _ema(close, 21)
    add_plots = [
        mpf.make_addplot(ema9,  color='tab:blue'),
        mpf.make_addplot(ema21, color='tab:orange'),
    ]

    # Style
    s = mpf.make_mpf_style(base_mpf_style="yahoo", gridstyle=":", gridaxis="y")

    # Plot
    fig, axlist = mpf.plot(
        df.tail(200),
        type="candle",
        volume=False,
        addplot=add_plots,
        style=s,
        returnfig=True,
        figsize=(8,4.2),
        tight_layout=True
    )
    ax = axlist[0]

    # Draw entry/stop/target
    ymin, ymax = ax.get_ylim()
    for y, label, col in [
        (entry,  "Entry", "#2ca02c"),
        (stop,   "Stop",  "#d62728"),
        (target, "Target","#1f77b4"),
    ]:
        ax.axhline(y, color=col, linewidth=1.4, alpha=0.9)
        ax.text(df.index[-1], y, f"  {label} {y}", color=col, va="center", fontsize=8)

    png = os.path.join(outdir, f"{symbol}_{dt.datetime.utcnow().strftime('%Y%m%d_%H%M%S')}Z.png")
    fig.savefig(png, dpi=150)
    plt.close(fig)
    return png

# ---------- caption ----------

def build_caption_and_chart(symbol: str,
                            tf: str,
                            res: Dict,
                            candles: List[Dict],
                            outdir: str = "charts") -> Tuple[str, Optional[str]]:
    """
    Given engine result + candles, return (caption_text, chart_path).
    """
    # Safety
    if not isinstance(res, dict) or not res.get("ok"):
        why = res.get("why","engine error") if isinstance(res, dict) else "engine error"
        return f"❌ {symbol}: N/A ({why})", None

    comps = res.get("components", {})
    score = float(res.get("score", 0))
    cls   = str(res.get("class","HOLD"))

    # Direction wording
    mood, dot = _class_color(cls)
    if mood == "—":
        mood = "Neutral"

    # Entry/SL/TP from ATR
    close = float(candles[-1]["c"]) if candles else float(res.get("last",0) or 0)
    atr = _atr(candles, 14) or (0.002 if symbol=="XAUUSD" else 0.0007)
    # Use score to bias: higher score => bullish tilt; low score => bearish tilt
    bullish_bias = score >= 60
    bearish_bias = score <= 40
    # default HOLD uses structure only
    if bullish_bias:
        entry, stop, target = close, close - 0.7*atr, close + 1.4*atr
    elif bearish_bias:
        entry, stop, target = close, close + 0.7*atr, close - 1.4*atr
    else:
        # HOLD: smaller targets
        entry, stop, target = close, close - 0.5*atr, close + 1.0*atr

    rr = abs((target-entry) / (entry-stop)) if (entry-stop)!=0 else 2.0

    # Components pretty
    trend   = comps.get("trend",0)
    mom     = comps.get("momentum",0)
    volume  = comps.get("volume",0)
    struct  = comps.get("structure",0)
    volat   = comps.get("volatility",0)

    nowz = dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%SZ")

    caption = (
        f"📈 <b>{symbol}</b> — {mood} {dot}\n"
        f"<i>Time:</i> {nowz}  •  <i>TF:</i> {tf}\n\n"
        f"• <b>Signal:</b> {score:.0f}/100 ({cls})\n"
        f"  — trend {trend}, mom {mom}, vol {volume}, struct {struct}, volat {volat}\n\n"
        f"• <b>Trade Plan</b>\n"
        f"  — <b>Entry:</b> <code>{_fmt_price(symbol,entry)}</code>\n"
        f"  — <b>Stop:</b>  <code>{_fmt_price(symbol,stop)}</code>\n"
        f"  — <b>Target:</b> <code>{_fmt_price(symbol,target)}</code>  (<b>RR</b> {rr:.1f})\n\n"
        f"• <b>Why?</b> structure/momentum mix\n\n"
        f"• <b>Risk:</b> suggest 0.5%–1.0%  •  <b>Session:</b> auto\n"
    )

    # Chart
    png = None
    try:
        if candles:
            png = _chart_png(symbol, candles, entry, stop, target, outdir)
    except Exception:
        png = None  # fail-safe; still post caption

    return caption, png
