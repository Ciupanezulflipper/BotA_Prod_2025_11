#!/usr/bin/env python3
"""
BotA Fusion Decider – Option B hardened, FINAL v3.0

Fail-closed safety gate for real-money trading.

Contract (Option A):
- Top-level JSON keys: exactly 4
    - accepted: bool
    - decision: "BUY" | "SELL" | "WAIT"
    - reason: str
    - fusion: object
- fusion contains exactly 11 keys:
    - pair: str
    - side: "BUY" | "SELL" | "WAIT"
    - session: str
    - session_group: "MAIN" | "ASIA"
    - fused_score: float (0–100)
    - min_fused: float
    - move_pips: float
    - min_move_pips: float
    - base_score: float
    - macro_score: float
    - lowvol_score: float

Safety goals:
- No acceptance leaks: malformed / conflicting / threshold-violating input
  MUST yield accepted=false and decision="WAIT".
- All exits (normal, error, exception) MUST emit a valid Option A JSON
  with newline-terminated output and flush().
"""

import sys
import json
import math
import os
import traceback
from typing import Any, Dict, List


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------


def _is_finite(value: Any) -> bool:
    """Return True if value can be safely converted to a finite float."""
    try:
        f = float(value)
    except Exception:
        return False
    return math.isfinite(f)


def _safe_float(value: Any, default: float = 0.0) -> float:
    """
    Safely convert value to a finite float.

    - On any error, NaN, or Inf, return default.
    """
    try:
        f = float(value)
    except Exception:
        return float(default)
    if not math.isfinite(f):
        return float(default)
    return f


def _env_int(name: str, default: int, min_val: int, max_val: int) -> int:
    """
    Read an int from the environment with range clamping and safe fallback.

    If env var is missing, invalid, or outside [min_val, max_val],
    return default.
    """
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return int(default)
    try:
        val = int(raw)
    except Exception:
        return int(default)
    if val < min_val or val > max_val:
        return int(default)
    return val


def _env_float(name: str, default: float, min_val: float, max_val: float) -> float:
    """
    Read a float from the environment with range clamping and safe fallback.

    If env var is missing, invalid, NaN/Inf, or outside [min_val, max_val],
    return default.
    """
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return float(default)
    try:
        val = float(raw)
    except Exception:
        return float(default)
    if not math.isfinite(val):
        return float(default)
    if min_val is not None and val < min_val:
        return float(default)
    if max_val is not None and val > max_val:
        return float(default)
    return val


def _normalize_side(value: Any) -> str:
    """
    Normalize side to "BUY", "SELL", or "".

    Non-string or unknown values become "".
    """
    if value is None:
        return ""
    s = str(value).strip().upper()
    if s in ("BUY", "SELL"):
        return s
    return ""


def _detect_session_group(session: str) -> str:
    """
    Detect session group from session string.

    - If "asia" appears in lowercased session → "ASIA"
    - Otherwise → "MAIN"
    """
    s = (session or "").lower()
    if "asia" in s:
        return "ASIA"
    return "MAIN"


# Numeric conflict fields: lower-key / upper-key pairs.
_NUMERIC_FIELDS = [
    ("base_score", "BASE_SCORE"),
    ("score_macro", "SCORE_MACRO"),
    ("score_lowvol", "SCORE_LOWVOL"),
    ("move_pips", "MOVE_PIPS"),
]


def _detect_conflicts(entry: Dict[str, Any], reasons: List[str]) -> bool:
    """
    Detect numeric conflicts between lower/upper key variants.

    For each pair (lower, UPPER) in _NUMERIC_FIELDS:
    - If both are present and differ by more than 1e-6, record
      "conflicting_keys:<lower>" and mark as fatal.

    Returns True if any fatal conflict is found.
    """
    fatal = False
    for lower, upper in _NUMERIC_FIELDS:
        lo_present = lower in entry
        up_present = upper in entry
        if not (lo_present and up_present):
            continue

        lo_val = _safe_float(entry.get(lower), 0.0)
        up_val = _safe_float(entry.get(upper), 0.0)
        if abs(lo_val - up_val) > 1e-6:
            reasons.append(f"conflicting_keys:{lower}")
            fatal = True
    return fatal


def _read_stdin_json() -> Dict[str, Any]:
    """
    Read and parse JSON from stdin with size and format safeguards.

    Env:
      MAX_FUSION_KB (int, 1–1024, default=256)

    On error, returns:
      {"_error": "<reason>"}
    """
    max_kb = _env_int("MAX_FUSION_KB", 256, 1, 1024)
    limit = max_kb * 1024

    try:
        data = sys.stdin.buffer.read(limit + 1)
    except Exception:
        return {"_error": "read_failed"}

    if not data:
        return {"_error": "empty_input"}

    if len(data) > limit:
        return {"_error": f"input_size_exceeded_{max_kb}KB"}

    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return {"_error": "invalid_utf8"}

    text = text.strip()
    if text == "":
        return {"_error": "empty_input"}

    try:
        obj = json.loads(text)
    except Exception:
        return {"_error": "invalid_json"}

    if not isinstance(obj, dict):
        return {"_error": "root_not_object"}

    return obj


