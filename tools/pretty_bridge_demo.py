# FILE: tools/pretty_bridge_demo.py
# Optional helper for local testing without Telegram.
# Runs status_pretty.py and prints the BASIC/ADVANCED slices so you can confirm parsing.

import pathlib, sys, subprocess

BASE = pathlib.Path(__file__).resolve().parents[0]
STATUS_PRETTY = BASE / "status_pretty.py"

def run():
    p = subprocess.run([sys.executable, str(STATUS_PRETTY)], text=True, stdout=subprocess.PIPE)
    out = p.stdout.replace("\r\n","\n")
    basic = ""
    advanced = ""
    if "=== BASIC ===" in out:
        after_b = out.split("=== BASIC ===",1)[1]
        if "=== ADVANCED ===" in after_b:
            basic, advanced = after_b.split("=== ADVANCED ===",1)
        else:
            basic = after_b
    elif "=== ADVANCED ===" in out:
        advanced = out.split("=== ADVANCED ===",1)[1]
    else:
        basic = out
    print("----- BASIC -----")
    print(basic.strip())
    print("\n----- ADVANCED -----")
    print(advanced.strip())

if __name__ == "__main__":
    run()
