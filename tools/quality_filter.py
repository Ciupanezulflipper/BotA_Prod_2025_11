#!/usr/bin/env python3
"""
tools/quality_filter.py

ROLE:
- Normalize + filter scoring_engine JSON into a stable contract for downstream scripts.
- Hard rejection ONLY on:
  1) direction not BUY/SELL
  2) score below TF-aware minimum
  3) entry invalid (<=0)
- SL/TP/RR/ATR/volatility are ADVISORY (filter_reasons) unless direction/score/entry fail.

OPTION A (RR):
- Default RR min is set to 1.66 so ATRx(1.5/2.5) => RR≈1.667 does NOT emit rr<... by default.
- You can override with env FILTER_RR_MIN.
"""

from __future__ import annotations

import json
import math
import os
import re
import signal
import sys
from typing import Any, Dict, List, Tuple


def log(msg: str) -> None:
    try:
        sys.stderr.write(f"[QUALITY] {msg}\n")
        sys.stderr.flush()
    except Exception:
        pass


def safe_float(v: Any, default: float = 0.0) -> float:
    try:
        f = float(v)
        if math.isnan(f) or math.isinf(f):
            return default
        return f
    except Exception:
        return default


def clean_float(v: Any, default: float = 0.0, precision: int = 5) -> float:
    f = safe_float(v, default)
    try:
        return float(f"{f:.{precision}f}")
    except Exception:
        return default


def _is_scalp_tf(tf: str) -> bool:
    tfu = (tf or "").upper()
    return bool(re.fullmatch(r"M(1|2|3|4|5|10|15|20|30)", tfu))


def _resolve_score_threshold(tf: str) -> float:
    tfu = (tf or "").upper()
    if os.environ.get("FILTER_SCORE_MIN_ALL"):
        return safe_float(os.environ.get("FILTER_SCORE_MIN_ALL"), 60.0)
    key = f"FILTER_SCORE_MIN_{tfu}"
    if os.environ.get(key):
        return safe_float(os.environ.get(key), 60.0)
    if tfu.startswith("M"):
        return 60.0
    if tfu.startswith("H"):
        return 60.0
    if tfu in ("D1", "1D"):
        return 70.0
    return 60.0


def compute_rr(direction: str, entry: float, sl: float, tp: float) -> float:
    d = (direction or "").upper()
    if entry <= 0.0 or sl <= 0.0 or tp <= 0.0:
        return 0.0
    if d == "BUY":
        risk = entry - sl
        reward = tp - entry
    elif d == "SELL":
        risk = sl - entry
        reward = entry - tp
    else:
        return 0.0
    if risk <= 0.0 or reward <= 0.0:
        return 0.0
    return reward / risk


def parse_atr_from_reasons(reasons: str) -> float:
    if not reasons:
        return 0.0
    m = re.search(r"\batr\s*=\s*([0-9]*\.?[0-9]+)\b", reasons, flags=re.IGNORECASE)
    if not m:
        return 0.0
    return safe_float(m.group(1), 0.0)


def _auto_fill_sl_tp(direction: str, entry: float, atr: float, sl: float, tp: float) -> Tuple[float, float, str]:
    d = (direction or "").upper()
    if entry <= 0.0 or atr <= 0.0:
        return sl, tp, ""
    try:
        scalp_sl_mult = float(os.environ.get("SCALP_SL_ATR_MULT", "1.5"))
    except Exception:
        scalp_sl_mult = 1.5
    try:
        scalp_tp_mult = float(os.environ.get("SCALP_TP_ATR_MULT", "2.5"))
    except Exception:
        scalp_tp_mult = 2.5
    sl_out = sl
    tp_out = tp
    if sl_out <= 0.0 or tp_out <= 0.0:
        if d == "BUY":
            sl_out = entry - scalp_sl_mult * atr
            tp_out = entry + scalp_tp_mult * atr
        elif d == "SELL":
            sl_out = entry + scalp_sl_mult * atr
            tp_out = entry - scalp_tp_mult * atr
        else:
            return sl, tp, ""
    if sl_out > 0.0 and tp_out > 0.0 and sl_out != tp_out:
        rec = f"sl_tp_rec=SL:{sl_out:.5f},TP:{tp_out:.5f},ATRx({scalp_sl_mult:.1f}/{scalp_tp_mult:.1f})"
        return sl_out, tp_out, rec
    return sl, tp, ""


def fallback_invalid(reason: str) -> Dict[str, Any]:
    return {
        "pair": "UNKNOWN", "tf": "UNKNOWN", "direction": "HOLD",
        "entry": 0.0, "sl": 0.0, "tp": 0.0, "volatility": "unknown",
        "score": 0.0, "confidence": 0.0, "reasons": reason, "price": 0.0,
        "provider": "quality_filter", "atr": 0.0, "filter_rr": 0.0,
        "filter_atr": 0.0, "filter_rejected": True,
        "filter_reasons": ["fail_closed"], "pattern_delta": 0,
    }


