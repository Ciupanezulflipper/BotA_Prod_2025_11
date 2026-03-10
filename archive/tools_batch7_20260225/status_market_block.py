#!/usr/bin/env python3
import os, subprocess
V2 = os.path.expanduser('~/bot-a/tools/market_block_v2.py')
def render_market_block() -> str:
    try:
        out = subprocess.check_output(["python3", V2], text=True).strip()
        return out
    except Exception as e:
        return f"Forex: <b>UNKNOWN</b>\n(error: {e})"
if __name__ == "__main__":
    print(render_market_block())
