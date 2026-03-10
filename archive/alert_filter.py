#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import time
from typing import Dict, List, Any

"""
BotA alert cooldown filter (Step C — trade/watch tiers)

Contract:
- stdin: JSON array from analytics.py, e.g.
  [
    {
      "pair": "EURUSD",
      "weighted": 7,
      "bias": "BUY",
      "tier": "trade" | "watch",
      "session": "ASIA" | "LONDON" | "NEW_YORK" | "LON_NY_OL",
      "source": "HYBRID" | "SCALPER_ONLY" | "HTF_ONLY",
      "strength": 7.0
    },
    ...
  ]

- env:
    ALERT_STATE_PATH   (optional) path to JSON state file
    COOL_DOWN_MIN      base cooldown (minutes) for backward compatibility
    COOL_DOWN_MIN_TRADE  per-pair cooldown for tier=="trade"
    COOL_DOWN_MIN_WATCH  per-pair cooldown for tier=="watch"
    UPDATE_STATE       "1"/"true" to persist state, anything else = dry run

- stdout: JSON array with same shape, but with items suppressed
          if they are inside cooldown window and NOT stronger than the last
          alert for that (pair, tier).

This preserves legacy behaviour:
- If COOL_DOWN_MIN_TRADE / _WATCH are NOT set, both tiers use COOL_DOWN_MIN.
- Old state entries keyed only by "PAIR" are still honoured on first run.
"""

# --- config & state paths ----------------------------------------------------

STATE_PATH = os.getenv(
    "ALERT_STATE_PATH",
    os.path.expanduser("~/BotA/state/alert_state.json"),
)

BASE_COOL_MIN = int(os.getenv("COOL_DOWN_MIN", "30"))
COOL_MIN_TRADE = int(os.getenv("COOL_DOWN_MIN_TRADE", str(BASE_COOL_MIN)))
COOL_MIN_WATCH = int(os.getenv("COOL_DOWN_MIN_WATCH", str(BASE_COOL_MIN)))

UPDATE = os.getenv("UPDATE_STATE", "0") in ("1", "true", "TRUE", "yes", "YES")


def load_state() -> Dict[str, Any]:
    """Load cooldown state from disk; tolerate missing/corrupt file."""
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            # Must be dict to be valid; otherwise reset.
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_state(st: Dict[str, Any]) -> None:
    """Atomically write cooldown state to disk."""
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    tmp = STATE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=2)
    os.replace(tmp, STATE_PATH)


def _tier_of(item: Dict[str, Any]) -> str:
    """
    Normalize tier.
    - Prefer explicit 'tier' from analytics.py.
    - Fallback to 'trade' as safe default.
    """
    raw = str(item.get("tier", "")).strip().lower()
    if raw in ("trade", "watch"):
        return raw
    return "trade"


def _cooldown_minutes(tier: str) -> int:
    """Return cooldown window in minutes for given tier."""
    if tier == "watch":
        return COOL_MIN_WATCH
    return COOL_MIN_TRADE


def _state_key(pair: str, tier: str) -> str:
    """Build state key. Pair is assumed upper-case by caller."""
    return f"{pair}:{tier}"


def filter_items(items: List[Dict[str, Any]], now: int, state: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Core filter:
    - Per (pair, tier) track last timestamp and last weighted score.
    - Allow new alert if:
        • outside cooldown window, OR
        • abs(current_weighted) > abs(last_weighted)  (stronger signal)
    """
    out: List[Dict[str, Any]] = []

    # Backward compatibility: legacy state may use just "PAIR" as key.
    legacy_state = {k: v for k, v in state.items() if ":" not in k}

    for it in items:
        pair = str(it.get("pair", "")).upper() or "UNKNOWN"
        weighted = int(it.get("weighted", 0))

        tier = _tier_of(it)
        cd_min = _cooldown_minutes(tier)
        key = _state_key(pair, tier)

        last = state.get(key)
        if last is None:
            # try legacy "PAIR" key on first run after upgrade
            last = legacy_state.get(pair, {})

        last_ts = int(last.get("ts", 0) or 0)
        last_w = int(last.get("weighted", 0) or 0)

        cooldown_ok = (now - last_ts) >= cd_min * 60
        stronger = abs(weighted) > abs(last_w)

        if cooldown_ok or stronger:
            out.append(it)
            if UPDATE:
                state[key] = {"ts": now, "weighted": weighted}
        # else: inside cooldown AND not stronger -> suppressed

    return out


def main() -> int:
    now = int(time.time())
    state = load_state()

    raw = sys.stdin.read()
    try:
        arr = json.loads(raw) if raw.strip() else []
        if not isinstance(arr, list):
            arr = []
    except Exception:
        arr = []

    filtered = filter_items(arr, now, state)

    if UPDATE:
        save_state(state)

    print(json.dumps(filtered, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
