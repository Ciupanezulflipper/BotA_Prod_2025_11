from __future__ import annotations
import json, os
from typing import Tuple
from datetime import datetime, timezone

STATE_PATH = os.getenv("BOTA_STATE_FILE", os.path.expanduser("~/.cache/bota/state.json"))
os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)

def _read_state():
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _write_state(obj):
    tmp = STATE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f)
    os.replace(tmp, STATE_PATH)

def should_suppress(symbol: str, tf: str, candle_time_iso: str, direction: int) -> Tuple[bool, str]:
    """
    Returns (suppress, reason).
    direction: 1=BUY, -1=SELL, 0=WAIT
    """
    st = _read_state()
    key = f"{symbol}:{tf}"
    last = st.get(key)
    if last and last.get("candle") == candle_time_iso and last.get("direction") == direction:
        return True, "duplicate_on_same_candle"
    st[key] = {"candle": candle_time_iso, "direction": direction, "ts": datetime.now(timezone.utc).isoformat()}
    _write_state(st)
    return False, ""
