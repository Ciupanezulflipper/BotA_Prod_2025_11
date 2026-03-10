#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import sys
from typing import Dict, List, Optional, Tuple

ROOT = os.path.expanduser("~/BotA")
CACHE_DIR = os.path.join(ROOT, "cache")
LOGS_DIR = os.path.join(ROOT, "logs")
SCALPER_LOG = os.path.join(LOGS_DIR, "signal_history.csv")

# --- UTC helpers (timezone-aware; avoids datetime.utcnow() DeprecationWarning) ---
UTC = getattr(dt, "UTC", dt.timezone.utc)


def _utc_now() -> dt.datetime:
    return dt.datetime.now(UTC)


# Try to import session_tag if available (hybrid mode: we never hard-block on session here)
SESSION_DEFAULT = "UNKNOWN"
try:
    sys.path.append(os.path.join(ROOT, "tools"))
    from session_tag import tag_hour  # type: ignore
except Exception:
    tag_hour = None  # type: ignore


def _safe_float(d: Dict, *keys: str) -> Optional[float]:
    """Return first available key as float, or None."""
    for k in keys:
        if k in d and d[k] is not None:
            try:
                return float(d[k])
            except (TypeError, ValueError):
                continue
    return None


def load_htf_snapshot(pair: str, tf: str) -> Dict:
    """Load a simple indicator snapshot for a given symbol/timeframe from JSON.

    We are conservative: if the file is missing or malformed, we fall back to neutral.
    Expected file pattern (best-effort): cache/{PAIR}_{TF}.json
    """
    fname = os.path.join(CACHE_DIR, f"{pair.upper()}_{tf}.json")
    try:
        with open(fname, "r", encoding="utf-8") as fh:
            return json.load(fh) or {}
    except FileNotFoundError:
        return {}
    except Exception:
        return {}


def vote_from_snapshot(snap: Dict) -> int:
    """Compute a single timeframe vote from EMA/RSI/MACD snapshot.

    +1 bullish, -1 bearish, 0 neutral/not enough info.
    """
    ema9 = _safe_float(snap, "ema9", "EMA9")
    ema21 = _safe_float(snap, "ema21", "EMA21")
    rsi14 = _safe_float(snap, "rsi14", "RSI14")
    macd = _safe_float(snap, "macd_hist", "MACD_hist", "macd")

    if ema9 is None or ema21 is None:
        return 0

    ema_v = 1 if ema9 > ema21 else -1 if ema9 < ema21 else 0
    rsi_v = 1 if (rsi14 is not None and rsi14 > 55) else -1 if (rsi14 is not None and rsi14 < 45) else 0
    macd_v = 1 if (macd is not None and macd > 0) else -1 if (macd is not None and macd < 0) else 0

    s = ema_v + rsi_v + macd_v
    if s > 0:
        return 1
    if s < 0:
        return -1
    return 0


def compute_htf_votes(pair: str) -> Tuple[int, int, int, int, str]:
    """Return (h1_vote, h4_vote, d1_vote, weighted, base_bias).

    Weighted = H1*1 + H4*2 + D1*3, base_bias from weighted.
    """
    h1_snap = load_htf_snapshot(pair, "H1")
    h4_snap = load_htf_snapshot(pair, "H4")
    d1_snap = load_htf_snapshot(pair, "D1")

    h1 = vote_from_snapshot(h1_snap)
    h4 = vote_from_snapshot(h4_snap)
    d1 = vote_from_snapshot(d1_snap)

    weighted = h1 * 1 + h4 * 2 + d1 * 3

    if weighted >= 3:
        base_bias = "BUY"
    elif weighted <= -3:
        base_bias = "SELL"
    else:
        base_bias = "NEUTRAL"

    return h1, h4, d1, weighted, base_bias


def parse_scalper_row(row: List[str]) -> Optional[Dict]:
    """Parse a row from signal_history.csv.

    Expected loose format:
      timestamp,pair,decision,score,weak,provider,...,price,...

    We are defensive and accept partial rows.
    """
    if len(row) < 4:
        return None

    ts_raw = row[0].strip()
    pair = row[1].strip().upper()
    decision = row[2].strip().upper()
    score_raw = row[3].strip()

    if decision not in ("BUY", "SELL"):
        return None

    try:
        score = float(score_raw)
    except ValueError:
        return None

    # Parse ISO8601 with optional trailing 'Z'
    ts: Optional[dt.datetime] = None
    try:
        if ts_raw.endswith("Z"):
            # keep same clock time, but mark as UTC
            ts = dt.datetime.fromisoformat(ts_raw[:-1]).replace(tzinfo=UTC)
        else:
            ts = dt.datetime.fromisoformat(ts_raw)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=UTC)
            else:
                ts = ts.astimezone(UTC)
    except Exception:
        ts = None

    return {
        "ts": ts,
        "pair": pair,
        "decision": decision,
        "score": score,
    }


