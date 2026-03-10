# BotA — Timestamp Integrity Gate (Fail-Closed Primitive)
#
# Purpose (NON-NEGOTIABLE):
# - Verify that the *actual* candle interval (delta between last two CLOSED candles)
#   matches the requested timeframe (e.g., M15 = 900s).
# - If mismatch, FAIL (non-zero exit) so the caller can fail-closed (HOLD or SILENT).
#
# Constraints:
# - Deterministic, auditable, broker-agnostic
# - No “best effort”
# - No inference or aggregation
# - Safe with intermittent mobile data and schema variability
#
# Supported inputs:
# - OANDA v20 candles JSON: {"candles":[{"time": "...", "complete": true, ...}, ...]}
# - Twelve Data time_series JSON: {"values":[{"datetime":"...", ...}, ...]}
# - Generic list of dict candles:
#   - [{"timestamp": 1700000000, ...}, {"timestamp": 1700000900, ...}]
#   - [{"time":"2026-01-22T10:00:00Z", ...}, ...]
#
# Output modes:
# - default: exit code only
# - --json: print a minimal JSON verdict to stdout
#
# Exit codes:
# - 0  PASS
# - 2  FAIL (timeframe mismatch, incomplete data, parse error, etc.)
#
# Local self-test:
#   python3 tools/timestamp_integrity_gate.py --selftest
#
# Example usage (file input):
#   python3 tools/timestamp_integrity_gate.py --tf-min 15 --input /tmp/candles.json
#
# Example usage (stdin):
#   cat /tmp/candles.json | python3 tools/timestamp_integrity_gate.py --tf-min 15
#
# NOTE:
# - This file DOES NOT fetch data.
# - It only validates integrity of already-fetched JSON.

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class GateResult:
    ok: bool
    reason: str
    observed_delta_sec: Optional[int] = None
    expected_delta_sec: Optional[int] = None
    t1_epoch_sec: Optional[int] = None
    t2_epoch_sec: Optional[int] = None


def _stderr(msg: str) -> None:
    sys.stderr.write(msg.rstrip() + "\n")


def _parse_iso8601_to_epoch_seconds(s: str) -> Optional[int]:
    """
    Parse ISO8601 timestamps into epoch seconds (UTC).
    Accepts:
      - 2026-01-22T10:00:00Z
      - 2026-01-22T10:00:00+00:00
      - 2026-01-22 10:00:00  (treated as UTC, conservative)
    """
    if not isinstance(s, str) or not s.strip():
        return None

    raw = s.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"

    try:
        dt = datetime.fromisoformat(raw)
    except Exception:
        return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return int(dt.astimezone(timezone.utc).timestamp())


def _parse_timestamp_any(value: Any) -> Optional[int]:
    """
    Parse:
    - int/float epoch seconds
    - epoch milliseconds (heuristic: > 10^12)
    - ISO8601 strings
    - numeric strings
    """
    if value is None:
        return None

    if isinstance(value, (int, float)):
        if value > 1_000_000_000_000:
            return int(value / 1000)
        if value > 0:
            return int(value)
        return None

    if isinstance(value, str):
        iso = _parse_iso8601_to_epoch_seconds(value)
        if iso is not None:
            return iso
        try:
            num = float(value)
        except Exception:
            return None
        return _parse_timestamp_any(num)

    return None


def _extract_candles(obj: Any) -> List[Dict[str, Any]]:
    """
    Extract candle-like dicts from known schemas.
    """
    if isinstance(obj, dict):
        if isinstance(obj.get("candles"), list):
            return [c for c in obj["candles"] if isinstance(c, dict)]
        if isinstance(obj.get("values"), list):
            return [v for v in obj["values"] if isinstance(v, dict)]
        for key in ("data", "result", "items"):
            if isinstance(obj.get(key), list):
                arr = [x for x in obj[key] if isinstance(x, dict)]
                if arr:
                    return arr
        return []

    if isinstance(obj, list):
        return [c for c in obj if isinstance(c, dict)]

    return []


def _is_closed(c: Dict[str, Any]) -> bool:
    """
    OANDA: 'complete' == true means closed.
    If no flag exists, treat as closed (we cannot infer otherwise).
    """
    if "complete" in c:
        return c.get("complete") is True
    return True


def _get_time_epoch(c: Dict[str, Any]) -> Optional[int]:
    for k in ("time", "datetime", "timestamp", "t"):
        if k in c:
            return _parse_timestamp_any(c.get(k))
    return None


