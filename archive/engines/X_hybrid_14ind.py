#!/usr/bin/env python3
"""
X_hybrid_14ind.py

BotA – 14-indicator hybrid scoring engine with CONSERVATIVE / MODERATE modes.

- Reads ONE JSON object from stdin.
- Writes ONE JSON object to stdout.
- Never makes network calls.
- Fail-closed: on any error or bad data → HOLD, ok=False or weak=True.

Direction:
  - BUY  if adjusted_score >  2.0
  - SELL if adjusted_score < -2.0
  - HOLD otherwise

Total score:
  - total_score = clamp(abs(adjusted_score) * 4.0, 0..100)

Mode gates:
  - CONSERVATIVE: total_score >= 55 and signals >= 5 and no conflict and no quality_penalty
  - MODERATE:    total_score >= 40 and signals >= 3 and no conflict and no quality_penalty

Quality penalty NEVER increases score and can never flip a SELL into BUY.
"""

import json
import math
import sys
from typing import Any, Dict, List


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def clamp(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(max_value, value))


def safe_float(val: Any, default: float = 0.0) -> float:
    """Parse float safely, neutralising NaN/inf and bad types."""
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return default
        return f
    except Exception:
        return default


def safe_int(val: Any, default: int = 0) -> int:
    """Parse int safely."""
    try:
        return int(val)
    except Exception:
        return default


def _error_result(reason: str) -> Dict[str, Any]:
    """Standard error payload, always fail-closed as HOLD + weak."""
    return {
        "ok": False,
        "symbol": "",
        "tf": "M15",
        "mode": "CONSERVATIVE",
        "direction": "HOLD",
        "total_score": 0.0,
        "weak": True,
        "reason": reason,
        "notes": [],
        "indicators_used": [],
        "inputs": {},
    }


# ---------------------------------------------------------------------------
# Core scoring
# ---------------------------------------------------------------------------

