#!/usr/bin/env python3
"""
BotA — UTC session classifier (v2.2)

Purpose
-------
Provide a single, canonical way to tag UTC time into trading sessions:

  • ASIA:        21:00–06:59  (wraps midnight; quieter, scalper-first)
  • LONDON:      07:00–11:59  (Europe active, core FX volume)
  • LON_NY_OL:   12:00–15:59  (London+New York overlap, peak liquidity)
  • NEW_YORK:    16:00–20:59  (NY only, still active)
  • OFF:         21:00–20:59 fallback (should not happen; safety only)

Notes
-----
- The ASIA block **crosses UTC midnight**, so hour >= 21 OR hour <= 6.
- Overlap ("LON_NY_OL") is treated as its own session; logic using this
  can treat it as either LONDON, NY, or a special case.
- This module is *read-only helper*; it does not touch any other files.
"""

from __future__ import annotations
import datetime as _dt
import json
import os
import sys
from typing import Literal, Dict

SessionType = Literal["ASIA", "LONDON", "LON_NY_OL", "NEW_YORK", "OFF"]


def session_for_hour(hour_utc: int) -> SessionType:
    """
    Map an integer UTC hour [0..23] to a session label.

    ASIA:
        21, 22, 23, 0, 1, 2, 3, 4, 5, 6
    LONDON:
        7, 8, 9, 10, 11
    LON_NY_OL (London+New York overlap):
        12, 13, 14, 15
    NEW_YORK:
        16, 17, 18, 19, 20
    OFF:
        only if hour is out-of-range (defensive fallback)
    """
    if not (0 <= hour_utc <= 23):
        return "OFF"  # defensive; should never happen

    # Asia crosses midnight: 21:00–06:59
    if hour_utc >= 21 or hour_utc <= 6:
        return "ASIA"
    # London: 07:00–11:59
    if 7 <= hour_utc <= 11:
        return "LONDON"
    # London + New York overlap: 12:00–15:59
    if 12 <= hour_utc <= 15:
        return "LON_NY_OL"
    # New York only: 16:00–20:59
    if 16 <= hour_utc <= 20:
        return "NEW_YORK"

    # Fallback
    return "OFF"


def classify_now_utc() -> Dict[str, object]:
    """
    Return a small JSON-able dict with current UTC time + session tag.
    """
    now = _dt.datetime.utcnow().replace(tzinfo=_dt.timezone.utc)
    hour = now.hour
    return {
        "iso_utc": now.isoformat(),
        "hour_utc": hour,
        "session": session_for_hour(hour),
    }


def main() -> int:
    """
    CLI usage:

      1) No args  → print current UTC session as JSON.
      2) One arg  → interpret as hour (0–23) and print session string.

    Examples:

        $ python3 tools/session_tag.py
        {"iso_utc": "...", "hour_utc": 12, "session": "LON_NY_OL"}

        $ python3 tools/session_tag.py 23
        ASIA
    """
    argv = sys.argv[1:]

    if not argv:
        info = classify_now_utc()
        print(json.dumps(info, ensure_ascii=False))
        return 0

    # Single integer hour
    try:
        h = int(argv[0])
    except ValueError:
        print("OFF")
        return 0

    print(session_for_hour(h))
    return 0


if __name__ == "__main__":
    sys.exit(main())
