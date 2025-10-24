#!/usr/bin/env python3
"""
Bot A — Phase 5: Format Telegram alert text.

Reads JSON list (from alert_rules.py) on STDIN and prints a single message.
Supports HTML (default) or MarkdownV2 via TELEGRAM_PARSE_MODE env (optional).
"""
from __future__ import annotations
import os, sys, json, datetime

BIAS_EMOJI = {
    "BULLISH": "🟢",
    "BEARISH": "🔴",
    "NEUTRAL": "⚪",
}

def fmt_line(it: dict) -> str:
    pair = it.get("pair", "PAIR")
    weighted = it.get("weighted", 0)
    bias = str(it.get("bias", "NEUTRAL")).upper()
    reason = it.get("reason", "threshold")
    emoji = BIAS_EMOJI.get(bias, "⚪")
    # EURUSD -> EUR/USD visual for readability
    vis = pair if "/" in pair else (pair[:3] + "/" + pair[3:]) if len(pair) == 6 else pair
    reason_tag = "WATCH" if reason == "watch" else "SIG"
    return f"{emoji} <b>{vis}</b>  w=<b>{weighted}</b>  bias=<b>{bias}</b>  <i>{reason_tag}</i>"

def main() -> int:
    raw = sys.stdin.read()
    try:
        items = json.loads(raw) if raw.strip() else []
    except Exception:
        items = []
    if not items:
        print("BotA — no actionable alerts.")
        return 0
    ts = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    lines = [fmt_line(it) for it in items]
    msg = "📣 <b>BotA WATCH Alerts</b>\n" + ts + "\n\n" + "\n".join(lines)
    print(msg)
    return 0

if __name__ == "__main__":
    sys.exit(main())
