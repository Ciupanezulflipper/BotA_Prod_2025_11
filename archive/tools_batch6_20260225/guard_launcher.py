#!/usr/bin/env python3
"""
guard_launcher.py
- Runs the Weekend/Holiday Guard first.
- If ALLOW → forwards all args to runner_confluence.py unchanged.
- If BLOCKED → cleanly exits after printing a one-line status (no send).
- Works with your current layout: ~/bot-a/tools
"""

import subprocess, sys, json, os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"

GUARD = TOOLS / "weekend_guard.py"
RUNNER = TOOLS / "runner_confluence.py"   # your existing runner

def run_guard() -> dict:
    """Return guard JSON (or minimal BLOCKED on error)."""
    try:
        p = subprocess.run(
            ["python3", str(GUARD), "--json"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
        out = p.stdout.strip()
        # If guard script printed plain text (not JSON), fall back
        if not out.startswith("{"):
            return {"allow": p.returncode == 0, "reason": out, "until_open_h": None, "until_open_m": None}
        return json.loads(out)
    except Exception as e:
        # If anything odd happens, be safe and block
        return {"allow": False, "reason": f"Guard error: {e}", "until_open_h": None, "until_open_m": None}

def main():
    g = run_guard()
    if not g.get("allow", False):
        reason = g.get("reason", "Guard BLOCKED")
        hh = g.get("until_open_h")
        mm = g.get("until_open_m")
        countdown = f" | next open in {hh}h {mm:02d}m" if hh is not None and mm is not None else ""
        print(f"[GUARD] BLOCKED: {reason}{countdown}")
        sys.exit(0)  # Not an error; just a controlled skip

    # Allowed → forward to your runner with original CLI args
    cmd = ["python3", str(RUNNER), *sys.argv[1:]]
    sys.exit(subprocess.call(cmd))

if __name__ == "__main__":
    main()