def _last_two_closed(candles: List[Dict[str, Any]]) -> Optional[Tuple[int, int]]:
    """
    Provider order is not trusted; sort by timestamp ascending.
    Returns (t1, t2) epoch seconds for last two closed candles.
    """
    items: List[int] = []
    for c in candles:
        if not isinstance(c, dict):
            continue
        if not _is_closed(c):
            continue
        ts = _get_time_epoch(c)
        if ts is None:
            continue
        items.append(ts)

    if len(items) < 2:
        return None

    items.sort()
    return items[-2], items[-1]


def validate_timeframe_delta(json_obj: Any, requested_tf_min: int, tolerance_sec: int) -> GateResult:
    if requested_tf_min <= 0:
        return GateResult(False, "invalid_requested_tf")

    expected = requested_tf_min * 60

    candles = _extract_candles(json_obj)
    if not candles:
        return GateResult(False, "no_candles_found", expected_delta_sec=expected)

    pair = _last_two_closed(candles)
    if pair is None:
        return GateResult(False, "insufficient_closed_candles", expected_delta_sec=expected)

    t1, t2 = pair
    if t2 <= t1:
        return GateResult(False, "non_monotonic_timestamps", expected_delta_sec=expected, t1_epoch_sec=t1, t2_epoch_sec=t2)

    observed = int(t2 - t1)

    if abs(observed - expected) > tolerance_sec:
        return GateResult(
            False,
            "tf_mismatch",
            observed_delta_sec=observed,
            expected_delta_sec=expected,
            t1_epoch_sec=t1,
            t2_epoch_sec=t2,
        )

    return GateResult(
        True,
        "ok",
        observed_delta_sec=observed,
        expected_delta_sec=expected,
        t1_epoch_sec=t1,
        t2_epoch_sec=t2,
    )


def _emit_json(r: GateResult) -> None:
    sys.stdout.write(
        json.dumps(
            {
                "ok": r.ok,
                "reason": r.reason,
                "observed_delta_sec": r.observed_delta_sec,
                "expected_delta_sec": r.expected_delta_sec,
                "t1_epoch_sec": r.t1_epoch_sec,
                "t2_epoch_sec": r.t2_epoch_sec,
            },
            separators=(",", ":"),
            ensure_ascii=False,
        )
        + "\n"
    )


def _load_input(path: Optional[str]) -> Any:
    if path:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    raw = sys.stdin.read()
    if not raw.strip():
        raise ValueError("empty_stdin")
    return json.loads(raw)


def _selftest() -> int:
    # PASS sample: exact M15 (900s)
    oanda_like = {
        "candles": [
            {"time": "2026-01-22T10:00:00Z", "complete": True},
            {"time": "2026-01-22T10:15:00Z", "complete": True},
        ]
    }
    r1 = validate_timeframe_delta(oanda_like, 15, tolerance_sec=5)
    if not r1.ok:
        _stderr("SELFTEST_FAIL: expected PASS for M15 sample")
        _emit_json(r1)
        return 2

    # FAIL sample: requested M15, observed H1 (3600s)
    td_like = {"values": [{"datetime": "2026-01-22 10:00:00"}, {"datetime": "2026-01-22 11:00:00"}]}
    r2 = validate_timeframe_delta(td_like, 15, tolerance_sec=5)
    if r2.ok or r2.reason != "tf_mismatch":
        _stderr("SELFTEST_FAIL: expected FAIL tf_mismatch for H1 sample")
        _emit_json(r2)
        return 2

    _stderr("SELFTEST_OK")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="BotA Timestamp Integrity Gate (timeframe delta validator)")
    p.add_argument("--tf-min", type=int, default=None, help="Requested timeframe in minutes (e.g., 15 for M15)")
    p.add_argument("--tolerance-sec", type=int, default=5, help="Allowed delta tolerance in seconds")
    p.add_argument("--input", type=str, default=None, help="Path to candles JSON file; if omitted reads stdin")
    p.add_argument("--json", action="store_true", help="Emit JSON verdict to stdout")
    p.add_argument("--selftest", action="store_true", help="Run internal self-test and exit")

    args = p.parse_args()

    if args.selftest:
        return _selftest()

    if args.tf_min is None:
        _stderr("FAIL: missing --tf-min")
        return 2

    try:
        obj = _load_input(args.input)
    except Exception as e:
        _stderr(f"FAIL: input_load_error: {type(e).__name__}")
        if args.json:
            _emit_json(GateResult(False, "input_load_error"))
        return 2

    r = validate_timeframe_delta(obj, args.tf_min, args.tolerance_sec)

    if args.json:
        _emit_json(r)

    if not r.ok:
        _stderr(f"FAIL: {r.reason} observed={r.observed_delta_sec} expected={r.expected_delta_sec}")
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
