#!/usr/bin/env python3
"""
tools/status_cmd.py

Heartbeat utility for BotA.

- No deprecated naive-UTC usage.
- Works both as:
    python -m tools.status_cmd --heartbeat "..."
  and:
    python tools/status_cmd.py --heartbeat "..."
"""

import os
import sys
import time
import datetime as dt

# Import that works in both module and script execution modes.
try:
    from .tg_utils import send_message  # module mode: python -m tools.status_cmd
except Exception:
    # script mode: python tools/status_cmd.py
    import pathlib

    ROOT = pathlib.Path(__file__).resolve().parents[1]
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from tools.tg_utils import send_message  # type: ignore

COOLDOWN_MIN = int(os.getenv("HEARTBEAT_COOLDOWN_MIN", "55"))
STATE = os.path.expanduser("~/BotA/.state")
os.makedirs(STATE, exist_ok=True)
STAMP = os.path.join(STATE, "heartbeat.stamp")

UTC = getattr(dt, "UTC", dt.timezone.utc)


def _utc_hm_str() -> str:
    # Preserve EXACT prior format: YYYY-mm-dd HH:MM (UTC label is appended in msg)
    return dt.datetime.now(UTC).strftime("%Y-%m-%d %H:%M")


def ok_to_send() -> bool:
    try:
        st = os.stat(STAMP)
        age = time.time() - st.st_mtime
        return age >= COOLDOWN_MIN * 60
    except Exception:
        return True


def mark_sent() -> None:
    try:
        with open(STAMP, "w", encoding="utf-8") as f:
            f.write(str(time.time()))
    except Exception:
        pass


def heartbeat(reason: str) -> None:
    if not ok_to_send():
        print("[HB] suppressed (cooldown active).")
        return

    msg = f"🤖 BotA heartbeat • {_utc_hm_str()} UTC • reason={reason}"
    ok = send_message(msg)
    mark_sent()
    print(f"Heartbeat sent to Telegram, ok={ok}")


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--heartbeat", default="")
    args = ap.parse_args()
    if args.heartbeat:
        heartbeat(args.heartbeat)


if __name__ == "__main__":
    main()
