#!/usr/bin/env python3
# Bot A — Daily summary (EURUSD H1)
# PRD rule: full-file replacement, no inline patching.

from __future__ import annotations
import os
import re
import datetime as dt
from pathlib import Path

# We only need tg_send; this does not change the runner or loop.
from tools.tg_send import send_message  # uses your TELEGRAM_* env

# --- Config (matches your current setup) ---
HOME = Path(os.path.expanduser("~"))
LOG  = HOME / "bot-a" / "logs" / "auto_h1.log"   # produced by auto_h1.sh loop
TITLE = "🧾 Bot A H1 daily summary"
# -------------------------------------------

# Use timezone-aware UTC (fixes DeprecationWarning from utcnow()).
TODAY_UTC = dt.datetime.now(dt.UTC).date()

TIME_RE = re.compile(r"^🕒\s+(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2})\s+UTC")
ACT_RE  = re.compile(r"^📈\s+Action:\s+(BUY|SELL|WAIT|HOLD)\s*$", re.I)

def parse_log_today(log_path: Path):
    """Return list of (time_str, action) for entries dated TODAY_UTC."""
    if not log_path.exists():
        return []

    entries: list[tuple[str, str]] = []
    current_ts: dt.datetime | None = None

    with log_path.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.rstrip("\n")

            # 1) capture the timestamp line
            mt = TIME_RE.match(line)
            if mt:
                d_s, hm_s = mt.group(1), mt.group(2)
                try:
                    ts = dt.datetime.strptime(f"{d_s} {hm_s}", "%Y-%m-%d %H:%M")
                    ts = ts.replace(tzinfo=dt.UTC)
                    current_ts = ts
                except Exception:
                    current_ts = None
                continue

            # 2) capture the action, tied to the most recent timestamp
            ma = ACT_RE.match(line)
            if ma and current_ts is not None and current_ts.date() == TODAY_UTC:
                action = ma.group(1).upper()
                entries.append((current_ts.strftime("%H:%M"), action))
                # after logging one action, we keep current_ts for possible repeats
                # (your runner prints exactly one action per block)
    return entries

def summarize(entries: list[tuple[str, str]]) -> str:
    if not entries:
        return f"{TITLE} (UTC {TODAY_UTC})\nNo signals recorded today."

    buy  = sum(1 for _,a in entries if a == "BUY")
    sell = sum(1 for _,a in entries if a == "SELL")
    wait = sum(1 for _,a in entries if a == "WAIT")
    hold = sum(1 for _,a in entries if a == "HOLD")
    total = len(entries)
    last_t, last_a = entries[-1]

    # recent last 8
    recent = "\n".join([f"• {t} {a}" for t,a in entries[-8:]])

    msg = (
        f"{TITLE} (UTC {TODAY_UTC})\n"
        f"Signals: {total}  (BUY {buy}, SELL {sell}, WAIT {wait}, HOLD {hold})\n"
        f"Last: {last_t} {last_a}\n\n"
        f"Recent:\n{recent}"
    )
    return msg

def main():
    entries = parse_log_today(LOG)
    text = summarize(entries)
    ok, info = send_message(text)
    # Be quiet on success; print only for manual runs
    if __name__ == "__main__":
        print("send:", ok, info)

if __name__ == "__main__":
    main()
