# BotA/tools/scoring_v2.py
# Full replacement. Provides EnhancedScorer used by runner_confluence.

from __future__ import annotations

import math
from typing import Dict, List, Tuple

class EnhancedScorer:
    """
    Scores the indicator bundle from indicators_ext.analyze_indicators().
    Outputs:
      - action: 'BUY' | 'SELL' | 'WAIT'
      - score16: technical points (0..16)
      - score6: risk/news points (0..6)
      - reason: short human text for PRD card
    """

    def __init__(self):
        # Tech thresholds
        self.min_adx_trend = 20.0
        self.strong_adx = 25.0
        self.atr_ratio_max = 0.0025  # ~0.25%
        self.rsi_buy = 35.0
        self.rsi_sell = 65.0
        # Risk weights (sum capped to 6)
        self.risk_items = [
            ("ATR ok", 1),
            ("No spike", 1),
            ("S/R clear", 1),
            ("News pass", 1),
            ("Trend coherence", 1),
            ("Momentum coherence", 1),
        ]

    # ---------- helpers ----------

    @staticmethod
    def _sgn(x: float) -> int:
        return 1 if x > 0 else (-1 if x < 0 else 0)

    def _trend_bias(self, bundle: Dict) -> int:
        # Use EMA50 slope and MACD delta to infer bias
        ema50 = float(bundle.get("ema50_slope", 0.0))
        macd_delta = float(bundle.get("macd", {}).get("delta", 0.0))
        bias = 0
        bias += self._sgn(ema50)
        bias += self._sgn(macd_delta)
        # clamp to -1..1
        return 1 if bias > 0 else (-1 if bias < 0 else 0)

    # ---------- scoring ----------

    def score(self, bundle: Dict) -> Dict:
        """
        bundle: dict from analyze_indicators()
        returns dict(action, score16, score6, reason)
        """
        reasons: List[str] = []
        tech = 0
        risk = 0

        rsi = float(bundle.get("rsi", float("nan")))
        adx = float(bundle.get("adx", float("nan")))
        macd = bundle.get("macd", {}) or {}
        macd_delta = float(macd.get("delta", 0.0))
        macd_hist = float(macd.get("hist", 0.0))
        ema50_slope = float(bundle.get("ema50_slope", 0.0))
        ema200_slope = float(bundle.get("ema200_slope", 0.0))
        atr = float(bundle.get("atr", 0.0))
        atr_ratio = float(bundle.get("atr_ratio", 0.0))
        spike_ok = bool(bundle.get("spike_ok", True))
        fib_near = bool(bundle.get("fib_near", False))
        sr_clear = bool(bundle.get("sr_clear", True))
        news_pass = bool(bundle.get("news_pass", True))

        # --- technical (target 0..16) ---
        # 1) Trend presence via ADX
        if not math.isnan(adx) and adx >= self.min_adx_trend:
            tech += 1
            reasons.append("ADX trend present")
        if not math.isnan(adx) and adx >= self.strong_adx:
            tech += 1  # extra point for stronger trend

        # 2) EMA slopes
        if ema50_slope > 0:
            tech += 1
            reasons.append("EMA50 slope up")
        elif ema50_slope < 0:
            tech += 1
            reasons.append("EMA50 slope down")
        if ema200_slope > 0:
            tech += 1
        elif ema200_slope < 0:
            tech += 1

        # 3) Momentum (MACD)
        if macd_delta > 0:
            tech += 1
            reasons.append("MACD momentum up")
        elif macd_delta < 0:
            tech += 1
            reasons.append("MACD momentum down")
        # histogram magnitude confirmation
        if abs(macd_hist) > 1e-6:
            tech += 1

        # 4) RSI context
        if not math.isnan(rsi):
            if rsi <= self.rsi_buy:
                tech += 1
                reasons.append("RSI oversold zone")
            elif rsi >= self.rsi_sell:
                tech += 1
                reasons.append("RSI overbought zone")

        # 5) Fibonacci proximity
        if fib_near:
            tech += 1
            reasons.append("Near Fibonacci level")

        # 6) S/R cleanliness
        if sr_clear:
            tech += 1
            reasons.append("No nearby S/R clutter")

        # 7) Volatility sanity (ATR ratio not too high)
        if atr_ratio > 0 and atr_ratio < self.atr_ratio_max:
            tech += 1

        # 8) Spike filter
        if spike_ok:
            tech += 1

        # cap to 16
        tech = min(tech, 16)

        # --- risk/news (target 0..6) ---
        if atr_ratio > 0 and atr_ratio < self.atr_ratio_max:
            risk += 1
        if spike_ok:
            risk += 1
        if sr_clear:
            risk += 1
        if news_pass:
            risk += 1

        # coherence items
        trend_bias = self._trend_bias(bundle)
        if trend_bias != 0:
            risk += 1
            reasons.append("Trend aligned" if trend_bias > 0 else "Trend down")
        if self._sgn(macd_delta) == trend_bias and trend_bias != 0:
            risk += 1
            reasons.append("Momentum aligned")

        risk = min(risk, 6)

        # --- action decision ---
        # Default WAIT, require enough confluence AND decent risk quality
        action = "WAIT"
        if tech >= 12 and risk >= 4:
            action = "BUY" if trend_bias > 0 else ("SELL" if trend_bias < 0 else "WAIT")
        elif tech >= 9 and risk >= 5:
            action = "BUY" if trend_bias > 0 else ("SELL" if trend_bias < 0 else "WAIT")

        # craft concise reason line
        reason_line = " + ".join(dict.fromkeys(reasons)) if reasons else "Confluence mixed"

        return {
            "action": action,
            "score16": int(tech),
            "score6": int(risk),
            "reason": reason_line,
        }

# convenience function if caller prefers functional API
def score(bundle: Dict) -> Dict:
    return EnhancedScorer().score(bundle)
