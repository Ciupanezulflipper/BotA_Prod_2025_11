#!/usr/bin/env python3
from __future__ import annotations
import sys, json
from datetime import datetime, timezone

BIAS_EMOJI = {"BULLISH":"🟢", "BEARISH":"🔴", "NEUTRAL":"⚪"}

def vis_pair(p: str) -> str:
    return p if "/" in p else (p[:3]+"/"+p[3:] if len(p)==6 else p)

def fmt_item(it: dict) -> str:
    pair = vis_pair(it.get("pair","PAIR"))
    weighted = it.get("weighted",0)
    bias = str(it.get("bias","NEUTRAL")).upper()
    emoji = BIAS_EMOJI.get(bias, "⚪")
    reason = it.get("reason","threshold")
    strength = it.get("strength", 0)
    an = it.get("analytics", {})
    D1 = an.get("D1", {})
    H4 = an.get("H4", {})
    H1 = an.get("H1", {})
    divs = []
    for tf in ("D1","H4","H1"):
        d = an.get(tf,{}).get("div_rsi","none")
        if d != "none":
            divs.append(f"{tf}:{d}")
    div_txt = ("  • div(" + ", ".join(divs) + ")") if divs else ""
    return (f"{emoji} <b>{pair}</b>  w=<b>{weighted}</b>  bias=<b>{bias}</b>  "
            f"<i>{reason}</i>  S={strength:.2f}{div_txt}")

def main() -> int:
    raw = sys.stdin.read()
    try:
        arr = json.loads(raw) if raw.strip() else []
    except Exception:
        arr = []
    if not arr:
        print("BotA — no actionable alerts.")
        return 0
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    lines = [fmt_item(it) for it in arr]
    msg = "📣 <b>BotA Alerts</b>\n" + ts + "\n\n" + "\n".join(lines)
    print(msg)
    return 0

if __name__ == "__main__":
    sys.exit(main())
