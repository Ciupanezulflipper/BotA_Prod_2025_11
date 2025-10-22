#!/usr/bin/env python3
import argparse
import os
import subprocess
import sys
from weekend_guard import status as guard_status

# Default to EURUSD only, as requested
DEFAULT_PAIR = "EURUSD"
DEFAULT_TF   = "M15"

def main():
    ap = argparse.ArgumentParser(description="Run analyzer only when FX is open.")
    ap.add_argument("--pair", default=DEFAULT_PAIR)
    ap.add_argument("--tf", default=DEFAULT_TF)
    ap.add_argument("--dry-run", action="store_true", help="Run analyzer without sending.")
    ap.add_argument("--force", action="store_true", help="Bypass market guard.")
    args, passthru = ap.parse_known_args()

    st = guard_status()
    if st.closed and not args.force:
        msg = f"[MARKET_GUARD] Blocked send: {st.reason}, opens in {st.hours_left:.2f}h"
        if st.next_open:
            msg += f" @ {st.next_open.isoformat()}"
        print(msg, flush=True)
        return 0

    cmd = [
        "python3",
        os.path.expanduser("~/bot-a/tools/runner_confluence.py"),
        "--pair", args.pair,
        "--tf", args.tf,
    ]
    if args.dry_run:
        cmd.append("--dry-run")
    else:
        cmd.append("--send")

    # pass any extra args downstream for flexibility
    cmd.extend(passthru)

    print(f"[MARKET_GUARD] Passing through to runner: {' '.join(cmd)}", flush=True)
    try:
        return subprocess.call(cmd)
    except FileNotFoundError:
        print("[ERROR] runner_confluence.py not found at ~/bot-a/tools/", file=sys.stderr)
        return 2

if __name__ == "__main__":
    sys.exit(main())
