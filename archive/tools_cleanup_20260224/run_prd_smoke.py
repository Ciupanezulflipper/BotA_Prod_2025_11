#!/usr/bin/env python3
import os, sys
from datetime import datetime, timezone

PAIR = os.getenv("PAIR","EURUSD")
TF   = os.getenv("TF","M15")

def prd_card(action, score_base="0/16", score_bonus="0/6", reason="Runner error or no data", risk="network/providers", spread="N/A"):
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    icon = {"BUY":"✅ BUY","SELL":"❌ SELL","WAIT":"⏸️ WAIT"}.get(action,"⏸️ WAIT")
    print(f"📊 {PAIR} ({TF})\n"
          f"🕒 Signal Time: {now}\n"
          f"📈 Action: {icon}\n"
          f"📊 Score: {score_base} + {score_bonus}\n"
          f"🧠 Reason: {reason}\n"
          f"⚠️ Risk: {risk}\n"
          f"📉 Spread: {spread}")

def main():
    # Try to use your runner if it’s importable; otherwise emit a WAIT card.
    try:
        import importlib, types
        spec = importlib.util.find_spec("tools.runner_confluence")
        if not spec:
            prd_card("WAIT", reason="runner not importable")
            return 0
        mod = importlib.import_module("tools.runner_confluence")
        run_once = getattr(mod, "run_once", None)
        if not isinstance(run_once, types.FunctionType):
            prd_card("WAIT", reason="run_once missing")
            return 0

        line = run_once(pair=PAIR, tf=TF, force=True, dry_run=True, prd_card=True)
        if not isinstance(line, str) or not line.strip():
            prd_card("WAIT", reason="empty output")
            return 0

        # If runner already prints a full PRD card, just print it; if it prints a compact line, wrap it.
        if line.strip().startswith("📊"):
            print(line)
        else:
            prd_card("WAIT", reason=line.strip())
        return 0
    except Exception as e:
        prd_card("WAIT", reason=str(e)[:180])
        return 0

if __name__ == "__main__":
    sys.exit(main())
