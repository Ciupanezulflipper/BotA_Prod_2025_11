# BotA/tools/signal_card.py
"""
Thin wrapper around build_signal_card() to keep old imports working.

Exports:
- format_card(ind, *, pair, tf, df=None, **_)  -> str
- render_signal_card(pair, tf, ind=None, df=None, rows=None, **_) -> str

Both call BotA.tools.signal_fusion.build_signal_card under the hood.
"""

from __future__ import annotations

from typing import Any, Optional
from BotA.tools.signal_fusion import build_signal_card

__all__ = ["format_card", "render_signal_card"]


def format_card(
    ind: Any,
    *,
    pair: str,
    tf: str,
    df: Optional[Any] = None,
    **_: Any,
) -> str:
    """
    Backward-compatible wrapper. Accepts optional df and ignores extra kwargs.
    """
    return build_signal_card(pair, tf, ind, df=df)


def render_signal_card(
    pair: str,
    tf: str,
    ind: Optional[Any] = None,
    df: Optional[Any] = None,
    rows: Optional[Any] = None,
    **_: Any,
) -> str:
    """
    Wrapper with convenience:
    - if df is None and rows is provided, convert rows -> DataFrame (best-effort)
    - if ind is None, produce a neutral WAIT card
    - ignores extra kwargs for compatibility
    """
    if df is None and rows is not None:
        try:
            # Best-effort conversion if available
            from BotA.tools.ohlc_fix import to_dataframe
            df = to_dataframe(rows)
        except Exception:
            # Silent fallback: df stays None; build_signal_card has its own guards
            pass

    if ind is None:
        # Neutral defaults if caller didn’t provide analysis result
        ind = {
            "action": "WAIT",
            "score": "n/a",
            "extra": "n/a",
            "reason": "n/a",
            "risk": "normal",
            "signal_time_utc": "n/a",
            "spread": None,
        }

    return build_signal_card(pair, tf, ind, df=df)
