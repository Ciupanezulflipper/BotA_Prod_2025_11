#!/usr/bin/env python3
"""
chart_generator.py — Rich signal chart with EMA/RSI/MACD panels.
Uses matplotlib + numpy. No pandas required.
Usage:
    python3 tools/chart_generator.py EURUSD   (sanity mode)
    python3 tools/chart_generator.py --pair EURUSD --tf M15 --direction BUY \
        --entry 1.0850 --sl 1.0820 --tp 1.0890 --score 75 --confidence 75 \
        --out logs/charts/signal.png
"""
import argparse, json, math, os, sys
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.dates as mdates
import numpy as np

ROOT   = Path(os.environ.get("BOTA_ROOT", Path.home() / "BotA"))
CACHE  = ROOT / "cache"
CHARTS = ROOT / "logs" / "charts"
CHARTS.mkdir(parents=True, exist_ok=True)


def sf(v, d=0.0):
    try:
        f = float(v)
        return d if math.isnan(f) or math.isinf(f) else f
    except Exception:
        return d


def load_ohlc(pair: str, tf: str) -> dict:
    path = CACHE / f"{pair}_{tf}.json"
    if not path.exists():
        raise FileNotFoundError(f"OHLC cache missing: {path}")
    with open(path) as f:
        raw = json.load(f)

    times, opens, highs, lows, closes = [], [], [], [], []

    if "rows" in raw and raw["rows"]:
        for r in raw["rows"]:
            t = r.get("time") or r.get("timestamp")
            if not t: continue
            try:
                if isinstance(t, (int, float)):
                    dt = datetime.fromtimestamp(t, tz=timezone.utc)
                else:
                    s = str(t).replace("Z", "+00:00")
                    dt = datetime.fromisoformat(s)
                    if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
            except: continue
            times.append(dt)
            opens.append(sf(r.get("open")))
            highs.append(sf(r.get("high")))
            lows.append(sf(r.get("low")))
            closes.append(sf(r.get("close")))
    elif "chart" in raw:
        result = raw["chart"]["result"][0]
        ts_list = result.get("timestamp", [])
        quotes = result.get("indicators", {}).get("quote", [{}])[0]
        for i, t in enumerate(ts_list):
            try: dt = datetime.fromtimestamp(t, tz=timezone.utc)
            except: continue
            times.append(dt)
            opens.append(sf(quotes.get("open", [0])[i]))
            highs.append(sf(quotes.get("high", [0])[i]))
            lows.append(sf(quotes.get("low", [0])[i]))
            closes.append(sf(quotes.get("close", [0])[i]))

    return {"time": times, "open": opens, "high": highs, "low": lows, "close": closes}


def load_indicators(pair: str, tf: str) -> dict:
    path = CACHE / f"indicators_{pair}_{tf}.json"
    if not path.exists(): return {}
    try:
        with open(path) as f: return json.load(f)
    except: return {}


def ema(values: list, period: int) -> list:
    result = [float("nan")] * len(values)
    if len(values) < period: return result
    k = 2.0 / (period + 1)
    seed = sum(values[:period]) / period
    result[period - 1] = seed
    for i in range(period, len(values)):
        result[i] = values[i] * k + result[i-1] * (1 - k)
    return result


def rsi(closes: list, period: int = 14) -> list:
    result = [float("nan")] * len(closes)
    if len(closes) < period + 1: return result
    gains, losses = [], []
    for i in range(1, len(closes)):
        d = closes[i] - closes[i-1]
        gains.append(max(d, 0))
        losses.append(max(-d, 0))
    ag = sum(gains[:period]) / period
    al = sum(losses[:period]) / period
    for i in range(period, len(closes)):
        if al == 0: result[i] = 100.0
        else: result[i] = 100 - (100 / (1 + ag / al))
        d = closes[i] - closes[i-1]
        ag = (ag * (period-1) + max(d, 0)) / period
        al = (al * (period-1) + max(-d, 0)) / period
    return result


