#!/usr/bin/env python3
# BotA — status_pretty v2.0 (modular, no external deps, safe add-on)
# Design merged from cross-audit (Grok, Gemini, Perplexity, Claude):
#   Sections: Header → Signal → Metrics → Health
#   Modes: basic (2-3 lines/pair) | advanced (4-6 lines/pair)
#   Core metrics: RSI, EMA(9/21) trend, Vote, Freshness
#   Health: freshness age, provider name (optional), cache state
#   Emojis: used as functional anchors, minimal & consistent
#
# This module is formatter-only. It accepts normalized dicts and returns
# Telegram-ready strings. No IO, no cache reads, no network calls.

from __future__ import annotations
from dataclasses import dataclass
from typing import List, Literal, Optional
import datetime as _dt

Mode = Literal["basic","advanced"]

@dataclass
class PairSnapshot:
    # Required
    pair: str                  # "EURUSD"
    tf: str                    # "H1","H4","D1"
    ts_utc_iso: str            # "2025-10-28 09:00:00Z"
    signal: Literal["BUY","SELL","NEUTRAL"]  # resolved direction
    rsi14: Optional[float]     # e.g., 61.2 (None -> "n/a")
    ema9_gt_21: Optional[bool] # True=↗, False=↘, None=→
    vote: Optional[int]        # e.g., +3, -2
    freshness_sec: Optional[int]   # seconds since data time
    # Optional health/context
    provider: Optional[str] = None     # e.g., "Yahoo"
    cache_ok: Optional[bool] = None    # True/False/None
    strong_signal: Optional[bool] = None  # emphasize strength

    # Optional advanced extras (only shown in advanced mode if present)
    adx: Optional[float] = None
    atr_pips: Optional[float] = None
    sentiment_bias: Optional[str] = None  # "bullish"/"bearish"/"neutral"

# ---------- emoji & helpers ----------

def _signal_emoji(sig: str) -> str:
    if sig == "BUY": return "🟢"
    if sig == "SELL": return "🔴"
    return "⚪"

def _trend_arrow(ema9_gt_21: Optional[bool]) -> str:
    if ema9_gt_21 is True: return "↗️"
    if ema9_gt_21 is False: return "↘️"
    return "→"

def _freshness_label(sec: Optional[int]) -> str:
    if sec is None: return "n/a"
    if sec < 60: return f"{sec}s"
    m = sec // 60
    if m < 60: return f"{m}m"
    h = m // 60
    return f"{h}h"

def _pair_pretty(sym: str) -> str:
    # Insert slash for common FX pairs if missing (EURUSD -> EUR/USD)
    if len(sym) == 6 and sym.isalpha():
        return f"{sym[:3]}/{sym[3:]}"
    return sym

def _safe_num(val: Optional[float], digits: int = 2) -> str:
    if val is None: return "n/a"
    try:
        return f"{float(val):.{digits}f}"
    except Exception:
        return "n/a"

def _vote_str(v: Optional[int]) -> str:
    if v is None: return "0"
    s = f"{v:+d}"
    return s

def _ts_short(ts_iso: str) -> str:
    # Accepts "YYYY-MM-DD HH:MM:SSZ" or "...Z" variants; returns "YYYY-MM-DD HH:MM UTC"
    t = ts_iso.replace("Z","").replace("T"," ")
    if "." in t: t = t.split(".")[0]
    if len(t) >= 16:
        return t[:16] + " UTC"
    return t + " UTC"

# ---------- public formatters ----------

def format_pair_basic(p: PairSnapshot) -> str:
    """
    Two lines per pair:
    1) 📊 EUR/USD H1 — 2025-10-28 09:00 UTC
    2) 🟢 BUY | RSI 61 | ↗️ +3 | 🩺 2m
    Health minimal; provider/cache only if useful.
    """
    header = f"📊 {_pair_pretty(p.pair)} {p.tf} — {_ts_short(p.ts_utc_iso)}"
    sig = f"{_signal_emoji(p.signal)} {p.signal}"
    rsi = f"RSI {_safe_num(p.rsi14,0)}"
    trend = f"{_trend_arrow(p.ema9_gt_21)} {_vote_str(p.vote)}"
    fresh = f"🩺 {_freshness_label(p.freshness_sec)}"
    # Keep under ~80 chars: join with pipes
    line2_parts = [sig, rsi, trend, fresh]
    line2 = " | ".join(line2_parts)
    return f"{header}\n{line2}"

