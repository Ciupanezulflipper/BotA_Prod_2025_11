#!/usr/bin/env python3
# dedupe_cache.py — simple time/price deduplication

import json, os
from datetime import datetime, timezone

CACHE_FILE = os.path.join(os.path.dirname(__file__), "last_signal_cache.json")

def should_send_signal(pair: str, action: str, entry_price: float,
                       time_window_minutes: int = 60,
                       price_window_pips: float = 4.0,
                       pip_size: float = 0.0001):
    cache = _load_cache()
    now = datetime.now(timezone.utc)
    key = f"{pair}:{action}"

    if key not in cache:
        return True, None

    last = cache[key]
    last_time = datetime.fromisoformat(last["timestamp"])
    last_entry = float(last["entry_price"])
    last_sent = bool(last.get("sent", False))
    age_min = (now - last_time).total_seconds() / 60

    # retry quickly if last send failed
    if not last_sent and age_min <= 5:
        return True, None

    if age_min <= time_window_minutes:
        pips = abs(entry_price - last_entry) / pip_size
        if pips <= price_window_pips:
            return False, f"Duplicate: {action} within {age_min:.0f}min, {pips:.1f} pips"
    return True, None

def mark_signal_sent(pair: str, action: str, entry_price: float, sent: bool = True):
    cache = _load_cache()
    now = datetime.now(timezone.utc)
    key = f"{pair}:{action}"
    cache[key] = {
        "timestamp": now.isoformat(),
        "entry_price": float(entry_price),
        "sent": bool(sent),
    }
    _save_cache(cache)

def _load_cache():
    if not os.path.exists(CACHE_FILE):
        return {}
    try:
        with open(CACHE_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}

def _save_cache(cache):
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2)
