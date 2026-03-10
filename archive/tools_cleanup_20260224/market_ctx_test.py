#!/usr/bin/env python3
from datetime import datetime, timezone
from tz_helper import resolve_display_zone
from market_hours import fx_market_state, fmt_eta

disp_tz = resolve_display_zone()
now_utc = datetime.now(timezone.utc)
st = fx_market_state(now_utc)

print(f"Now (UTC): {now_utc:%Y-%m-%d %H:%M:%S} | Local({disp_tz.key}): {now_utc.astimezone(disp_tz):%Y-%m-%d %H:%M:%S}")
print(f"Forex: {'OPEN' if st['is_open'] else 'CLOSED'}")
if not st['is_open']:
    eta = fmt_eta(st['next_global_open_utc'], now_utc)
    print(f"Next global open: {st['next_global_open_utc']} (in {eta})")

print("Next sessions:")
for name, when_utc in st["sessions_utc"]:
    eta = fmt_eta(when_utc, now_utc)
    print(f"  • {name} opens at {when_utc} UTC  (in {eta})  | local: {when_utc.astimezone(disp_tz):%Y-%m-%d %H:%M}")
