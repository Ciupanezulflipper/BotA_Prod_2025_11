# BotA/tools/ind_bridge.py
from __future__ import annotations
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable

UTC_FMT = "%Y-%m-%d %H:%M"

def _utc_now_str() -> str:
    return datetime.now(timezone.utc).strftime(UTC_FMT)

def _to_plain_dict(obj: Any) -> Dict[str, Any]:
    """
    Convert IndicatorResult-like objects to a plain dict safely.
    Handles: dict, dataclass, objects with __dict__, and (key,value) iterables.
    """
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return dict(obj)
    if is_dataclass(obj):
        return asdict(obj)
    if hasattr(obj, "__dict__"):
        return dict(obj.__dict__)
    try:
        return dict(obj)  # e.g., list of tuples
    except Exception:
        return {"value": obj}

def _first_present(d: Dict[str, Any], keys: Iterable[str], default: Any = None) -> Any:
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return default

def _join_reason(val: Any) -> str:
    if val is None:
        return "n/a"
    if isinstance(val, str):
        return val
    if isinstance(val, (list, tuple, set)):
        return " + ".join(str(x) for x in val if x is not None and str(x) != "")
    return str(val)

def normalize_for_card(ind_obj: Any, *, pair: str, tf: str) -> Dict[str, Any]:
    """
    Produce the exact dict the card formatter expects:
      action (BUY/SELL/WAIT), score, extra, reason, risk, spread, signal_time_utc
    It is purposely defensive—works with many indicator payload shapes.
    """
    raw = _to_plain_dict(ind_obj) or {}

    # lowercase mirror for flexible lookup
    low = {str(k).lower(): v for k, v in raw.items()}

    action = _first_present(low, ["action", "signal", "side", "decision"], "WAIT")
    # score parts (our card shows “score/16 + extra/6”)
    score16 = _first_present(low, ["score16", "score_16", "score"], "n/a")
    bonus6  = _first_present(low, ["bonus6", "bonus_6", "extra", "extrascore"], "n/a")

    # fallback: if a single numeric “score” 0..22 is provided, split it roughly
    try:
        if score16 == "n/a" and isinstance(low.get("score"), (int, float)):
            total = float(low["score"])
            score16 = int(round(min(max(total, 0), 22)))  # clamp
            if score16 > 16:
                bonus6 = score16 - 16
                score16 = 16
    except Exception:
        pass

    reason = _join_reason(_first_present(low, ["reason", "reasons", "explain", "why"], "n/a"))
    risk   = _first_present(low, ["risk", "risk_level"], "normal")

    # spread can be numeric or text; leave as-is if present
    spread = _first_present(low, ["spread", "spread_pips"], None)

    # time keys that might exist
    sig_time = _first_present(
        low,
        ["signal_time_utc", "signal_time", "time_utc", "timestamp_utc", "ts", "t"],
        None,
    )
    if not sig_time:
        sig_time = _utc_now_str()

    return {
        "pair": pair,
        "tf": tf,
        "action": str(action).upper(),
        "score": score16,
        "extra": bonus6,
        "reason": reason,
        "risk": str(risk).lower(),
        "spread": spread,
        "signal_time_utc": sig_time,
    }
