#!/usr/bin/env python3
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta, time, timezone

# Toggle this to mute sends around daily rollover (spreads explode)
ENABLE_DAILY_ROLLOVER_MUTE = True
ROLLOVER_MUTE_START = time(21, 59)   # 21:59 UTC
ROLLOVER_MUTE_END   = time(22, 5)    # 22:05 UTC

# FX weekend closure we enforce
FRI_CLOSE_UTC = time(21, 0)  # Fri 21:00 UTC
SUN_OPEN_UTC  = time(21, 5)  # Sun 21:05 UTC

@dataclass(frozen=True)
class FxGateStatus:
    closed: bool
    reason: str
    next_open: datetime | None
    hours_left: float | None

def _now_utc() -> datetime:
    return datetime.now(timezone.utc)

def _today_utc(d: datetime, t: time) -> datetime:
    return d.replace(hour=t.hour, minute=t.minute, second=0, microsecond=0)

def _in_window(d: datetime, start: time, end: time) -> bool:
    s = _today_utc(d, start)
    e = _today_utc(d, end)
    if e <= s:
        # crosses midnight
        return d >= s or d < e
    return s <= d < e

def _weekend_closed_status(now: datetime) -> FxGateStatus:
    wd = now.weekday()  # Mon=0 ... Sun=6
    # Fri after close
    if wd == 4 and now.time() >= FRI_CLOSE_UTC:
        # next open: Sun 21:05
        days_ahead = (6 - wd)  # to Sunday
        open_dt = _today_utc(now + timedelta(days=days_ahead), SUN_OPEN_UTC)
        hours_left = (open_dt - now).total_seconds() / 3600.0
        return FxGateStatus(True, "WEEKEND(Fri after close)", open_dt, hours_left)
    # Sat (full day closed)
    if wd == 5:
        open_dt = _today_utc(now + timedelta(days=1), SUN_OPEN_UTC)
        hours_left = (open_dt - now).total_seconds() / 3600.0
        return FxGateStatus(True, "WEEKEND(Saturday)", open_dt, hours_left)
    # Sun before open
    if wd == 6 and now.time() < SUN_OPEN_UTC:
        open_dt = _today_utc(now, SUN_OPEN_UTC)
        hours_left = (open_dt - now).total_seconds() / 3600.0
        return FxGateStatus(True, "WEEKEND(Sun before open)", open_dt, hours_left)
    return FxGateStatus(False, "OPEN", None, None)

def _rollover_mute_status(now: datetime) -> FxGateStatus | None:
    if not ENABLE_DAILY_ROLLOVER_MUTE:
        return None
    if _in_window(now, ROLLOVER_MUTE_START, ROLLOVER_MUTE_END):
        # next "open" is end of mute window (same day or next)
        s = _today_utc(now, ROLLOVER_MUTE_START)
        e = _today_utc(now, ROLLOVER_MUTE_END)
        if e <= s and now.time() >= ROLLOVER_MUTE_START:
            e = e + timedelta(days=1)
        hours_left = (e - now).total_seconds() / 3600.0
        return FxGateStatus(True, "ROLLOVER_MUTE", e, hours_left)
    return None

def status() -> FxGateStatus:
    now = _now_utc()
    wk = _weekend_closed_status(now)
    if wk.closed:
        return wk
    roll = _rollover_mute_status(now)
    if roll:
        return roll
    return FxGateStatus(False, "OPEN", None, None)

# Public helpers
def is_fx_closed_now() -> bool:
    return status().closed

def hours_until_open() -> float:
    st = status()
    return st.hours_left if st.closed and st.hours_left is not None else 0.0

if __name__ == "__main__":
    st = status()
    if st.closed:
        nxt = st.next_open.isoformat() if st.next_open else "n/a"
        print(f"[MARKET_GUARD] CLOSED: {st.reason}, opens in {st.hours_left:.2f}h @ {nxt}")
    else:
        print("[MARKET_GUARD] OPEN")
