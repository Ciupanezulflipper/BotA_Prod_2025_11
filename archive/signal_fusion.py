#!/data/data/com.termux/files/usr/bin/python3
"""
Signal fusion helpers for BotA.

Current scope: only build_signal_card() used by tools/alerts_runner.py.
This function formats a compact, emoji-friendly Telegram card.

Contract (used by alerts_runner):
    build_signal_card(pair, frames_label, ind, df=None)

`ind` is a dict with:
    action            → "BUY" / "SELL" / "WAIT"
    score             → 0–16 (technical score)
    extra             → 0–6  (macro/sentiment score)
    reason            → short human-readable explanation
    risk              → "high" / "normal" / etc.
    signal_time_utc   → "YYYY-MM-DD HH:MM" or "n/a"
    entry             → float or None
    sl                → float or None
    tp                → float or None
    rr                → string, e.g. "1:1.50" or "n/a"
    spread            → string, e.g. "0.00012" or "n/a"
"""

from typing import Any, Dict


def _fmt_price(x: Any) -> str:
    try:
        v = float(x)
    except Exception:
        return "n/a"
    if v <= 0.0:
        return "n/a"
    return f"{v:.5f}"


def build_signal_card(
    pair: str,
    frames_label: str,
    ind: Dict[str, Any],
    df: Any = None,  # kept for compatibility, not used here
) -> str:
    action = (ind.get("action") or "WAIT").upper()
    score16 = int(ind.get("score") or 0)
    extra6 = int(ind.get("extra") or 0)
    reason = str(ind.get("reason") or "").strip()
    risk = str(ind.get("risk") or "high")
    signal_time_utc = str(ind.get("signal_time_utc") or "n/a")

    entry = ind.get("entry")
    sl = ind.get("sl")
    tp = ind.get("tp")
    rr = str(ind.get("rr") or "n/a")
    spread = str(ind.get("spread") or "n/a")

    # Action emoji
    if action == "BUY":
        action_label = "✅ BUY"
    elif action == "SELL":
        action_label = "🔻 SELL"
    else:
        action_label = "⏸️ WAIT"

    # Prices
    entry_str = _fmt_price(entry)
    sl_str = _fmt_price(sl) if sl is not None else "n/a"
    tp_str = _fmt_price(tp) if tp is not None else "n/a"

    # R:R and spread
    rr_str = rr if rr and rr.lower() != "n/a" else "n/a"
    spread_str = spread if spread else "n/a"

    # Build lines
    lines = []

    # Header
    lines.append(f"📊 {pair} ({frames_label})")

    # Time
    if signal_time_utc != "n/a":
        lines.append(f"🕒 Signal Time: {signal_time_utc} UTC")
    else:
        lines.append("🕒 Signal Time: n/a")

    # Action + score
    lines.append(f"📈 Action: {action_label}")
    lines.append(f"📊 Score: {score16}/16 + {extra6}/6")

    # Reason and risk
    if reason:
        lines.append(f"🧠 Reason: {reason}")
    else:
        lines.append("🧠 Reason: n/a")
    lines.append(f"⚠️ Risk: {risk}")

    # Levels / SL / TP
    lines.append(
        f"🎯 Levels: entry {entry_str}, SL {sl_str}, TP {tp_str}"
    )

    # R:R and spread on their own lines
    lines.append(f"📏 R:R: {rr_str}")
    lines.append(f"📉 Spread: {spread_str}")

    return "\n".join(lines)
