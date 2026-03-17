#!/usr/bin/env python3
"""
Apply Bollinger Bands scoring patch to scoring_engine.sh
Run: python3 tools/patch_bb_scoring.py
"""
import sys
from pathlib import Path

TARGET = Path(__file__).parent / "scoring_engine.sh"

OLD = '''                base = 40.0
                score = base + ema_comp + rsi_comp + macd_comp + adx_comp'''

NEW = '''                # 5. Bollinger Bands component (volatility + price position)
                bb_upper  = sf(ind.get("bb_upper", 0.0))
                bb_middle = sf(ind.get("bb_middle", 0.0))
                bb_lower  = sf(ind.get("bb_lower", 0.0))
                bb_squeeze = bool(ind.get("bb_squeeze", False))

                bb_comp = 0.0
                bb_tag = "bb_neutral"
                if bb_upper > 0 and bb_lower > 0 and bb_middle > 0:
                    if bb_squeeze:
                        bb_comp = -10.0
                        bb_tag = "bb_squeeze"
                    elif direction == "SELL" and price >= bb_upper * 0.9998:
                        bb_comp = 8.0
                        bb_tag = "bb_upper_sell"
                    elif direction == "BUY" and price <= bb_lower * 1.0002:
                        bb_comp = 8.0
                        bb_tag = "bb_lower_buy"
                    elif direction == "SELL" and price > bb_middle:
                        bb_comp = 3.0
                        bb_tag = "bb_above_mid_sell"
                    elif direction == "BUY" and price < bb_middle:
                        bb_comp = 3.0
                        bb_tag = "bb_below_mid_buy"
                    else:
                        bb_comp = -5.0
                        bb_tag = "bb_counter"

                base = 40.0
                score = base + ema_comp + rsi_comp + macd_comp + adx_comp + bb_comp'''

OLD_REASONS = '''                reasons.extend([
                    "ok",
                    f"ema_bps={ema_delta_bps:.1f}",
                    f"rsi={rsi:.1f}",
                    f"macd_hist={macd_hist:.6f}",
                    f"adx={adx:.1f}",
                    f"ema_comp={ema_comp:.1f}",
                    f"rsi_comp={rsi_comp:.1f}",
                    f"macd_comp={macd_comp:.1f}",
                    f"adx_comp={adx_comp:.1f}",
                    f"phase={phase}"
                ])'''

NEW_REASONS = '''                reasons.extend([
                    "ok",
                    f"ema_bps={ema_delta_bps:.1f}",
                    f"rsi={rsi:.1f}",
                    f"macd_hist={macd_hist:.6f}",
                    f"adx={adx:.1f}",
                    f"ema_comp={ema_comp:.1f}",
                    f"rsi_comp={rsi_comp:.1f}",
                    f"macd_comp={macd_comp:.1f}",
                    f"adx_comp={adx_comp:.1f}",
                    f"bb_comp={bb_comp:.1f}",
                    f"bb={bb_tag}",
                    f"phase={phase}"
                ])'''

text = TARGET.read_text(encoding="utf-8")

if OLD not in text:
    print(f"ERROR: scoring patch target not found in {TARGET}")
    print("The file may have changed. Check manually.")
    sys.exit(1)

if OLD_REASONS not in text:
    print(f"ERROR: reasons patch target not found in {TARGET}")
    sys.exit(1)

text = text.replace(OLD, NEW, 1)
text = text.replace(OLD_REASONS, NEW_REASONS, 1)

TARGET.write_text(text, encoding="utf-8")
print(f"✅ BB scoring patch applied to {TARGET}")
print("Verify with: grep -n 'bb_comp\\|bb_tag\\|bb_squeeze' tools/scoring_engine.sh")