def apply_filters(data: Dict[str, Any]) -> Dict[str, Any]:
    pair = str(data.get("pair", "UNKNOWN"))
    tf = str(data.get("tf", data.get("timeframe", "UNKNOWN")))
    direction = str(data.get("direction", "HOLD")).upper()
    price = safe_float(data.get("price", 0.0), 0.0)
    score = safe_float(data.get("score", 0.0), 0.0)
    confidence = safe_float(data.get("confidence", 0.0), 0.0)
    volatility = str(data.get("volatility", "unknown"))
    reasons = str(data.get("reasons", ""))
    entry = safe_float(data.get("entry", 0.0), 0.0)
    sl = safe_float(data.get("sl", 0.0), 0.0)
    tp = safe_float(data.get("tp", 0.0), 0.0)
    provider = str(data.get("provider", "engine_A2"))
    atr = safe_float(data.get("atr", 0.0), 0.0)
    if atr <= 0.0:
        atr = parse_atr_from_reasons(reasons)

    filter_reasons: List[str] = []
    gating_flags: List[str] = []

    # 1) Direction hard gate
    if direction not in ("BUY", "SELL"):
        filter_reasons.append("direction_not_tradeable")
        gating_flags.append("direction_not_tradeable")

    # 2) Score hard gate
    score_min = _resolve_score_threshold(tf)
    if score < score_min:
        filter_reasons.append(f"score<{int(score_min)}")
        gating_flags.append("score_below_min")

    # 3) Entry hard gate
    if entry <= 0.0:
        filter_reasons.append("entry_invalid_zero")
        gating_flags.append("entry_invalid_zero")

    # 4) Advisory auto-fill SL/TP for scalp TF
    sl_tp_rec_str = ""
    if _is_scalp_tf(tf) and direction in ("BUY", "SELL") and entry > 0.0:
        sl, tp, sl_tp_rec_str = _auto_fill_sl_tp(direction, entry, atr, sl, tp)
    if sl_tp_rec_str:
        reasons = (reasons + " | " + sl_tp_rec_str) if reasons else sl_tp_rec_str

    # 5) Advisory SL/TP completeness
    if entry > 0.0 and (sl <= 0.0 or tp <= 0.0):
        filter_reasons.append("missing_sl_tp_entry")

    # 6) Advisory RR
    rr = compute_rr(direction, entry, sl, tp)
    if rr <= 0.0:
        filter_reasons.append("rr<=0")
    else:
        default_rr_min = 1.66
        try:
            rr_min = float(os.environ.get("FILTER_RR_MIN", default_rr_min))
        except Exception:
            rr_min = default_rr_min
        if rr + 1e-9 < rr_min:
            filter_reasons.append(f"rr<{rr_min:.2f}")

    # 7) Advisory ATR/volatility
    if atr <= 0.0:
        filter_reasons.append("atr<=0")
    if volatility == "unknown":
        filter_reasons.append("volatility_unknown")

    # 8) Extended-move suppression
    extended_mult = safe_float(os.environ.get("EXTENDED_MOVE_ATR_MULT", "0"), 0.0)
    if extended_mult > 0.0 and atr > 0.0 and entry > 0.0 and sl > 0.0:
        if direction == "BUY":
            move = entry - sl
        elif direction == "SELL":
            move = sl - entry
        else:
            move = 0.0
        if move > extended_mult * atr:
            filter_reasons.append(
                f"extended_move={move:.5f}>{extended_mult:.1f}x_atr={atr:.5f}"
            )
            if os.environ.get("EXTENDED_MOVE_HARD_REJECT", "0") == "1":
                gating_flags.append("extended_move")

    # 9) Trend alignment penalty
    trend_penalty = safe_float(os.environ.get("TREND_OPPOSITE_PENALTY", "0.85"), 0.85)
    if "H1_trend_opposite" in reasons:
        old_score = score
        score = score * trend_penalty
        filter_reasons.append(f"trend_opposite_penalty={old_score:.1f}->{score:.1f}")
        log(f"trend_opposite_penalty applied: {old_score:.1f} -> {score:.1f}")
        if score < score_min:
            gating_flags.append("score_below_min_after_trend_penalty")
            filter_reasons.append(f"score<{int(score_min)}_after_trend_penalty")


    # Hard rejection ONLY from gating_flags
    filter_rejected = bool(gating_flags)

    out: Dict[str, Any] = dict(data)
    out["pair"] = pair
    out["tf"] = tf
    out["direction"] = direction
    out["entry"] = clean_float(entry, 0.0, precision=5)
    out["sl"] = clean_float(sl, 0.0, precision=5)
    out["tp"] = clean_float(tp, 0.0, precision=5)
    out["volatility"] = volatility
    out["score"] = clean_float(score, 0.0, precision=2)
    out["confidence"] = clean_float(confidence, 0.0, precision=2)
    out["price"] = clean_float(price, 0.0, precision=5)
    out["provider"] = provider
    out["reasons"] = reasons
    out["filter_rr"] = clean_float(rr, 0.0, precision=3)
    out["filter_atr"] = clean_float(atr, 0.0, precision=8)
    out["filter_rejected"] = filter_rejected
    out["filter_reasons"] = filter_reasons
    return out


def main() -> None:
    try:
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    except Exception:
        pass
    raw = sys.stdin.read()
    if not raw or not raw.strip():
        obj = fallback_invalid("empty input JSON for quality_filter")
        try:
            sys.stdout.write(json.dumps(obj, separators=(",", ":")))
        except BrokenPipeError:
            return
        return
    try:
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("input JSON must be an object")
    except Exception as e:
        obj = fallback_invalid(f"invalid JSON: {e}")
        try:
            sys.stdout.write(json.dumps(obj, separators=(",", ":")))
        except BrokenPipeError:
            return
        return
    out = apply_filters(data)
    try:
        sys.stdout.write(json.dumps(out, separators=(",", ":")))
    except BrokenPipeError:
        return


if __name__ == "__main__":
    main()