def _build_result(
    accepted: bool,
    decision: str,
    reason: str,
    fused_payload: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Construct the final Option A output object (4 + 11 keys).

    - Sanitizes decision to BUY/SELL/WAIT (default WAIT).
    - Normalizes side; invalid values become "WAIT".
    - Enforces MAIN/ASIA for session_group.
    - Ensures all numeric fields are finite floats.
    - Clamps fused_score to [0.0, 100.0].
    """
    # Decision safety net
    if decision not in ("BUY", "SELL", "WAIT"):
        decision = "WAIT"

    # Pair
    pair = str(fused_payload.get("pair", ""))

    # Side normalization
    raw_side = fused_payload.get("side", "")
    side = _normalize_side(raw_side)
    if side not in ("BUY", "SELL"):
        side = "WAIT"

    # Session
    session = str(fused_payload.get("session", ""))

    # Session group
    session_group = fused_payload.get("session_group", "MAIN")
    if session_group not in ("MAIN", "ASIA"):
        session_group = "MAIN"

    # Numeric fields
    fused_score = _safe_float(fused_payload.get("fused_score", 0.0), 0.0)
    min_fused = _safe_float(fused_payload.get("min_fused", 60.0), 60.0)
    move_pips = _safe_float(fused_payload.get("move_pips", 0.0), 0.0)
    min_move_pips = _safe_float(fused_payload.get("min_move_pips", 5.0), 5.0)
    base_score = _safe_float(fused_payload.get("base_score", 0.0), 0.0)
    macro_score = _safe_float(fused_payload.get("macro_score", 0.0), 0.0)
    lowvol_score = _safe_float(fused_payload.get("lowvol_score", 0.0), 0.0)

    # Clamp fused_score to [0, 100]
    if fused_score < 0.0:
        fused_score = 0.0
    if fused_score > 100.0:
        fused_score = 100.0

    fusion = {
        "pair": pair,
        "side": side,
        "session": session,
        "session_group": session_group,
        "fused_score": fused_score,
        "min_fused": min_fused,
        "move_pips": move_pips,
        "min_move_pips": min_move_pips,
        "base_score": base_score,
        "macro_score": macro_score,
        "lowvol_score": lowvol_score,
    }

    return {
        "accepted": bool(accepted),
        "decision": decision,
        "reason": str(reason),
        "fusion": fusion,
    }


# ---------------------------------------------------------------------------
# Main fusion decision logic
# ---------------------------------------------------------------------------


def main() -> None:
    """
    Main entry: read JSON from stdin, apply fusion logic, emit Option A JSON.

    Fail-closed policy:
      - Start with accepted=True.
      - Any anomaly or failed gate sets accepted=False.
      - Final decision is:
          - BUY/SELL if accepted=True
          - WAIT if accepted=False
    """
    obj = _read_stdin_json()

    # Handle input-level errors early
    if "_error" in obj:
        reason = f"input_error:{obj.get('_error', 'unknown')}"
        result = _build_result(False, "WAIT", reason, {})
        sys.stdout.write(json.dumps(result, separators=(",", ":")) + "\n")
        sys.stdout.flush()
        return

    reasons: List[str] = []
    accepted = True

    # SmartEntry gate
    smart_entry_raw = obj.get("smart_entry", None)
    if not isinstance(smart_entry_raw, dict):
        accepted = False
        reasons.append("smart_entry_rejected:missing_or_not_object")
    else:
        se_accepted = bool(smart_entry_raw.get("accepted", False))
        se_reason = smart_entry_raw.get("reason")
        if not se_accepted:
            accepted = False
            # Preserve reason if provided, else mark generic
            suffix = str(se_reason) if se_reason not in (None, "") else "no_reason"
            reasons.append(f"smart_entry_rejected:{suffix}")

    # Missing required fields (includes smart_entry)
    missing: List[str] = []
    for f in (
        "pair",
        "side",
        "session",
        "base_score",
        "score_macro",
        "score_lowvol",
        "move_pips",
        "smart_entry",
    ):
        if f not in obj:
            missing.append(f)
    if missing:
        accepted = False
        missing_str = ",".join(sorted(missing))
        reasons.append(f"missing_required_fields:{missing_str}")

    # Numeric conflicts – fatal if any
    if _detect_conflicts(obj, reasons):
        accepted = False
        reasons.append("fatal_conflict")

    # Normalize basic fields
    pair_raw = obj.get("pair", "")
    pair = str(pair_raw) if pair_raw is not None else ""

    side_raw = obj.get("side", "")
    side = _normalize_side(side_raw)

    session_raw = obj.get("session", "")
    session = str(session_raw) if session_raw is not None else ""
    session_group = _detect_session_group(session)

    # Scores and move
    base_score = _safe_float(obj.get("base_score", 0.0), 0.0)
    score_macro = _safe_float(obj.get("score_macro", 0.0), 0.0)
    score_lowvol = _safe_float(obj.get("score_lowvol", 0.0), 0.0)
    move_pips = _safe_float(obj.get("move_pips", 0.0), 0.0)

    # Compute fused_score and clamp to [0, 100]
    fused_score = base_score + score_macro + score_lowvol
    if fused_score < 0.0:
        fused_score = 0.0
    if fused_score > 100.0:
        fused_score = 100.0

    # Thresholds with env guarding
    if session_group == "ASIA":
        min_fused = _env_float("FUSION_MIN_FUSED_ASIA", 70.0, 30.0, 100.0)
        min_move = _env_float("FUSION_MIN_MOVE_ASIA", 8.0, 1.0, 1000.0)
    else:
        session_group = "MAIN"
        min_fused = _env_float("FUSION_MIN_FUSED_MAIN", 60.0, 30.0, 100.0)
        min_move = _env_float("FUSION_MIN_MOVE_MAIN", 5.0, 1.0, 1000.0)

    # Side validation
    if side not in ("BUY", "SELL"):
        accepted = False
        reasons.append(f"invalid_side:{side or 'missing'}")

    # Fused score threshold
    if fused_score < min_fused:
        accepted = False
        reasons.append(
            f"fused_score_below_min({fused_score:.1f}<{min_fused:.1f})"
        )

    # Move pips threshold
    if move_pips < min_move:
        accepted = False
        reasons.append(
            f"move_pips_below_min({move_pips:.1f}<{min_move:.1f})"
        )

    # Build fused payload for _build_result
    fused_payload: Dict[str, Any] = {
        "pair": pair,
        "side": side if side in ("BUY", "SELL") else "WAIT",
        "session": session,
        "session_group": session_group,
        "fused_score": fused_score,
        "min_fused": min_fused,
        "move_pips": move_pips,
        "min_move_pips": min_move,
        "base_score": base_score,
        "macro_score": score_macro,
        "lowvol_score": score_lowvol,
    }

    # Final decision and reason
    if accepted:
        decision = side  # "BUY" or "SELL"
        final_reason = "fusion_passed_all_checks"
    else:
        decision = "WAIT"
        final_reason = ";".join(reasons) if reasons else "rejected"

    result = _build_result(accepted, decision, final_reason, fused_payload)
    sys.stdout.write(json.dumps(result, separators=(",", ":")) + "\n")
    sys.stdout.flush()


# ---------------------------------------------------------------------------
# Top-level entry with hardened exception fallback (Option B + MAIN-safe A)
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # Primary exception handler – log and emit safe MAIN-default JSON
        traceback.print_exc(file=sys.stderr)

        safe_payload: Dict[str, Any] = {
            "pair": "",
            "side": "WAIT",
            "session": "",
            "session_group": "MAIN",
            "fused_score": 0.0,
            "min_fused": 60.0,
            "move_pips": 0.0,
            "min_move_pips": 5.0,
            "base_score": 0.0,
            "macro_score": 0.0,
            "lowvol_score": 0.0,
        }
        fallback = _build_result(False, "WAIT", "exception", safe_payload)

        try:
            sys.stdout.write(
                json.dumps(fallback, separators=(",", ":")) + "\n"
            )
            sys.stdout.flush()
        except Exception:
            # Catastrophic fallback: hard-coded MAIN-safe Option A JSON
            try:
                sys.stdout.write(
                    '{"accepted":false,'
                    '"decision":"WAIT",'
                    '"reason":"exception_fallback",'
                    '"fusion":{'
                    '"pair":"",'
                    '"side":"WAIT",'
                    '"session":"",'
                    '"session_group":"MAIN",'
                    '"fused_score":0.0,'
                    '"min_fused":60.0,'
                    '"move_pips":0.0,'
                    '"min_move_pips":5.0,'
                    '"base_score":0.0,'
                    '"macro_score":0.0,'
                    '"lowvol_score":0.0'
                    '}}\n'
                )
                sys.stdout.flush()
            except Exception:
                # If even this fails, caller must treat as hard failure.
                pass
