# BotA/tools/signal_fusion.py

from __future__ import annotations
import pandas as pd

def _calc_spread_fallback(df: pd.DataFrame | None, pair: str) -> str:
    """Fallback spread calculation from last two candles."""
    if df is None or df.empty:
        return "n/a"
    try:
        last_close = float(df["close"].iloc[-1])
        prev_close = float(df["close"].iloc[-2])
        spread_val = abs(last_close - prev_close) * 10000  # 4-digit pips
        return f"{spread_val:.1f} pips"
    except Exception:
        return "n/a"

def build_signal_card(pair: str, tf: str, ind: dict | object, df: pd.DataFrame | None = None) -> str:
    """
    Normalize indicator results into a text card.
    Accepts dict or IndicatorResult-like objects.
    """
    # Normalize to dict
    if hasattr(ind, "__dict__"):
        ind = vars(ind)
    elif not isinstance(ind, dict):
        try:
            ind = dict(ind)
        except Exception:
            ind = {}

    action = str(ind.get("action", "WAIT")).upper()
    score16 = ind.get("score", "n/a")
    bonus6 = ind.get("extra", "n/a")
    reason = ind.get("reason", "n/a")
    risk = str(ind.get("risk", "normal")).lower()
    signal_time = ind.get("signal_time_utc", "n/a")

    # Spread
    spread = ind.get("spread", None)
    if spread is None:
        spread_text = _calc_spread_fallback(df, pair)
    else:
        try:
            s = float(spread)
            spread_text = (
                f"{s:.1f}" if s >= 1.0 else
                (f"{s:.1f}" if abs((s * 10) % 1) < 1e-6 else f"{s:.2f}")
            ) + " pips"
        except Exception:
            spread_text = "n/a"

    # Action map
    action_map = {"BUY": "✅ BUY", "SELL": "❌ SELL", "WAIT": "⏸️ WAIT"}
    action_text = action_map.get(action, "⏸️ WAIT")

    # Reason
    if isinstance(reason, list):
        reason_text = " + ".join(map(str, reason))
    elif isinstance(reason, str):
        reason_text = reason
    else:
        reason_text = "n/a"

    # Build card
    return (
        f"📊 {pair} ({tf})\n"
        f"🕒 Signal Time: {signal_time} UTC\n"
        f"📈 Action: {action_text}\n"
        f"📊 Score: {score16}/16 + {bonus6}/6\n"
        f"🧠 Reason: {reason_text}\n"
        f"⚠️ Risk: {risk}\n"
        f"📉 Spread: {spread_text}"
    )