def macd_hist(closes: list) -> list:
    e12 = ema(closes, 12); e26 = ema(closes, 26)
    macd_line = [a-b if not math.isnan(a) and not math.isnan(b) else float("nan")
                 for a, b in zip(e12, e26)]
    valid = [x for x in macd_line if not math.isnan(x)]
    signal = ema(valid, 9)
    nans_before = sum(1 for x in macd_line if math.isnan(x))
    signal_full = [float("nan")] * nans_before + signal
    signal_full = signal_full[:len(macd_line)]
    return [m-s if not math.isnan(m) and not math.isnan(s) else float("nan")
            for m, s in zip(macd_line, signal_full)]


def make_chart(out_path: str, pair: str, tf: str, direction: str,
               entry: float, sl: float, tp: float, score: float, confidence: float):
    try:
        ohlc = load_ohlc(pair, tf)
    except FileNotFoundError:
        ohlc = {"time": [], "open": [], "high": [], "low": [], "close": []}

    closes = ohlc["close"]
    n = min(len(closes), 80)
    times_plot = ohlc["time"][-n:] if n > 0 else []
    o = ohlc["open"][-n:]
    h = ohlc["high"][-n:]
    l = ohlc["low"][-n:]
    c = closes[-n:]

    all_c = closes if closes else [entry or 1.0]
    ema20 = ema(all_c, 20)[-n:] if n >= 20 else [float("nan")] * n
    ema50 = ema(all_c, 50)[-n:] if n >= 50 else [float("nan")] * n
    rsi14 = rsi(all_c)[-n:]     if n >= 15 else [float("nan")] * n
    macdh = macd_hist(all_c)[-n:] if n >= 35 else [float("nan")] * n

    fig = plt.figure(figsize=(12, 8), facecolor="#0d0d1a")
    gs  = fig.add_gridspec(3, 1, height_ratios=[3, 1, 1], hspace=0.05)
    ax1 = fig.add_subplot(gs[0])
    ax2 = fig.add_subplot(gs[1], sharex=ax1)
    ax3 = fig.add_subplot(gs[2], sharex=ax1)

    for ax in [ax1, ax2, ax3]:
        ax.set_facecolor("#0d0d1a")
        ax.tick_params(colors="#888", labelsize=7)
        ax.spines[:].set_color("#333")

    x = list(range(n))

    if n > 0:
        for i in range(n):
            bull = c[i] >= o[i]
            color = "#00c878" if bull else "#ff3355"
            ax1.plot([x[i], x[i]], [l[i], h[i]], color=color, linewidth=0.8, zorder=2)
            ax1.bar(x[i], max(o[i], c[i]) - min(o[i], c[i]),
                    bottom=min(o[i], c[i]), width=0.6, color=color, alpha=0.9, zorder=3)

    def plot_ema(ax, vals, color, label):
        cx = [x[i] for i in range(len(vals)) if not math.isnan(vals[i])]
        cv = [vals[i] for i in range(len(vals)) if not math.isnan(vals[i])]
        if cx: ax.plot(cx, cv, color=color, linewidth=1.2, label=label, zorder=4)

    if n > 0:
        plot_ema(ax1, ema20, "#ffaa00", "EMA20")
        plot_ema(ax1, ema50, "#6699ff", "EMA50")

    if entry: ax1.axhline(entry, color="#ffd700", linewidth=1.5, linestyle="--", zorder=5)
    if sl:    ax1.axhline(sl,    color="#ff4444", linewidth=1.2, linestyle=":",  zorder=5)
    if tp:    ax1.axhline(tp,    color="#00cc66", linewidth=1.2, linestyle=":",  zorder=5)

    if entry: ax1.text(n-1 if n else 1, entry, f" Entry {entry:.5f}", color="#ffd700", fontsize=7, va="center")
    if sl:    ax1.text(n-1 if n else 1, sl,    f" SL {sl:.5f}",       color="#ff4444", fontsize=7, va="center")
    if tp:    ax1.text(n-1 if n else 1, tp,    f" TP {tp:.5f}",       color="#00cc66", fontsize=7, va="center")

    dir_color = "#00cc66" if direction == "BUY" else "#ff3355"
    cur = c[-1] if c else entry
    rsi_val = rsi14[-1] if rsi14 and not math.isnan(rsi14[-1]) else 0
    atr_val = sf(load_indicators(pair, tf).get("atr", 0))
    tier = "GREEN" if score >= 65 else "YELLOW"
    ax1.set_title(
        f"[{tier}] BotA {pair} {tf} {direction}  score={score:.0f} conf={confidence:.0f}"
        f" | EMA21≈{cur:.5f} | RSI≈{rsi_val:.1f} | ATR≈{atr_val:.5f}",
        color=dir_color, fontsize=8, pad=4)

    if n >= 20: ax1.legend(fontsize=7, facecolor="#1a1a2e", edgecolor="#333",
                           labelcolor="white", loc="upper left")
    ax1.set_ylabel("Price", fontsize=7, color="#888")

    # RSI
    crx = [x[i] for i in range(len(rsi14)) if not math.isnan(rsi14[i])]
    crv = [rsi14[i] for i in range(len(rsi14)) if not math.isnan(rsi14[i])]
    if crx:
        ax2.plot(crx, crv, color="#aa88ff", linewidth=1.2)
        ax2.fill_between(crx, crv, 50, where=[v>=50 for v in crv], alpha=0.15, color="#00cc66")
        ax2.fill_between(crx, crv, 50, where=[v<50  for v in crv], alpha=0.15, color="#ff3355")
    ax2.axhline(70, color="#ff3355", linewidth=0.6, linestyle="--")
    ax2.axhline(30, color="#00cc66", linewidth=0.6, linestyle="--")
    ax2.axhline(50, color="#555",    linewidth=0.4)
    ax2.set_ylim(0, 100); ax2.set_ylabel("RSI", fontsize=7, color="#888")
    ax2.set_yticks([30, 50, 70])

    # MACD
    cmx = [x[i] for i in range(len(macdh)) if not math.isnan(macdh[i])]
    cmv = [macdh[i] for i in range(len(macdh)) if not math.isnan(macdh[i])]
    if cmx:
        ax3.bar(cmx, cmv, color=["#00c878" if v>=0 else "#ff3355" for v in cmv],
                width=0.6, alpha=0.8)
    ax3.axhline(0, color="#555", linewidth=0.6)
    ax3.set_ylabel("MACD", fontsize=7, color="#888")

    if c and entry:
        ax1.annotate("▲ BUY" if direction=="BUY" else "▼ SELL",
                     xy=(n//2 if n else 1, entry), color=dir_color,
                     fontsize=10, fontweight="bold", ha="center", va="center",
                     bbox=dict(boxstyle="round,pad=0.3", facecolor="#0d0d1a",
                               edgecolor=dir_color, alpha=0.8))

    plt.tight_layout()
    plt.savefig(out_path, dpi=100, bbox_inches="tight",
                facecolor="#0d0d1a", edgecolor="none")
    plt.close(fig)


def main():
    if len(sys.argv) == 2 and not sys.argv[1].startswith("-"):
        pair = sys.argv[1]
        try:
            ohlc = load_ohlc(pair, "M15")
            entry = sf(ohlc["close"][-1]) if ohlc["close"] else 1.0850
        except: entry = 1.0850
        sl, tp = entry*0.999, entry*1.002
        out = str(CHARTS / f"sanity_{pair}.png")
        make_chart(out, pair, "M15", "BUY", entry, sl, tp, 70.0, 70.0)
        print(f"[chart] OK → {out}")
        return

    ap = argparse.ArgumentParser()
    ap.add_argument("--pair",       default="EURUSD")
    ap.add_argument("--tf",         default="M15")
    ap.add_argument("--direction",  default="BUY")
    ap.add_argument("--entry",      type=float, default=0)
    ap.add_argument("--sl",         type=float, default=0)
    ap.add_argument("--tp",         type=float, default=0)
    ap.add_argument("--score",      type=float, default=65)
    ap.add_argument("--confidence", type=float, default=65)
    ap.add_argument("--out",        default="")
    args = ap.parse_args()

    if not args.out:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        args.out = str(CHARTS / f"{args.pair}_{args.direction}_{ts}.png")

    make_chart(args.out, args.pair, args.tf, args.direction.upper(),
               args.entry, args.sl, args.tp, args.score, args.confidence)
    print(args.out)


if __name__ == "__main__":
    main()
