#!/data/data/com.termux/files/usr/bin/python3
### BEGIN FILE: tools/signal_guard.py
import os, time, datetime as dt
from typing import Dict, Any

# --------------------------------
# Trading session gate
# --------------------------------
# Allowed trading hours (UTC) → London + NY overlap
OPEN_UTC  = int(os.environ.get("OPEN_UTC", "6"))   # 06:00 UTC
CLOSE_UTC = int(os.environ.get("CLOSE_UTC", "20")) # 20:00 UTC

def session_gate() -> (bool, str):
    """Return (ok, reason) depending on UTC trading hours."""
    now = dt.datetime.utcnow().hour
    if OPEN_UTC <= now < CLOSE_UTC:
        return True, "inside window"
    return False, f"outside trading window (UTC {OPEN_UTC:02d}-{CLOSE_UTC:02d})"

# --------------------------------
# Duplicate / cooldown guard
# --------------------------------
_last_decisions: Dict[str, float] = {}

def should_skip_duplicate(symbol: str, decision: str, ttl: int = 60) -> bool:
    """
    Skip if same decision for symbol within ttl seconds.
    """
    key = f"{symbol.upper()}::{decision}"
    now = time.time()
    last = _last_decisions.get(key, 0)
    if now - last < ttl:
        return True
    _last_decisions[key] = now
    return False

class Cooldown:
    def __init__(self, minutes: int = 10):
        self.minutes = minutes

def cooldown(key: str, cd: Cooldown) -> bool:
    """
    Skip if same key fired within cooldown window.
    """
    now = time.time()
    last = _last_decisions.get(key, 0)
    if now - last < cd.minutes * 60:
        return True
    _last_decisions[key] = now
    return False
### END FILE
