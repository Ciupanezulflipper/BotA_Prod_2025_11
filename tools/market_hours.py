from __future__ import annotations
from datetime import datetime, timezone
import os
from typing import Optional, Set

UTC = timezone.utc

def _load_holidays(path: str) -> Set[str]:
    """Lines: YYYY-MM-DD (UTC)."""
    out = set()
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                s = line.strip().split("#", 1)[0]
                if s:
                    out.add(s)
    except FileNotFoundError:
        pass
    return out

def is_market_open(ts: Optional[datetime] = None) -> bool:
    """
    Simple 24x5 FX gate. Weekend is closed from Fri 22:00 UTC to Sun 21:00 UTC typically,
    but spreads/liquidity vary. We do a conservative rule:
      - Closed on Saturday (weekday=5) and most of Sunday (weekday=6) until 21:00 UTC.
    """
    ts = (ts or datetime.now(UTC)).astimezone(UTC)
    ymd = ts.strftime("%Y-%m-%d")

    # Optional holidays file
    holidays_path = os.getenv("FX_HOLIDAYS_FILE", os.path.expanduser("~/BotA/config/holidays.txt"))
    if ymd in _load_holidays(holidays_path):
        return False

    wd = ts.weekday()  # Mon=0 .. Sun=6
    h = ts.hour

    if wd == 5:  # Saturday
        return False
    if wd == 6 and h < 21:  # Sunday before ~21:00 UTC
        return False
    if wd == 4 and h >= 22:  # Late Friday (conservative)
        return False

    # Optional "quiet hours" (comma-separated UTC hours) -> suppress signals
    quiet = os.getenv("QUIET_UTC_HOURS", "").strip()
    if quiet:
        try:
            quiet_set = {int(x) for x in quiet.split(",") if x}
            if h in quiet_set:
                return False
        except Exception:
            pass

    return True
