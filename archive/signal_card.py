#!/usr/bin/env python3
"""
tools/signal_card.py

Pure formatting helper for Telegram "Card v1" messages.
No network, no file I/O, no subprocess.

API:
  format_card_v1(meta: dict, candidates: list[dict]) -> str
"""

from __future__ import annotations

from typing import Any, Dict, List


def _s(x: Any) -> str:
    if x is None:
        return ""
    try:
        return str(x).strip()
    except Exception:
        return ""


def _f(x: Any, default: float = 0.0) -> float:
    try:
        return float(x)
    except Exception:
        return default


def _fmt_price(x: Any, decimals: int) -> str:
    v = _f(x, 0.0)
    if v == 0.0:
        return "0"
    return f"{v:.{decimals}f}"


def _fmt_rr(x: Any) -> str:
    v = _f(x, 0.0)
    if v <= 0.0:
        return "0.00"
    return f"{v:.2f}"


def _badge(direction: str) -> str:
    d = _s(direction).upper()
    if d == "BUY":
        return "🔺 🟢"
    if d == "SELL":
        return "🔻 🔴"
    return "⏸️ ⚪️"


def format_card_v1(meta: Dict[str, Any], candidates: List[Dict[str, Any]]) -> str:
    utc = _s(meta.get("utc", ""))
    phase = _s(meta.get("phase", ""))
    updater_ok = bool(meta.get("updater_ok", False))
    timeframes = _s(meta.get("timeframes", ""))
    rr_min = _s(meta.get("rr_min", ""))
    hard_errors_new = _s(meta.get("hard_errors_new", "0"))

    lines: List[str] = []
    lines.append("📡 BotA Strong Signals (Card v1)")
    if utc:
        lines.append(f"UTC={utc}")
    if phase:
        lines.append(f"PHASE={phase}")
    if timeframes:
        lines.append(f"UPDATER={'OK' if updater_ok else 'FAIL'} ({timeframes})")
    else:
        lines.append(f"UPDATER={'OK' if updater_ok else 'FAIL'}")
    if rr_min:
        lines.append(f"RR_MIN={rr_min}")
    if hard_errors_new:
        lines.append(f"HARD_ERRORS_NEW={hard_errors_new}")
    lines.append("")

    if not updater_ok:
        lines.append("❌ FAIL-CLOSED: indicators update failed, so no trade candidates are emitted.")
        return "\n".join(lines).strip()

    if not candidates:
        lines.append("ℹ️ No candidates met gates right now.")
        return "\n".join(lines).strip()

    for c in candidates:
        pair = _s(c.get("pair", "")).upper()
        direction = _s(c.get("dir", c.get("direction", ""))).upper()

        # JPY pairs: 3 decimals; others: 5
        dec = 3 if pair.endswith("JPY") else 5

        entry = c.get("entry", 0.0)
        sl = c.get("sl", 0.0)
        tp = c.get("tp", 0.0)
        rr = c.get("rr", c.get("filter_rr", 0.0))
        score = _s(c.get("score", "0"))
        h1_trend = _s(c.get("h1_trend", "")).upper()
        h1_adx = _s(c.get("h1_adx", ""))
        advisory = _s(c.get("advisory", ""))

        lines.append(f"{_badge(direction)} {pair} — {direction or 'HOLD'}")
        lines.append(f"Entry: {_fmt_price(entry, dec)}")
        lines.append(f"SL: {_fmt_price(sl, dec)} | TP: {_fmt_price(tp, dec)}")
        lines.append(f"RR: {_fmt_rr(rr)} | Score: {score}")
        if h1_trend or h1_adx:
            lines.append(f"H1: {h1_trend or 'NA'} | ADX: {h1_adx or 'NA'}")
        if advisory:
            lines.append(f"Note: {advisory}")
        lines.append("")

    return "\n".join(lines).strip()