def compute_indicator_scores(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compute raw_score, bull/bear counts, quality_penalty and diagnostics.

    This function does NOT choose BUY/SELL/HOLD; it only scores.
    """
    notes: List[str] = []
    indicators_used: List[str] = []

    ind = payload.get("indicators") or {}
    symbol = str(payload.get("symbol", "")).upper()
    tf = str(payload.get("tf", "M15")).upper()

    price = safe_float(ind.get("price"), 0.0)
    ema_fast = safe_float(ind.get("ema_fast"), price)
    ema_slow = safe_float(ind.get("ema_slow"), price)
    rsi = safe_float(ind.get("rsi"), 50.0)
    macd = safe_float(ind.get("macd"), 0.0)
    macd_signal = safe_float(ind.get("macd_signal"), 0.0)
    # SAFER: never derive from macd - macd_signal; default to 0.0
    macd_hist = safe_float(ind.get("macd_hist"), 0.0)
    adx = safe_float(ind.get("adx"), 0.0)
    di_plus = safe_float(ind.get("di_plus"), 0.0)
    di_minus = safe_float(ind.get("di_minus"), 0.0)
    stoch_k = safe_float(ind.get("stoch_k"), 50.0)
    stoch_d = safe_float(ind.get("stoch_d"), 50.0)
    atr_pips = safe_float(ind.get("atr_pips"), 0.0)
    if atr_pips < 0.0:
        atr_pips = 0.0
        notes.append("atr: negative value sanitised to 0.0")
    bb_pos = safe_float(ind.get("bb_pos"), 0.0)
    cci = safe_float(ind.get("cci"), 0.0)
    willr = safe_float(ind.get("willr"), -50.0)
    mfi = safe_float(ind.get("mfi"), 50.0)
    obv_slope = safe_float(ind.get("obv_slope"), 0.0)
    volume_rel = safe_float(ind.get("volume"), 1.0)

    rows = safe_int(payload.get("rows"), 0)
    age_min = safe_float(payload.get("age_min"), 9999.0)
    spread_pips = safe_float(payload.get("spread_pips"), 9999.0)

    raw_score = 0.0
    bull = 0
    bear = 0
    quality_penalty = 0.0

    pip_mul = 10000.0 if symbol.endswith("USD") else 100.0

    # 1) EMA trend -----------------------------------------------------------
    comp = 0.0
    ema_diff_pips = (ema_fast - ema_slow) * pip_mul
    if ema_diff_pips >= 10.0:
        comp = 12.0
        bull += 1
        notes.append(
            f"ema_trend: fast above slow by {ema_diff_pips:.1f} pips → strong bullish (+12)"
        )
    elif ema_diff_pips >= 4.0:
        comp = 8.0
        bull += 1
        notes.append(
            f"ema_trend: fast above slow by {ema_diff_pips:.1f} pips → bullish (+8)"
        )
    elif ema_diff_pips <= -10.0:
        comp = -12.0
        bear += 1
        notes.append(
            f"ema_trend: fast below slow by {ema_diff_pips:.1f} pips → strong bearish (-12)"
        )
    elif ema_diff_pips <= -4.0:
        comp = -8.0
        bear += 1
        notes.append(
            f"ema_trend: fast below slow by {ema_diff_pips:.1f} pips → bearish (-8)"
        )

    if comp != 0.0:
        raw_score += comp
        indicators_used.append("ema_trend")

    # 2) RSI block -----------------------------------------------------------
    comp = 0.0
    if 55.0 <= rsi <= 70.0:
        comp = 8.0
        bull += 1
        notes.append(f"rsi: {rsi:.1f} in bullish zone 55–70 (+8)")
    elif 30.0 <= rsi <= 45.0:
        comp = -8.0
        bear += 1
        notes.append(f"rsi: {rsi:.1f} in bearish zone 30–45 (-8)")
    elif rsi > 75.0:
        comp = 3.0
        bull += 1
        notes.append(f"rsi: {rsi:.1f} overbought >75 (late bullish, +3)")
    elif rsi < 25.0:
        comp = -3.0
        bear += 1
        notes.append(f"rsi: {rsi:.1f} oversold <25 (late bearish, -3)")

    if comp != 0.0:
        raw_score += comp
        indicators_used.append("rsi")

    # 3) MACD block ----------------------------------------------------------
    comp = 0.0
    macd_diff = macd - macd_signal
    if macd_diff > 0.0 and macd_hist > 0.0:
        comp = 6.0
        bull += 1
        notes.append("macd: line>signal and hist>0 → strong bullish (+6)")
    elif macd_diff > 0.0:
        comp = 3.0
        bull += 1
        notes.append("macd: line>signal → bullish (+3)")
    elif macd_diff < 0.0 and macd_hist < 0.0:
        comp = -6.0
        bear += 1
        notes.append("macd: line<signal and hist<0 → strong bearish (-6)")
    elif macd_diff < 0.0:
        comp = -3.0
        bear += 1
        notes.append("macd: line<signal → bearish (-3)")

    if comp != 0.0:
        raw_score += comp
        indicators_used.append("macd")

    # 4) ADX block -----------------------------------------------------------
    comp = 0.0
    if adx >= 40.0:
        comp = 6.0
        notes.append(f"adx: {adx:.1f} strong trend (+6)")
    elif adx >= 25.0:
        comp = 4.0
        notes.append(f"adx: {adx:.1f} trending (+4)")
    elif adx <= 15.0:
        comp = -3.0
        notes.append(f"adx: {adx:.1f} choppy (-3)")

    if comp != 0.0:
        raw_score += comp
        indicators_used.append("adx")

    # 5) DI+/DI- block -------------------------------------------------------
    comp = 0.0
    if di_plus > di_minus + 5.0:
        comp = 5.0
        bull += 1
        notes.append("di: DI+ > DI- +5 → bullish (+5)")
    elif di_minus > di_plus + 5.0:
        comp = -5.0
        bear += 1
        notes.append("di: DI- > DI+ +5 → bearish (-5)")

    if comp != 0.0:
        raw_score += comp
        indicators_used.append("di")

    # 6) Stochastic block ----------------------------------------------------
    comp = 0.0
    if stoch_k >= 80.0 and stoch_d >= 80.0:
        comp = -4.0
        bear += 1
        notes.append("stoch: overbought >=80 → bearish (-4)")
    elif stoch_k <= 20.0 and stoch_d <= 20.0:
        comp = 4.0
        bull += 1
        notes.append("stoch: oversold <=20 → bullish (+4)")
    elif stoch_k > stoch_d + 5.0 and 40.0 <= stoch_k <= 70.0:
        comp = 3.0
        bull += 1
        notes.append("stoch: bullish cross in mid-zone → bullish (+3)")
    elif stoch_d > stoch_k + 5.0 and 30.0 <= stoch_d <= 60.0:
        comp = -3.0
        bear += 1
        notes.append("stoch: bearish cross in mid-zone → bearish (-3)")

    if comp != 0.0:
        raw_score += comp
        indicators_used.append("stoch")

    # 7) ATR block -----------------------------------------------------------
    comp = 0.0
    if atr_pips >= 12.0:
        comp = 5.0
        notes.append(f"atr: {atr_pips:.1f} pips high volatility (+5)")
    elif atr_pips >= 6.0:
        comp = 3.0
        notes.append(f"atr: {atr_pips:.1f} pips moderate volatility (+3)")
    elif atr_pips <= 2.0:
        comp = -6.0
        notes.append(f"atr: {atr_pips:.1f} pips very low volatility (-6)")

    if comp != 0.0:
        raw_score += comp
        indicators_used.append("atr")

    # 8) Bollinger block -----------------------------------------------------
    comp = 0.0
    if bb_pos > 0.6:
        comp = 3.0
        bull += 1
        notes.append("bollinger: near upper band → bullish (+3)")
    elif bb_pos < -0.6:
        comp = -3.0
        bear += 1
        notes.append("bollinger: near lower band → bearish (-3)")

    if comp != 0.0:
        raw_score += comp
        indicators_used.append("bollinger")

    # 9) CCI block -----------------------------------------------------------
    comp = 0.0
    if cci >= 100.0:
        comp = 4.0
        bull += 1
        notes.append(f"cci: {cci:.1f} >= 100 → bullish (+4)")
    elif cci <= -100.0:
        comp = -4.0
        bear += 1
        notes.append(f"cci: {cci:.1f} <= -100 → bearish (-4)")

    if comp != 0.0:
        raw_score += comp
        indicators_used.append("cci")

    # 10) Williams %R block --------------------------------------------------
    comp = 0.0
    if willr >= -20.0:
        comp = -3.0
        bear += 1
        notes.append(f"willr: {willr:.1f} >= -20 (overbought) → bearish (-3)")
    elif willr <= -80.0:
        comp = 3.0
        bull += 1
        notes.append(f"willr: {willr:.1f} <= -80 (oversold) → bullish (+3)")

    if comp != 0.0:
        raw_score += comp
        indicators_used.append("willr")

    # 11) MFI block ----------------------------------------------------------
    comp = 0.0
    if mfi >= 70.0:
        comp = -3.0
        bear += 1
        notes.append(f"mfi: {mfi:.1f} >= 70 (high) → bearish (-3)")
    elif mfi <= 30.0:
        comp = 3.0
        bull += 1
        notes.append(f"mfi: {mfi:.1f} <= 30 (low) → bullish (+3)")

    if comp != 0.0:
        raw_score += comp
        indicators_used.append("mfi")

    # 12) OBV slope block ----------------------------------------------------
    comp = 0.0
    if obv_slope > 0.4:
        comp = 4.0
        bull += 1
        notes.append("obv: slope>0.4 → bullish (+4)")
    elif obv_slope < -0.4:
        comp = -4.0
        bear += 1
        notes.append("obv: slope<-0.4 → bearish (-4)")

    if comp != 0.0:
        raw_score += comp
        indicators_used.append("obv")

    # 13) Volume participation block ----------------------------------------
    comp = 0.0
    if volume_rel >= 1.5:
        comp = 4.0
        notes.append("volume: >=1.5× average → strong participation (+4)")
    elif volume_rel <= 0.6:
        comp = -4.0
        notes.append("volume: <=0.6× average → weak participation (-4)")

    if comp != 0.0:
        raw_score += comp
        indicators_used.append("volume")

    # 14) Data quality / risk block -----------------------------------------
    if rows < 30:
        quality_penalty += 8.0
        notes.append(f"quality: rows={rows} <30 → penalty +8")
    if age_min > 15.0:
        quality_penalty += 6.0
        notes.append(f"quality: age_min={age_min:.1f} >15 → penalty +6")
    if spread_pips > 3.0:
        quality_penalty += 5.0
        notes.append(f"quality: spread={spread_pips:.1f} >3.0 → penalty +5")

    return {
        "symbol": symbol,
        "tf": tf,
        "raw_score": raw_score,
        "bull": bull,
        "bear": bear,
        "quality_penalty": quality_penalty,
        "rows": rows,
        "age_min": age_min,
        "spread_pips": spread_pips,
        "notes": notes,
        "indicators_used": indicators_used,
        "inputs": {
            "price": price,
            "ema_fast": ema_fast,
            "ema_slow": ema_slow,
            "rsi": rsi,
            "macd": macd,
            "macd_signal": macd_signal,
            "macd_hist": macd_hist,
            "adx": adx,
            "di_plus": di_plus,
            "di_minus": di_minus,
            "stoch_k": stoch_k,
            "stoch_d": stoch_d,
            "atr_pips": atr_pips,
            "bb_pos": bb_pos,
            "cci": cci,
            "willr": willr,
            "mfi": mfi,
            "obv_slope": obv_slope,
            "volume_rel": volume_rel,
        },
    }


def decide_direction(scoring: Dict[str, Any], mode: str) -> Dict[str, Any]:
    """
    Apply penalties and mode thresholds to get final direction + score.

    - quality_penalty always shrinks raw_score magnitude (never flips sign or
      increases it).
    """
    raw_score = float(scoring["raw_score"])
    bull = int(scoring["bull"])
    bear = int(scoring["bear"])
    quality_penalty = float(scoring["quality_penalty"])
    notes = list(scoring["notes"])
    indicators_used = list(scoring["indicators_used"])

    conflict = bull > 0 and bear > 0
    if conflict:
        conflict_penalty = min(20.0, 4.0 * float(min(bull, bear)))
        notes.append(
            f"conflict: bull={bull}, bear={bear} → conflict_penalty={conflict_penalty:.1f}"
        )
    else:
        conflict_penalty = 0.0

    # Apply penalties – always shrink magnitude, never flip sign.
    score_adj = raw_score

    total_penalty = quality_penalty + conflict_penalty
    if total_penalty > 0.0:
        mag = max(0.0, abs(score_adj) - total_penalty)
        score_adj = math.copysign(mag, score_adj) if score_adj != 0.0 else 0.0
        notes.append(
            f"penalties: quality={quality_penalty:.1f}, conflict={conflict_penalty:.1f} → adjusted_score={score_adj:.1f}"
        )

    direction = "HOLD"
    if score_adj > 2.0:
        direction = "BUY"
    elif score_adj < -2.0:
        direction = "SELL"

    magnitude = abs(score_adj)
    total_score = clamp(magnitude * 4.0, 0.0, 100.0)

    weak = True
    sig_count = bull + bear

    if direction != "HOLD":
        if mode == "CONSERVATIVE":
            base_thresh = 55.0
            min_signals = 5
        else:  # MODERATE (and any other mode treated as MODERATE)
            base_thresh = 40.0
            min_signals = 3

        if (
            total_score >= base_thresh
            and sig_count >= min_signals
            and not conflict
            and quality_penalty <= 0.0
        ):
            weak = False

    reason = (
        f"mode={mode} raw_score={raw_score:.1f} adj_score={score_adj:.1f} "
        f"bull={bull} bear={bear} quality_penalty={quality_penalty:.1f} "
        f"conflict_penalty={conflict_penalty:.1f} sig_count={sig_count}"
    )

    return {
        "ok": True,
        "symbol": scoring["symbol"],
        "tf": scoring["tf"],
        "mode": mode,
        "direction": direction,
        "total_score": float(f"{total_score:.4f}"),
        "weak": weak,
        "reason": reason,
        "notes": notes,
        "indicators_used": indicators_used,
        "inputs": scoring["inputs"],
    }


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------

def main() -> int:
    raw = sys.stdin.read()
    if not raw or not raw.strip():
        err = _error_result("empty_stdin_payload")
        print(json.dumps(err, separators=(",", ":")))
        return 0

    try:
        payload = json.loads(raw)
    except Exception as e:
        err = _error_result(f"json_parse_error:{e}")
        print(json.dumps(err, separators=(",", ":")))
        return 0

    if not isinstance(payload, dict):
        err = _error_result("payload_not_object")
        print(json.dumps(err, separators=(",", ":")))
        return 0

    if "tf" not in payload:
        payload["tf"] = "M15"
    if "mode" not in payload:
        payload["mode"] = "CONSERVATIVE"

    mode_in = str(payload.get("mode", "CONSERVATIVE")).upper()
    if mode_in.startswith("C"):
        mode = "CONSERVATIVE"
    else:
        mode = "MODERATE"

    scoring = compute_indicator_scores(payload)
    result = decide_direction(scoring, mode)
    print(json.dumps(result, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
