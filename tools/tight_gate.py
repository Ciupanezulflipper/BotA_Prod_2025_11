#!/usr/bin/env python3
import os, subprocess, sys
def spread_ok():
    try:
        r = subprocess.run(
            ["python3", os.path.expanduser("~/bot-a/tools/spread_guard.py")],
            capture_output=True, text=True
        )
        return (r.returncode == 0, r.stdout.strip())
    except Exception as e:
        return (False, f"spread_guard error: {e}")
def gate_or_reason():
    ok,msg = spread_ok()
    if not ok:
        return False, f"spread-block: {msg}"
    return True, ""
if __name__ == "__main__":
    ok, why = gate_or_reason()
    print("OK" if ok else f"BLOCK {why}")
    sys.exit(0 if ok else 2)
