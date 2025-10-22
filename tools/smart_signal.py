#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Smart signal wrapper (EURUSD only)
- Pulls base decision via final_runner.analyse(symbol) (read-only).
- Fetches TF OHLC via tools.data_rotator.get_ohlc_rotating (respects your provider rotation & free limits).
- Scores TECH to 16/16 using EMA/RSI/MACD/ADX + Candles + Fibonacci across 5m,1h,4h,1d (4 pts each).
- TP/SL via ATR(14) on 4h (fallback 1h). RR = 1.5, SL = 1.2*ATR.
- Sends ONLY on: flip, or 16/16, or >=80% (>=13/16). 20 min cooldown (ignored on flip).
- Writes state to ~/bot-a/logs/smart_eurusd_state.json.
No edits to final_runner.py.
"""

from __future__ import annotations
import os, json, argparse
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Tuple

import numpy as np
import pandas as pd

# Use existing project modules
from tools.final_runner import analyse          # base decision/entry/providers
from tools.data_rotator import get_ohlc_rotating

# ---------- indicators ----------
def ema(s: pd.Series, span: int) -> pd.Series:
    return s.ewm(span=span, adjust=False).mean()

def rsi(s: pd.Series, period: int = 14) -> pd.Series:
    d = s.diff()
    up = d.clip(lower=0).ewm(alpha=1/period, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1/period, adjust=False).mean()
    rs = up / (dn + 1e-12)
    return 100 - (100/(1+rs))

def macd(s: pd.Series, fast=12, slow=26, signal=9):
    m = ema(s, fast) - ema(s, slow)
    sig = ema(m, signal)
    hist = m - sig
    return m, sig, hist

def adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    h,l,c = df["high"], df["low"], df["close"]
    up = h.diff()
    dn = -l.diff()
    plus_dm  = ((up > dn) & (up > 0)) * up
    minus_dm = ((dn > up) & (dn > 0)) * dn
    tr = pd.concat([(h-l).abs(), (h-c.shift()).abs(), (l-c.shift()).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1/period, adjust=False).mean()
    plus_di  = 100 * (plus_dm.ewm(alpha=1/period, adjust=False).mean() / (atr + 1e-12))
    minus_di = 100 * (minus_dm.ewm(alpha=1/period, adjust=False).mean() / (atr + 1e-12))
    dx = 100 * (plus_di - minus_di).abs() / ((plus_di + minus_di) + 1e-12)
    return dx.ewm(alpha=1/period, adjust=False).mean()

def atr(df: pd.DataFrame, period: int = 14) -> float:
    h,l,c = df["high"], df["low"], df["close"]
    tr = pd.concat([(h-l).abs(), (h-c.shift()).abs(), (l-c.shift()).abs()], axis=1).max(axis=1)
    a = tr.ewm(alpha=1/period, adjust=False).mean().iloc[-1]
    val = float(a)
    if not np.isfinite(val) or val <= 0:
        raise ValueError("ATR invalid")
    return val

# ---------- candles (simple, robust) ----------
def candle_bias(df: pd.DataFrame) -> int:
    """+1 bullish, -1 bearish, 0 neutral (engulfing / hammer / shooting-star)"""
    if len(df) < 2: return 0
    p, c = df.iloc[-2], df.iloc[-1]
    # engulfing
    bull = (p["close"] < p["open"]) and (c["close"] > c["open"]) and (c["open"] <= p["close"]) and (c["close"] >= p["open"])
    bear = (p["close"] > p["open"]) and (c["close"] < c["open"]) and (c["open"] >= p["close"]) and (c["close"] <= p["open"])
    if bull: return +1
    if bear: return -1
    body = abs(c["close"] - c["open"])
    rng  = c["high"] - c["low"]
    if rng <= 0: return 0
    lower = min(c["open"], c["close"]) - c["low"]
    upper = c["high"] - max(c["open"], c["close"])
    if body/rng < 0.3:
        if lower > 2*body: return +1   # hammer
        if upper > 2*body: return -1   # shooting star
    return 0

# ---------- fibonacci ----------
FIBS = [0.382, 0.5, 0.618]

def recent_swing(df: pd.DataFrame, lookback: int = 120) -> Tuple[float,float]:
    d = df.tail(lookback)
    return float(d["high"].max()), float(d["low"].min())

def fib_bias(df: pd.DataFrame, side_hint: str, lookback: int = 120) -> int:
    hi, lo = recent_swing(df, lookback)
    if hi <= lo: return 0
    close = float(df["close"].iloc[-1])
    levels = [hi - (hi-lo)*f for f in FIBS]
    nearest = min(levels, key=lambda x: abs(close - x))
    dist = abs(close - nearest) / (hi - lo + 1e-12)
    if dist > 0.02:  # >2% of swing -> ignore
        return 0
    if side_hint == "BUY":  return +1
    if side_hint == "SELL": return -1
    return 0

# ---------- per-TF scoring (max 4 each) ----------
def tf_points(df: pd.DataFrame, side: str) -> int:
    """
    4 checks = 4 pts per TF:
      1) Trend (EMA9 vs EMA21)
      2) Momentum (MACD hist sign)
      3) RSI band (trend-aware loose bands)
      4) Strength (ADX >= 25)
    Candles/Fib can fill a missing point up to the cap of 4.
    """
    c = df["close"]
    e9, e21 = ema(c,9).iloc[-1], ema(c,21).iloc[-1]
    _, _, mh = macd(c)
    mhv = float(mh.iloc[-1])
    r14 = float(rsi(c,14).iloc[-1])
    adx14 = float(adx(df,14).iloc[-1])

    pts = 0
    trend_ok = (e9 > e21) if side=="BUY" else (e9 < e21)
    if trend_ok: pts += 1
    mom_ok = (mhv > 0) if side=="BUY" else (mhv < 0)
    if mom_ok: pts += 1
    if side=="BUY" and 45 <= r14 <= 70: pts += 1
    if side=="SELL" and 30 <= r14 <= 55: pts += 1
    if adx14 >= 25: pts += 1

    if pts < 4 and ((side=="BUY" and candle_bias(df) > 0) or (side=="SELL" and candle_bias(df) < 0)):
        pts += 1
    if pts < 4 and ((side=="BUY" and fib_bias(df,"BUY") > 0) or (side=="SELL" and fib_bias(df,"SELL") < 0)):
        pts += 1
    return min(4, pts)

# ---------- TP/SL ----------
def derive_tp_sl(side: str, entry: float, df4h: pd.DataFrame, atr_mult=1.2, rr=1.5) -> Tuple[float,float]:
    a = atr(df4h,14) * atr_mult
    if side=="BUY":
        sl = entry - a
        tp = entry + (entry - sl) * rr
    else:
        sl = entry + a
        tp = entry - (sl - entry) * rr
    r = lambda x: float(np.round(x,5))
    return r(tp), r(sl)

# ---------- Telegram ----------
def tg_send_md(text: str) -> None:
    tok = os.getenv("TELEGRAM_BOT_TOKEN")
    chat = os.getenv("TELEGRAM_CHAT_ID") or os.getenv("TELEGRAM_CHAT")
    if not tok or not chat:
        print("[smart] Telegram env missing; would send:\n", text)
        return
    import urllib.request, urllib.parse
    url = f"https://api.telegram.org/bot{tok}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": chat, "text": text, "parse_mode": "Markdown"}).encode()
    with urllib.request.urlopen(url, data=data, timeout=10) as r:
        _ = r.read()

# ---------- state ----------
def state_path(symbol: str) -> Path:
    return Path.home()/ "bot-a" / "logs" / f"smart_{symbol.lower()}_state.json"

def load_state(p: Path) -> Dict:
    try: return json.loads(p.read_text())
    except Exception: return {}

def save_state(p: Path, s: Dict) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(s, indent=2))

# ---------- main run ----------
TF_LIST = ("5m","1h","4h","1d")

def run_once(symbol: str, threshold: float = 0.80, cooldown_min: int = 20, dry: bool = False) -> None:
    sp = state_path(symbol)
    prev = load_state(sp)

    base = analyse(symbol)  # do not modify final_runner
    decision = base.get("decision","HOLD")
    entry = float(base.get("entry", 0.0))
    providers = dict(base.get("providers") or {})

    # Fetch TF data through your rotator
    frames: Dict[str,pd.DataFrame] = {}
    provtf: Dict[str,str] = {}
    for tf, limit in (("5m",150),("1h",100),("4h",60),("1d",200)):
        try:
            df, p = get_ohlc_rotating(symbol, tf, limit=limit)
            frames[tf] = df
            provtf[tf] = p
        except Exception:
            continue

    # Per-TF points (use base decision as side hint; if HOLD -> infer by EMAs on 1h)
    side = decision
    if side == "HOLD":
        if "1h" in frames:
            c = frames["1h"]["close"]
            side = "BUY" if ema(c,9).iloc[-1] > ema(c,21).iloc[-1] else "SELL"

    tf_pts: Dict[str,int] = {}
    for tf in TF_LIST:
        if tf in frames:
            tf_pts[tf] = tf_points(frames[tf], side)

    tech_points = sum(tf_pts.values())
    tech_max = 4 * len(tf_pts) if tf_pts else 16
    tech_points = min(tech_points, 16)
    tech_max = min(tech_max, 16)
    ratio = tech_points / (tech_max or 1)

    # TP/SL
    tp = base.get("tp"); sl = base.get("sl")
    try:
        if tp is None or sl is None:
            if "4h" in frames:
                src_df, src_p = frames["4h"], provtf["4h"]
                tp, sl = derive_tp_sl(side, entry, src_df)
                providers["tp_sl"] = f"atr14@4h:{src_p}"
            elif "1h" in frames:
                src_df, src_p = frames["1h"], provtf["1h"]
                tp, sl = derive_tp_sl(side, entry, src_df)
                providers["tp_sl"] = f"atr14@1h:{src_p}"
    except Exception:
        pass

    # gating (flip / max / >=threshold) with cooldown
    now_utc = datetime.now(timezone.utc)
    signature = f"{side}:{round(entry,5)}:{tech_points}/{tech_max}"
    last_dec = prev.get("decision")
    last_sig = prev.get("last_signature")
    last_sent = prev.get("last_sent_ts")  # epoch seconds
    flip = last_dec and last_dec != side and side in ("BUY","SELL")
    hit_max = tech_points >= tech_max and tech_max > 0
    hit_thr = ratio >= threshold and signature != last_sig

    cooldown_ok = True
    if last_sent is not None:
        from time import time as _t
        cooldown_ok = (_t() - float(last_sent)) >= cooldown_min*60

    should_send = (flip) or (hit_max and cooldown_ok) or (hit_thr and cooldown_ok)

    # format card
    ts = now_utc.strftime("%H:%M")
    tf_line = "  ".join([f"{tf}={tf_pts[tf]}/4" for tf in TF_LIST if tf in tf_pts])
    pct = int(round(ratio*100))
    prov_bits = []
    for tf in TF_LIST:
        if tf in provtf: prov_bits.append(f"{tf}:{provtf[tf]}")
    if providers.get("tp_sl"): prov_bits.append(f"{providers['tp_sl']}")
    prov_line = ", ".join(prov_bits) if prov_bits else ""
    lines = [
        f"*{symbol}*  UTC {ts}",
        f"Decision: *{side}*",
        f"TF: {tf_line}" if tf_line else "TF: data missing",
        f"Score: *{tech_points}/{tech_max}* ({pct}%)",
        f"Entry≈ {entry:.5f}",
    ]
    if tp is not None and sl is not None:
        lines.append(f"TP≈ {tp:.5f}   SL≈ {sl:.5f}")
    if prov_line:
        lines.append(f"Prov: {prov_line}")
    card = "\n".join(lines)

    if dry:
        print("[smart] DRY (no send)")
        print(card)
        return

    if should_send:
        tg_send_md(card)
        from time import time as _t
        save_state(sp, {"decision": side, "last_signature": signature, "last_sent_ts": _t()})
        print(f"[smart] SENT ({'flip' if flip else 'max' if hit_max else f'thresh_{int(threshold*100)}'})")
    else:
        print(f"[smart] SKIP (no trigger or cooldown); score {tech_points}/{tech_max} ({pct}%)")
        print(card)

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="EURUSD")
    ap.add_argument("--threshold", type=float, default=0.80)     # 80%
    ap.add_argument("--cooldown", type=int, default=20)          # minutes
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()
    run_once(args.symbol.upper(), threshold=args.threshold, cooldown_min=args.cooldown, dry=args.dry)
