#!/usr/bin/env python3
from __future__ import annotations

import sys
import json
import datetime as dt
from typing import List, Dict, Any


def detect_session(hour: int) -> str:
    """
    Map UTC hour -> trading session.

    ASIA:      21–23, 0–6
    LONDON:    7–11
    LON_NY_OL: 12–16
    NEW_YORK:  17–20
    """
    if hour >= 21 or hour <= 6:
        return "ASIA"
    if 7 <= hour <= 11:
        return "LONDON"
    if 12 <= hour <= 16:
        return "LON_NY_OL"
    return "NEW_YORK"


def current_session() -> str:
    now = dt.datetime.utcnow()
    return detect_session(now.hour)


def _preferred_tf(weighted: int) -> str:
    aw = abs(weighted)
    if aw >= 6:
        return "D1"
    if aw >= 3:
        return "H4"
    return "H1"


def _dummy_analytics(weighted: int) -> Dict[str, Dict[str, Any]]:
    """
    Lightweight placeholder analytics so downstream formatters
    always see H1/H4/D1 keys.
    """
    sign = 1.0 if weighted > 0 else -1.0 if weighted < 0 else 0.0
    base = {
        "vote_mean_5": sign,
        "macd_mean_5": 0.0,
        "div_rsi": "none",
    }
    return {
        "H1": dict(base),
        "H4": dict(base),
        "D1": dict(base),
    }


def enrich_item(item: Dict[str, Any]) -> Dict[str, Any]:
    it: Dict[str, Any] = dict(item)  # shallow copy

    # Core numerics
    w = int(it.get("weighted", 0) or 0)
    aw = abs(w)
    it["weighted"] = w
    it["strength"] = float(aw)
    it["preferred_tf"] = _preferred_tf(w)

    # Analytics stub (we can wire real values later)
    if "analytics" not in it:
        it["analytics"] = _dummy_analytics(w)

    # Session tagging
    session = it.get("session") or "UNKNOWN"
    if session == "UNKNOWN":
        session = current_session()
    it["session"] = session

    # Tier / reason defaults
    tier = it.get("tier")
    if not tier:
        tier = "trade" if aw >= 1 else "watch"
    it["tier"] = tier

    reason = it.get("reason") or "status"
    source = (it.get("source") or "").upper()

    # --- Asia logic (Boatmaster Rulebook v2.2) ---
    # - SCALPER_ONLY in ASIA  -> always watch
    # - HYBRID in ASIA:
    #       |w| < 6  -> watch (weak hybrid)
    #       |w| >= 6 -> trade allowed, but tagged
    if session == "ASIA" and tier == "trade":
        if source == "SCALPER_ONLY":
            it["tier"] = "watch"
            it["reason"] = reason + "|asia_downgrade_scalper"
        elif source == "HYBRID" and aw < 6:
            it["tier"] = "watch"
            it["reason"] = reason + "|asia_downgrade_weak_hybrid"
        elif source == "HYBRID" and aw >= 6:
            it["reason"] = reason + "|asia_strong_hybrid_ok"
        else:
            # Any other source in ASIA gets tagged but not forcibly changed
            it["reason"] = reason + "|asia_other"
    else:
        # Non-Asia or non-trade tier: just keep reason as-is
        it["reason"] = reason

    return it


def main() -> int:
    raw = sys.stdin.read().strip()
    if not raw:
        print("[]")
        return 0
    try:
        data = json.loads(raw)
        if not isinstance(data, list):
            data = []
    except Exception:
        data = []
    out = [enrich_item(it) for it in data]
    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