def format_pair_advanced(p: PairSnapshot) -> str:
    """
    4–5 lines per pair:
      📊 EUR/USD H1 — 2025-10-28 09:00 UTC
      🟢 BUY (Trend: Bullish) — Vote +3
      📈 RSI 61 | EMA 9>21 ↗️
      🩺 Fresh 2m | Provider: Yahoo | Cache OK
    Optionally add a compact extras line (ADX/ATR/Sentiment) only if present.
    """
    header = f"📊 {_pair_pretty(p.pair)} {p.tf} — {_ts_short(p.ts_utc_iso)}"
    trend_name = "Bullish" if p.ema9_gt_21 is True else ("Bearish" if p.ema9_gt_21 is False else "Range")
    sig = f"{_signal_emoji(p.signal)} {p.signal} (Trend: {trend_name}) — Vote {_vote_str(p.vote)}"
    # metrics
    ema_str = "EMA 9>21" if p.ema9_gt_21 is True else ("EMA 9<21" if p.ema9_gt_21 is False else "EMA 9≈21")
    metrics = f"📈 RSI {_safe_num(p.rsi14,0)} | {ema_str} {_trend_arrow(p.ema9_gt_21)}"
    # health
    provider = f" | Provider: {p.provider}" if p.provider else ""
    cache = ""
    if p.cache_ok is True: cache = " | Cache OK"
    elif p.cache_ok is False: cache = " | Cache WARN"
    health = f"🩺 Fresh {_freshness_label(p.freshness_sec)}{provider}{cache}"
    # extras only when provided
    extras = []
    if p.adx is not None: extras.append(f"ADX {_safe_num(p.adx,0)}")
    if p.atr_pips is not None: extras.append(f"ATR {_safe_num(p.atr_pips,0)}p")
    if p.sentiment_bias: extras.append(f"Sentiment {p.sentiment_bias}")
    if extras:
        return f"{header}\n{sig}\n{metrics}\n{health}\n" + "🧪 " + " | ".join(extras)
    return f"{header}\n{sig}\n{metrics}\n{health}"

def format_status(pairs: List[PairSnapshot], mode: Mode = "basic") -> str:
    """Join multiple pairs with a blank line separator. Keeps total < ~3500 chars."""
    blocks: List[str] = []
    fmt = format_pair_basic if mode == "basic" else format_pair_advanced
    for p in pairs:
        blocks.append(fmt(p))
    out = "\n\n".join(blocks)
    # Hard safety trim under Telegram 4096. Prefer trimming at pair boundary.
    if len(out) > 4000:
        trimmed = out[:4000]
        cut = trimmed.rfind("\n\n📊")
        if cut > 0:
            return trimmed[:cut] + "\n\n⚠️ Output truncated. Use /status <PAIR>."
        return trimmed[:3950] + "\n\n⚠️ Output truncated."
    return out

# --------- tiny self-test runner (manual) ---------
if __name__ == "__main__":
    demo = [
        PairSnapshot(pair="EURUSD", tf="H1", ts_utc_iso="2025-10-28 09:00:00Z",
                     signal="BUY", rsi14=61.4, ema9_gt_21=True, vote=3,
                     freshness_sec=125, provider="Yahoo", cache_ok=True),
        PairSnapshot(pair="GBPUSD", tf="H1", ts_utc_iso="2025-10-28 09:05:00Z",
                     signal="SELL", rsi14=38.1, ema9_gt_21=False, vote=-2,
                     freshness_sec=750, provider="Yahoo", cache_ok=True, adx=28.0, atr_pips=12.4)
    ]
    print("=== BASIC ===")
    print(format_status(demo, mode="basic"))
    print("\n=== ADVANCED ===")
    print(format_status(demo, mode="advanced"))
