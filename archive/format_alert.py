#!/usr/bin/env python3
from __future__ import annotations

import sys
import json
from typing import List, Dict, Any


def _tier_prefix(tier: str) -> str:
    t = (tier or "").lower()
    if t == "trade":
        return "🟢 TRADE"
    if t == "watch":
        return "⚪ WATCH"
    return "⚪ WATCH"


def _bias_emoji(bias: str) -> str:
    b = (bias or "").upper()
    if b == "BUY":
        return "📈"
    if b == "SELL":
        return "📉"
    return "➖"


def format_item(it: Dict[str, Any]) -> str:
    pair = it.get("pair", "?")
    bias = (it.get("bias") or "UNKNOWN").upper()
    source = (it.get("source") or "UNKNOWN").upper()
    session = (it.get("session") or "UNKNOWN").upper()
    tier = it.get("tier", "watch")
    reason = it.get("reason", "status")

    w = int(it.get("weighted", 0) or 0)
    strength = float(it.get("strength", abs(w)))
    preferred_tf = it.get("preferred_tf", "H1")

    prefix = _tier_prefix(tier)
    dir_emoji = _bias_emoji(bias)

    # Line 1: compact summary
    line1 = (
        f"{prefix} {dir_emoji} {pair} "
        f"w={w} S={strength:.1f} "
        f"src={source} tf={preferred_tf} sess={session}"
    )

    # Line 2: bias + tier semantics
    if tier == "trade":
        tier_note = "✅ candidate trade (meets RULEBOOK)"
    else:
        tier_note = "👀 watch-only (no auto-trade)"

    line2 = f"• Bias: {bias} — {tier_note}"

    # Line 3: reason / tags (short but useful for debugging)
    line3 = f"• Reason: {reason}"

    return "\n".join([line1, line2, line3])


def main() -> int:
    raw = sys.stdin.read().strip()
    if not raw:
        print("No alerts.")
        return 0
    try:
        data = json.loads(raw)
        if not isinstance(data, list):
            data = []
    except Exception:
        data = []

    if not data:
        print("No alerts.")
        return 0

    lines: List[str] = []
    for it in data:
        try:
            lines.append(format_item(it))
        except Exception as e:
            # Fail-soft on a single bad item
            lines.append(f"⚠️ format_error for {it.get('pair','?')}: {e}")

    # Telegram message = all items separated by blank line
    msg = "\n\n".join(lines)
    sys.stdout.write(msg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