def load_last_scalper_signal(pair: str) -> Optional[Dict]:
    """Load the most recent scalper signal for a given pair from signal_history.csv.

    Returns dict with keys: ts, pair, decision, score, age_min.
    If file missing or no valid row, returns None.
    """
    pair = pair.upper()
    try:
        with open(SCALPER_LOG, "r", encoding="utf-8") as fh:
            rows = list(csv.reader(fh))
    except FileNotFoundError:
        return None
    except Exception:
        return None

    last: Optional[Dict] = None
    for row in rows:
        parsed = parse_scalper_row(row)
        if not parsed:
            continue
        if parsed["pair"] != pair:
            continue
        last = parsed

    if not last:
        return None

    now = _utc_now()
    ts = last.get("ts")
    if isinstance(ts, dt.datetime):
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)
        else:
            ts = ts.astimezone(UTC)
        age_min = (now - ts).total_seconds() / 60.0
        last["ts"] = ts
    else:
        age_min = None

    last["age_min"] = age_min
    return last


def decide_final_bias(
    pair: str,
    htf_weighted: int,
    base_bias: str,
    scalper: Optional[Dict],
    min_scalper_score: float,
    max_scalper_age_min: float,
) -> Tuple[int, str, str, Optional[Dict]]:
    """Combine HTF bias with optional scalper signal.

    Returns (final_weighted, final_bias, source, scalper_used).
    """
    # Default: HTF only
    final_w = htf_weighted
    final_bias = base_bias
    source = "HTF_ONLY"
    used_scalper: Optional[Dict] = None

    if not scalper:
        return final_w, final_bias, source, used_scalper

    score = scalper.get("score")
    age_min = scalper.get("age_min")
    decision = scalper.get("decision")

    if score is None or decision not in ("BUY", "SELL"):
        return final_w, final_bias, source, used_scalper

    if score < min_scalper_score:
        return final_w, final_bias, source, used_scalper

    if (age_min is not None) and (age_min > max_scalper_age_min):
        return final_w, final_bias, source, used_scalper

    dir_sign = 1 if decision == "BUY" else -1

    # Case 1: HTF neutral, scalper strong → SCALPER_ONLY with canonical |w| = 3
    if -2 <= htf_weighted <= 2:
        final_w = 3 * dir_sign
        final_bias = decision
        source = "SCALPER_ONLY"
        used_scalper = scalper
        return final_w, final_bias, source, used_scalper

    # Case 2: HTF and scalper in same direction → HYBRID, boost weight modestly
    if (htf_weighted * dir_sign) > 0:
        final_w = htf_weighted + 2 * dir_sign
        if final_w >= 3:
            final_bias = "BUY"
        elif final_w <= -3:
            final_bias = "SELL"
        else:
            final_bias = "NEUTRAL"
        source = "HYBRID"
        used_scalper = scalper
        return final_w, final_bias, source, used_scalper

    # Case 3: Conflict (scalper vs HTF) → ignore scalper for now, HTF_ONLY
    return final_w, final_bias, source, used_scalper


def current_session(ignore_session: bool) -> str:
    if ignore_session:
        return SESSION_DEFAULT
    if tag_hour is None:
        return SESSION_DEFAULT
    try:
        now = _utc_now()
        return tag_hour(now.hour)
    except Exception:
        return SESSION_DEFAULT


def main() -> int:
    ap = argparse.ArgumentParser(description="BotA early watch — HTF + scalper hybrid bias")
    ap.add_argument("--pairs", help="Space or comma separated list, e.g. 'EURUSD GBPUSD'")
    ap.add_argument("--ignore-session", action="store_true", help="Ignore session logic (hybrid mode)")
    args = ap.parse_args()

    # Pairs from CLI, env PAIRS or default
    if args.pairs:
        raw_pairs = args.pairs.replace(",", " ")
    else:
        raw_pairs = os.getenv("PAIRS", "EURUSD GBPUSD").replace(",", " ")
    pairs = [p.strip().upper() for p in raw_pairs.split() if p.strip()]

    min_scalper_score = float(os.getenv("SCALPER_MIN_SCORE", "50"))
    max_scalper_age_min = float(os.getenv("SCALPER_MAX_AGE_MIN", "15"))

    sess = current_session(ignore_session=args.ignore_session)

    for pair in pairs:
        h1, h4, d1, w, base_bias = compute_htf_votes(pair)
        print(f"[early_watch] {pair}: HTF votes H1={h1} H4={h4} D1={d1} w={w} base_bias={base_bias}")

        scalper = load_last_scalper_signal(pair)
        if scalper is None:
            print(f"[early_watch] {pair}: no recent scalper signal (or below thresholds)")
        else:
            age_str = f"{scalper['age_min']:.1f}m" if isinstance(scalper.get("age_min"), (int, float)) else "NA"
            print(f"[early_watch] {pair}: scalper {scalper['decision']} score={scalper['score']:.1f} age={age_str}")

        final_w, final_bias, source, used_scalper = decide_final_bias(
            pair=pair,
            htf_weighted=w,
            base_bias=base_bias,
            scalper=scalper,
            min_scalper_score=min_scalper_score,
            max_scalper_age_min=max_scalper_age_min,
        )

        print(f"[early_watch] {pair} weighted={final_w} bias={final_bias} source={source} session={sess}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
