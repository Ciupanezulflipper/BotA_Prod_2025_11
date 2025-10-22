#!/usr/bin/env python3
# market_clock.py — zero-dep countdowns for major sessions

import datetime as dt
from typing import Dict, Tuple

# Approx FX sessions (UTC wall clock; DST is handled by using UTC as base)
SESSIONS_UTC = {
    "FX Global Open": (6, 22, 0),   # Sunday 22:00 UTC -> weekday=6 (Sun)
    "London":         (0, 7, 0),    # Mon–Fri 07:00 UTC
    "New York":       (0, 12, 0),   # Mon–Fri 12:00 UTC
}

def _next_weekday_after(base: dt.datetime, weekday: int) -> dt.datetime:
    """Return next date (today or later) whose weekday()==weekday.
       weekday: Mon=0..Sun=6"""
    days_ahead = (weekday - base.weekday()) % 7
    return base + dt.timedelta(days=days_ahead)

def _fmt_delta(h: int, m: int) -> str:
    parts = []
    if h: parts.append(f"{h}h")
    if m: parts.append(f"{m}m")
    return " ".join(parts) if parts else "0m"

def _localize(utc_dt: dt.datetime) -> dt.datetime:
    # Convert a UTC-aware datetime to the device's local tz
    return utc_dt.astimezone()

def next_open_counts(now_utc: dt.datetime=None) -> Dict[str, Tuple[str, str]]:
    """
    Returns dict:
      name -> (local_time_str, countdown_str)
    local_time_str is in device local timezone.
    """
    if now_utc is None:
        now_utc = dt.datetime.now(dt.timezone.utc)

    out: Dict[str, Tuple[str, str]] = {}
    for name, (weekday, hour, minute) in SESSIONS_UTC.items():
        # target this week (or today)
        base_date = _next_weekday_after(now_utc, weekday)
        target_utc = dt.datetime(
            year=base_date.year, month=base_date.month, day=base_date.day,
            hour=hour, minute=minute, tzinfo=dt.timezone.utc
        )
        # If target already passed for this particular session and it’s a weekday session,
        # move to the next weekday (skip weekends for London/NY)
        if name != "FX Global Open" and now_utc >= target_utc:
            # move to next day until Mon–Fri
            d = 1
            while True:
                cand = target_utc + dt.timedelta(days=d)
                if cand.weekday() < 5:  # Mon..Fri
                    target_utc = dt.datetime(
                        cand.year, cand.month, cand.day, hour, minute, tzinfo=dt.timezone.utc
                    )
                    break
                d += 1
        elif name == "FX Global Open":
            # If we already passed this Sunday's open, move to next Sunday
            if now_utc >= target_utc:
                target_utc = target_utc + dt.timedelta(days=7)

        delta = target_utc - now_utc
        total_mins = int(delta.total_seconds() // 60)
        h, m = divmod(total_mins, 60)
        local_str = _localize(target_utc).strftime("%a %H:%M %Z")
        out[name] = (local_str, _fmt_delta(h, m))

    return out

def render_countdown_block(now_utc: dt.datetime=None) -> str:
    data = next_open_counts(now_utc)
    lines = ["⏳ Next openings (your local time):"]
    # Show in a nice order
    for key in ("FX Global Open", "London", "New York"):
        if key in data:
            t_local, left = data[key]
            emoji = "🌐" if key=="FX Global Open" else ("🇬🇧" if key=="London" else "🇺🇸")
            lines.append(f"{emoji} {key}: {t_local}  ({left} left)")
    return "\n".join(lines)
