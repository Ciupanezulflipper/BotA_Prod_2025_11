#!/usr/bin/env python3
"""
BotA — Session enricher (v2.2)

Reads a JSON array of alert candidates from stdin and attaches:
  - session: "ASIA" | "LONDON" | "LON_NY_OL" | "NEW_YORK" | "OFF"
  - hour_utc: integer 0..23

Session is derived from current UTC hour using tools/session_tag.py logic.
"""

from __future__ import annotations
import datetime as dt
import json
import os
import sys
from typing import List, Dict, Any

# Import session_for_hour from session_tag
ROOT = os.path.expanduser("~/BotA")
if ROOT not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, "tools"))

try:
    from session_tag import session_for_hour  # type: ignore
except Exception:
    # Defensive fallback: treat as OFF if helper missing
    def session_for_hour(hour_utc: int) -> str:  # type: ignore
        return "OFF"


def enrich_with_session(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Attach session + hour_utc to each alert candidate."""
    now = dt.datetime.now(dt.timezone.utc)
    h = now.hour
    sess = session_for_hour(h)
    out: List[Dict[str, Any]] = []
    for it in items:
        it2 = dict(it)
        it2.setdefault("hour_utc", h)
        it2.setdefault("session", sess)
        out.append(it2)
    return out


def main() -> int:
    raw = sys.stdin.read().strip()
    if not raw:
        print("[]")
        return 0
    try:
        arr = json.loads(raw)
        if not isinstance(arr, list):
            arr = []
    except Exception:
        arr = []
    enriched = enrich_with_session(arr)
    print(json.dumps(enriched, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
