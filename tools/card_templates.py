#!/usr/bin/env python3
# tools/card_templates.py
# Format neat, compact cards for Telegram/console.

from __future__ import annotations
from typing import Optional

# ---- helpers ---------------------------------------------------------------

def _to_float(x, default: Optional[float] = None) -> Optional[float]:
    try:
        return float(x)
    except Exception:
        return default

def _stars_10(score: float) -> str:
    """Return 0–10 stars (★ empty when not filled)."""
    s = max(0.0, min(10.0, float(score)))
    full = int(round(s))
    return "★" * full + "☆" * (10 - full)

def _fmt_price(sym: str, val) -> str:
    """Format price with typical precision."""
    f = _to_float(val)
    if f is None:
        return "-"
    sym = (sym or "").upper()
    if sym == "EURUSD":
        return f"{f:.4f}"
    if sym == "XAUUSD":
        return f"{f:.2f}"
    # default
    return f"{f:.5f}"

def _fmt_conf(conf) -> str:
    c = _to_float(conf, 0.0)
    return f"{c:.1f}/10*  {_stars_10(c)}"

def _fmt_tech_bucket(bucket: Optional[str]) -> str:
    b = (bucket or "").strip().upper()
    if not b:
        return "*N/A*"
    score_hint = ""
    if b == "BUY":
        icon = "🟢"
    elif b == "SELL":
        icon = "🔴"
    elif b == "HOLD":
        icon = "📊"
    else:
        icon = "📊"
    return f"*{b}* {icon}"

def _fmt_risk(risk: Optional[str]) -> str:
    r = (risk or "Medium").strip().capitalize()
    icon = "🌞" if r == "Low" else ("🌤" if r == "Medium" else "🌡")
    return f"*{r}* {icon}"

def _fmt_direction(decision: str) -> str:
    d = (decision or "").upper()
    if d == "BUY":
        return "🟢 *BUY*"
    if d == "SELL":
        return "🔴 *SELL*"
    return "⚪ *HOLD*"

# ---- public API ------------------------------------------------------------

def compose_card(
    *,
    symbol: str,
    decision: str,
    news_score: Optional[int] = None,
    tech_bucket: Optional[str] = None,
    tech_score: Optional[int] = None,
    why: Optional[str] = None,
    confidence: Optional[float] = None,
    entry: Optional[str] = None,
    tp: Optional[str] = None,
    sl: Optional[str] = None,
    risk: Optional[str] = None,
    timeframe: Optional[str] = None,
    time_now: Optional[str] = None,
) -> str:
    """
    Build a single signal card.
    All fields are optional except symbol/decision; missing ones render as '-'.
    """
    sym = (symbol or "").upper()
    tf = timeframe or "-"
    news_txt = f"*{news_score}/10*" if news_score is not None else "*- /10*"
    tech_txt = _fmt_tech_bucket(tech_bucket)
    conf_txt = _fmt_conf(confidence if confidence is not None else 0.0)
    risk_txt = _fmt_risk(risk)
    e_txt = _fmt_price(sym, entry)
    tp_txt = _fmt_price(sym, tp)
    sl_txt = _fmt_price(sym, sl)
    dir_txt = _fmt_direction(decision or "HOLD")
    clock = time_now or ""

    lines = []
    lines.append(f"*{sym} Signal*")
    if clock:
        lines.append(f"🕒 {clock}")
    lines.append(f"• Direction: {dir_txt}")
    lines.append(f"🧠  News: *{news_txt}*   |   📊  Tech: {tech_txt}")
    lines.append(f"⭐  Confidence: *{conf_txt}*   |   {risk_txt}")
    lines.append(f"🎯  Entry: *{e_txt}*   •   TP: *{tp_txt}*   •   SL: *{sl_txt}*   •")
    lines.append(f"🕓 TTF: *{tf}*")
    lines.append("")  # spacer
    if (why or "").strip():
        lines.append("*Why*")
        lines.append(f"• {why.strip()}")
    return "\n".join(lines)

def compose_health_ping() -> str:
    """Simple one-liner health ping."""
    return "✅ Bot-A health ping"
