#!/usr/bin/env python3
import sys
import json
import math
import os
from datetime import datetime, timezone

# --- Configurable Input Size Limit -------------------------------

# Read max JSON input size (in KB) from environment, default 256 KB
_MAX_INPUT_KB = int(os.environ.get("MAX_SIGNAL_KB", "256"))
_MAX_INPUT_BYTES = _MAX_INPUT_KB * 1024

# --- Helper Functions (Environment & Data Safety) --------------------------

def _read_stdin_json():
    """Read a single JSON object from stdin, up to a safe limit. On failure or over-size, return {}."""
    try:
        data = sys.stdin.read(_MAX_INPUT_BYTES)
        # If we hit the limit, try to read more to detect oversize
        if len(data) == _MAX_INPUT_BYTES:
            extra = sys.stdin.read(1)
            if extra:
                # Input too large — treat as malformed
                return {}
        if not data or not data.strip():
            return {}
        return json.loads(data)
    except Exception:
        return {}

def _env_flag(name: str, default: bool) -> bool:
    val = os.environ.get(name, "").strip().lower()
    if val in ("1", "true", "yes", "y", "on"):
        return True
    if val in ("0", "false", "no", "n", "off"):
        return False
    return default

def _env_int(name: str, default: int) -> int:
    val = os.environ.get(name, "").strip()
    if not val:
        return default
    try:
        return int(val)
    except ValueError:
        return default

def _env_float(name: str, default: float) -> float:
    val = os.environ.get(name, "").strip()
    if not val:
        return default
    try:
        return float(val)
    except ValueError:
        return default

def _safe_float(val, default: float = 0.0) -> float:
    try:
        if val is None:
            return default
        f = float(val)
        if math.isnan(f) or math.isinf(f) or abs(f) > 1e12:
            return default
        return f
    except Exception:
        return default

def _iso_utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00","Z")

# --- Core Logic ------------------------------------------------------------

def decide(entry: dict) -> dict:
    dry_run_mode = _env_flag("DRY_RUN_MODE", True)
    smart_min_score = _env_int("SMART_MIN_SCORE", 55)
    smart_full_score = _env_int("SMART_FULL_SCORE", 65)
    max_age_min = _env_float("SMART_MAX_AGE_MIN", 10.0)
    max_spread_pips = _env_float("SMART_MAX_SPREAD_PIPS", 2.0)

    age_fail_default = max_age_min + 1.0
    spread_fail_default = max_spread_pips + 1.0

    pair = str(entry.get("pair", "UNKNOWN") or "UNKNOWN")
    side = str(entry.get("side", "HOLD") or "HOLD").upper()
    base_bias = str(entry.get("base_bias", "UNKNOWN") or "UNKNOWN")
    provider = str(entry.get("provider", "unknown") or "unknown")

    score = _safe_float(entry.get("score"), 0.0)

    age_raw = entry.get("age_min", None)
    spread_raw = entry.get("spread_pips", None)

    age_provided = "age_min" in entry and age_raw is not None
    spread_provided = "spread_pips" in entry and spread_raw is not None

    age_min_val = None
    spread_pips_val = None

    if age_provided:
        age_min_val = _safe_float(age_raw, age_fail_default)
    if spread_provided:
        spread_pips_val = _safe_float(spread_raw, spread_fail_default)

    ts = _iso_utc_now()

    if score < 0.0 or score > 100.0:
        score = 0.0

    accepted = True
    reason = "ok"

    if side == "HOLD" or score <= 0.0:
        reason = "no_trade(HOLD_or_zero_score)"
        accepted = False
    elif score < float(smart_min_score):
        reason = f"score_lt_min({score:.0f}<{smart_min_score})"
        accepted = False
    elif age_provided and age_min_val is not None and age_min_val > max_age_min:
        reason = f"too_old({age_min_val:.1f}>{max_age_min:.1f}min)"
        accepted = False
    elif spread_provided and spread_pips_val is not None and spread_pips_val > max_spread_pips:
        reason = f"spread_too_wide({spread_pips_val:.1f}>{max_spread_pips:.1f}pips)"
        accepted = False

    out_age_min = float(age_min_val) if age_min_val is not None and age_provided else None
    out_spread_pips = float(spread_pips_val) if spread_pips_val is not None and spread_provided else None

    out = {
        "accepted": bool(accepted),
        "reason": reason,
        "smart_entry": {
            "accepted": bool(accepted),
            "reason": reason,
            "score": float(score),
            "min_score": int(smart_min_score),
            "full_score": int(smart_full_score),
            "age_min": out_age_min,
            "max_age_min": float(max_age_min),
            "spread_pips": out_spread_pips,
            "max_spread_pips": float(max_spread_pips),
            "side": side,
            "pair": pair,
            "base_bias": base_bias,
            "provider": provider,
            "dry_run": bool(dry_run_mode),
            "ts": ts,
        },
    }
    return out

def main() -> int:
    entry = _read_stdin_json()
    dry_run = _env_flag("DRY_RUN_MODE", True)
    smart_min_score = _env_int("SMART_MIN_SCORE", 55)
    smart_full_score = _env_int("SMART_FULL_SCORE", 65)
    max_age_min = _env_float("SMART_MAX_AGE_MIN", 10.0)
    max_spread_pips = _env_float("SMART_MAX_SPREAD_PIPS", 2.0)

    if not entry:
        result = {
            "accepted": False,
            "reason": "invalid_input",
            "smart_entry": {
                "accepted": False,
                "reason": "invalid_input",
                "score": 0.0,
                "min_score": smart_min_score,
                "full_score": smart_full_score,
                "age_min": None,
                "max_age_min": max_age_min,
                "spread_pips": None,
                "max_spread_pips": max_spread_pips,
                "side": "HOLD",
                "pair": "UNKNOWN",
                "base_bias": "UNKNOWN",
                "provider": "unknown",
                "dry_run": dry_run,
                "ts": _iso_utc_now(),
            },
        }
    else:
        result = decide(entry)

    json.dump(result, sys.stdout, separators=(",", ":"), ensure_ascii=False)
    sys.stdout.write("\n")
    sys.stdout.flush()
    return 0

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as e:
        print(f"FATAL PYTHON ERROR: {e}", file=sys.stderr)
        raise SystemExit(1)
