#!/usr/bin/env python3
from datetime import datetime, timedelta, timezone

# Get device local tz safely (no external deps)
LOCAL_TZ = datetime.now().astimezone().tzinfo
UTC = timezone.utc

def now_utc():
    return datetime.now(UTC)

def to_local(dt_utc):
    return dt_utc.astimezone(LOCAL_TZ)

def fmt_dhms(dt_delta):
    secs = int(dt_delta.total_seconds())
    if secs < 0: secs = 0
    h, r = divmod(secs, 3600)
    m, _ = divmod(r, 60)
    return f"{h}h {m}m"

def next_weekday(dt, weekday):
    # weekday: Mon=0 .. Sun=6 ; returns next occurrence (>= dt if exactly)
    days_ahead = (weekday - dt.weekday()) % 7
    return dt + timedelta(days=days_ahead)

def forex_sessions(now):
    """
    Define canonical FX sessions as UTC anchors (Sun..Fri).
    We compute open/close purely in UTC, then render duration in local time.
    Sydney:   Sun 22:00–Mon 07:00 (UTC)  (daylight shifts handled by 'local' presentation)
    Tokyo:    Mon 00:00–09:00 (UTC)
    London:   Mon 07:00–16:00 (UTC)
    New York: Mon 12:00–21:00 (UTC)
    For simplicity, we roll daily windows based on 'now' weekday.
    """
    wd = now.weekday()  # Mon=0..Sun=6, but we also need Sun => treat Sun as 6
    # Build today's anchors
    base = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # Today's windows (UTC)
    tokyo_open  = base + timedelta(hours=0)
    tokyo_close = base + timedelta(hours=9)

    london_open  = base + timedelta(hours=7)
    london_close = base + timedelta(hours=16)

    ny_open  = base + timedelta(hours=12)
    ny_close = base + timedelta(hours=21)

    # Sydney spans late Sunday UTC to Monday morning UTC. If we’re before Mon 07:00 UTC,
    # use today’s close; otherwise compute the next window.
    # Compute most recent Sun 22:00 UTC and next Mon 07:00 UTC around 'now'
    # Find last Sunday 22:00
    last_sun = base - timedelta(days=((wd + 1) % 7))  # back to Sunday 00:00
    sydney_open = last_sun + timedelta(hours=22)
    sydney_close = next_weekday(base, 0) + timedelta(hours=7)  # next Monday 07:00

    # If we've passed today's windows, roll forward 1 day
    def roll_forward(o,c):
        if now >= c:
            o += timedelta(days=1)
            c += timedelta(days=1)
        return o,c

    tokyo_open, tokyo_close = roll_forward(tokyo_open, tokyo_close)
    london_open, london_close = roll_forward(london_open, london_close)
    ny_open, ny_close = roll_forward(ny_open, ny_close)

    # Sydney: if we’re past close, push to next Sun 22:00 -> Mon 07:00
    if now >= sydney_close:
        # next Sunday 22:00
        next_sun = next_weekday(base + timedelta(days=1), 6)  # next Sunday 00:00
        sydney_open = next_sun + timedelta(hours=22)
        sydney_close = next_weekday(sydney_open, 0).replace(hour=7, minute=0, second=0, microsecond=0)

    return {
        "Sydney": (sydney_open, sydney_close),
        "Tokyo": (tokyo_open, tokyo_close),
        "London": (london_open, london_close),
        "NewYork": (ny_open, ny_close),
    }

def line_for(name, o_utc, c_utc, now):
    if o_utc <= now < c_utc:
        # OPEN
        left = fmt_dhms(c_utc - now)
        return f"{name}: OPEN (closes in {left})"
    elif now < o_utc:
        # Not yet open
        left = fmt_dhms(o_utc - now)
        return f"{name} opens in {left}"
    else:
        # After close -> next day’s open
        next_open = o_utc + timedelta(days=1)
        left = fmt_dhms(next_open - now)
        return f"{name} opens in {left}"

def main():
    now = now_utc()
    sess = forex_sessions(now)
    lines = []
    lines.append("Forex: <b>OPEN</b> (Weekend guard may mute sends)")
    for k in ("Sydney","Tokyo","London","NewYork"):
        o,c = sess[k]
        lines.append(line_for(k, o, c, now))
    print("\n".join(lines))

if __name__ == "__main__":
    main()
