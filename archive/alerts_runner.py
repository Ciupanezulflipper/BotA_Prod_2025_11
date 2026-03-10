#!/data/data/com.termux/files/usr/bin/python3
"""
BotA snapshot alert runner with SL/TP/R:R and macro stub.

- Calls tools/emit_snapshot.py SYMBOL (H1/H4/D1 EMA/RSI/MACD snapshot, with per-TF votes).
- Decides BUY/SELL/WAIT from EMA stack + RSI + vote confluence.
- Computes a 0–100 confidence score and maps it to 0–16 (capped at 12).
- Adds simple technical SL/TP and fixed R:R for BUY/SELL signals.
- Builds a card via BotA.tools.signal_fusion.build_signal_card().
- Sends to Telegram via BotA.tools.telegramalert.send_message().

Design guarantees (per BotA PRD):
- Fail-closed on missing/invalid frames or suspicious timestamps.
- H1 age gating via MAX_H1_AGE_HOURS (ALERTS_MAX_H1_AGE_H env).
- DEBUG_ALLOW_FUTURE=1 treats future broker timestamps as age=0.0.
- Macro / sentiment layer is stubbed as 0/6 (to be filled later).
- No SL/TP/R:R for WAIT signals (they remain n/a on the card).
"""

import argparse
import io
import os
import re
import runpy
import sys
import time
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple

# ---------------------------------------------------------------------------
# Path setup: ensure BotA package is importable
# ---------------------------------------------------------------------------

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(THIS_DIR)
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from BotA.tools.signal_fusion import build_signal_card
from BotA.tools import telegramalert

# ---------------------------------------------------------------------------
# Environment configuration
# ---------------------------------------------------------------------------

HOME = os.path.expanduser("~")
BOT_DIR = os.environ.get("BOT_DIR", os.path.join(HOME, "BotA"))
TOOLS_DIR = os.path.join(BOT_DIR, "tools")
EMIT_SNAPSHOT = os.path.join(TOOLS_DIR, "emit_snapshot.py")

# Maximum acceptable H1 candle age in hours before hard block
MAX_H1_AGE_HOURS = float(os.environ.get("ALERTS_MAX_H1_AGE_H", "4.0"))

# Clock skew tolerance (seconds) for future timestamps in production
CLOCK_SKEW_TOLERANCE_SEC = float(os.environ.get("CLOCK_SKEW_TOLERANCE_SEC", "60.0"))

# Debug flag: accept ALL future timestamps as age=0.0
DEBUG_ALLOW_FUTURE = os.environ.get("ALERTS_DEBUG_ALLOW_FUTURE", "0") not in (
    "0",
    "",
    "false",
    "False",
    "no",
    "No",
    "NO",
)

# Debug flag: show raw snapshot text
DEBUG_SNAPSHOT = os.environ.get("ALERTS_DEBUG_SNAPSHOT", "0") not in (
    "0",
    "",
    "false",
    "False",
    "no",
    "No",
    "NO",
)

# ---------------------------------------------------------------------------
# Regex for parsing snapshot lines
# ---------------------------------------------------------------------------

# Example snapshot text segments:
#   === EURUSD snapshot === | H1: t=2025-12-11 22:47:16Z close=1.17426 EMA9=1.17426 EMA21=1.17282 RSI14=67.21 MACD_hist=-0.00017 vote=+1 | ...
RE_LINE = re.compile(
    r"(?P<tf>H1|H4|D1):\s*"
    r"t=(?P<ts>\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}Z?)\s+"
    r"close=(?P<close>[-+0-9.eE]+)\s+"
    r"EMA9=(?P<ema9>[-+0-9.eE]+)\s+"
    r"EMA21=(?P<ema21>[-+0-9.eE]+)\s+"
    r"RSI14=(?P<rsi>[-+0-9.eE]+)\s+"
    r"MACD_hist=(?P<macd>[-+0-9.eE]+)\s+"
    r"vote=(?P<vote>[-+0-9]+)"
)

RE_ANSI = re.compile(r"\x1b\[[0-9;]*m")


def strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from text."""
    return RE_ANSI.sub("", text)


def die(msg: str) -> None:
    """Fatal error helper."""
    print(f"[alerts_runner] FATAL: {msg}", file=sys.stderr)
    sys.exit(1)


def check_prereqs() -> None:
    """Ensure emit_snapshot.py exists before running."""
    if not os.path.isfile(EMIT_SNAPSHOT):
        die(f"Missing {EMIT_SNAPSHOT}")


# ---------------------------------------------------------------------------
# Snapshot parsing
# ---------------------------------------------------------------------------


def parse_snapshot(symbol: str) -> Dict[str, Dict]:
    """
    Execute tools/emit_snapshot.py SYMBOL in-process and parse H1/H4/D1 data.

    Returns dict like:
      {
        "H1": {"ts": datetime|None, "close": float, "ema9": float, "ema21": float,
               "rsi": float, "macd": float, "vote": int},
        "H4": {...},
        "D1": {...},
      }

    Fail-closed: on any error, returns {}.
    """
    old_argv = sys.argv[:]
    try:
        sys.argv = [EMIT_SNAPSHOT, symbol]
        buf = io.StringIO()
        with redirect_stdout(buf), redirect_stderr(buf):
            runpy.run_path(EMIT_SNAPSHOT, run_name="__main__")
        raw = buf.getvalue()
    except SystemExit:
        print(f"[alerts_runner] snapshot SystemExit for {symbol}", file=sys.stderr)
        return {}
    except Exception as e:
        print(f"[alerts_runner] snapshot exception for {symbol}: {e}", file=sys.stderr)
        return {}
    finally:
        sys.argv = old_argv

    raw = strip_ansi(raw)

    if DEBUG_SNAPSHOT:
        compact = " | ".join(ln.strip() for ln in raw.splitlines() if ln.strip())
        if compact:
            print(f"[alerts_runner] DEBUG raw snapshot for {symbol}: {compact}")

    frames: Dict[str, Dict] = {}

    # Support "single line with pipes" and "one TF per line"
    for ln in raw.splitlines():
        if not ln.strip():
            continue
        parts = ln.split("|")
        for part in parts:
            segment = part.strip()
            if not segment:
                continue
            m = RE_LINE.search(segment)
            if not m:
                continue
            gd = m.groupdict()
            ts_raw = gd["ts"]
            try:
                clean_ts = ts_raw.replace("Z", "")
                dt = datetime.strptime(clean_ts, "%Y-%m-%d %H:%M:%S").replace(
                    tzinfo=timezone.utc
                )
            except Exception:
                dt = None
            try:
                vote_val = gd["vote"].replace("+", "") if gd["vote"] else "0"
                frames[gd["tf"]] = {
                    "ts": dt,
                    "close": float(gd["close"]),
                    "ema9": float(gd["ema9"]),
                    "ema21": float(gd["ema21"]),
                    "rsi": float(gd["rsi"]),
                    "macd": float(gd["macd"]),
                    "vote": int(vote_val),
                }
            except Exception:
                # Any parsing failure for this segment: skip it
                continue

    return frames


# ---------------------------------------------------------------------------
# Time / age handling
# ---------------------------------------------------------------------------


def age_hours(ts: Optional[datetime]) -> float:
    """
    Compute age in hours between now (UTC) and ts.

    Returns:
      - age_h >= 0 if ts is in the past.
      - 0.0 if ts is in the future but within tolerance, or if DEBUG_ALLOW_FUTURE=1.
      - MAX_H1_AGE_HOURS + 1.0 on None / parsing errors / large future skew.
    """
    if ts is None:
        return MAX_H1_AGE_HOURS + 1.0

    now = datetime.now(timezone.utc)
    try:
        if ts.tzinfo is None or ts.tzinfo.utcoffset(ts) is None:
            ts_utc = ts.replace(tzinfo=timezone.utc)
        else:
            ts_utc = ts.astimezone(timezone.utc)
        delta_sec = (now - ts_utc).total_seconds()
    except Exception:
        return MAX_H1_AGE_HOURS + 1.0

    # Past or present
    if delta_sec >= 0:
        return delta_sec / 3600.0

    # Future timestamp
    abs_delta = abs(delta_sec)

    # Debug mode: accept all future timestamps as fresh
    if DEBUG_ALLOW_FUTURE:
        if DEBUG_SNAPSHOT:
            print(
                f"[alerts_runner] DEBUG: future ts accepted ({abs_delta:.0f}s ahead)"
            )
        return 0.0

    # Production mode: tolerate only small skew
    if abs_delta <= CLOCK_SKEW_TOLERANCE_SEC:
        return 0.0

    # Large future skew → treat as stale and block
    if DEBUG_SNAPSHOT:
        print(
            f"[alerts_runner] DEBUG: future ts BLOCKED "
            f"({abs_delta:.0f}s ahead, tolerance={CLOCK_SKEW_TOLERANCE_SEC}s)"
        )
    return MAX_H1_AGE_HOURS + 1.0


def _safe_float(val: object, default: float = 0.0) -> float:
    """Best-effort float conversion with default fallback."""
    try:
        return float(val)
    except Exception:
        return default


# ---------------------------------------------------------------------------
# Decision logic (EMA + RSI + votes → BUY/SELL/WAIT)
# ---------------------------------------------------------------------------


def decide(frames: Dict[str, Dict]) -> Tuple[str, int, bool, float, Optional[datetime]]:
    """
    Given parsed frames, return:

      (decision, score_0_100, weak_flag, price, h1_ts)

    Where:
      - decision ∈ {"BUY", "SELL", "WAIT"}
      - score_0_100 is a confidence score (0=strong sell, 50=neutral, 100=strong buy)
      - weak_flag indicates marginal signals
      - price is the H1 close (entry reference)
      - h1_ts is the H1 timestamp

    Age/staleness is handled in run_once(), not here.
    """
    h1 = frames.get("H1", {})
    h4 = frames.get("H4", {})
    d1 = frames.get("D1", {})

    h1_ts: Optional[datetime] = h1.get("ts")
    price = _safe_float(h1.get("close"), 0.0)

    # Basic completeness check
    need = all(k in h1 for k in ("close", "ema9", "ema21", "rsi"))
    if not need:
        return ("WAIT", 50, True, price, h1_ts)

    ema9 = _safe_float(h1.get("ema9"), price)
    ema21 = _safe_float(h1.get("ema21"), price)
    rsi = _safe_float(h1.get("rsi"), 50.0)

    # Global RSI sanity
    if not (0.0 <= rsi <= 100.0):
        return ("WAIT", 50, True, price, h1_ts)

    # Collect votes from all frames that provide them
    votes = []
    for frame in (h1, h4, d1):
        if "vote" in frame:
            try:
                votes.append(int(_safe_float(frame.get("vote", 0), 0)))
            except Exception:
                continue

    if not votes:
        return ("WAIT", 50, True, price, h1_ts)

    vote_sum = sum(votes)
    frames_with_vote = len(votes)
    threshold = frames_with_vote  # require net ±1 vote per frame on average

    up = price > ema9 > ema21
    dn = price < ema9 < ema21

    decision = "WAIT"
    score = 50

    # Hard RSI blocks
    if rsi >= 80.0 or rsi <= 20.0:
        return ("WAIT", 50, True, price, h1_ts)

    # BUY regime: bullish votes + stacked EMAs + RSI on bullish side
    if (vote_sum >= threshold) and up and (rsi >= 50.0):
        decision = "BUY"
        # Score is confidence, not direction: higher = stronger signal.
        score = 50 + vote_sum * 10
        if up:
            score += 5
        rsi_bias = rsi - 50.0
        score += int(max(min(rsi_bias, 20.0), 0.0))  # up to +20
        if rsi > 70.0:
            hot_penalty = int(min((rsi - 70.0) * 1.5, 15.0))
            score -= hot_penalty

    # SELL regime: bearish votes + stacked EMAs + RSI on bearish side
    elif (vote_sum <= -threshold) and dn and (rsi <= 50.0):
        decision = "SELL"
        # Score is still confidence: abs(vote_sum) so strong SELL has high score.
        score = 50 + abs(vote_sum) * 10
        if dn:
            score += 5
        rsi_bias = 50.0 - rsi
        score += int(max(min(rsi_bias, 20.0), 0.0))  # up to +20
        if rsi < 30.0:
            deep_penalty = int(min((30.0 - rsi) * 1.5, 15.0))
            score -= deep_penalty

    # Clamp to 0–100
    score = max(0, min(100, score))
    weak = score < 60 or (rsi > 70.0 or rsi < 30.0)

    return (decision, score, weak, price, h1_ts)


def _map_score_to_16(score_0_100: int) -> int:
    """
    Map 0–100 confidence score to 0–16, capped at 12 so snapshot engine
    cannot impersonate the full 16/16 engine.
    """
    try:
        s = int(score_0_100)
    except Exception:
        return 0
    mapped = round(s / 100.0 * 16)
    return max(0, min(12, mapped))


# ---------------------------------------------------------------------------
# SL/TP/R:R computation
# ---------------------------------------------------------------------------


def compute_levels(
    decision: str, frames: Dict[str, Dict], price: float, rr_ratio: float = 1.5
) -> Tuple[Optional[float], Optional[float], str]:
    """
    Simple technical SL/TP for snapshot scalps.

    For BUY:
      - SL just below H1 EMA21 (support) with a small buffer.
      - TP such that R:R is rr_ratio (default 1:1.5).

    For SELL:
      - SL just above H1 EMA21 (resistance) with a small buffer.
      - TP such that R:R is rr_ratio (default 1:1.5).

    Returns (sl, tp, rr_text). If computation not possible, SL/TP=None and rr="n/a".
    """
    if decision not in ("BUY", "SELL"):
        return (None, None, "n/a")

    h1 = frames.get("H1", {})
    ema9 = _safe_float(h1.get("ema9"), price)
    ema21 = _safe_float(h1.get("ema21"), price)

    if price <= 0.0 or ema21 <= 0.0:
        return (None, None, "n/a")

    # Buffer ~1/10 of the EMA9–EMA21 gap, with minimum step
    gap = abs(ema9 - ema21)
    step = max(gap / 10.0, 0.00010)

    if decision == "BUY":
        sl = ema21 - step
        if sl >= price:
            return (None, None, "n/a")
        risk = price - sl
        tp = price + risk * rr_ratio
    else:  # SELL
        sl = ema21 + step
        if sl <= price:
            return (None, None, "n/a")
        risk = sl - price
        tp = price - risk * rr_ratio

    rr_text = f"1:{rr_ratio:.2f}"
    return (sl, tp, rr_text)


# ---------------------------------------------------------------------------
# Card building and Telegram sending
# ---------------------------------------------------------------------------


def format_card(
    pair: str,
    decision: str,
    score_0_100: int,
    weak: bool,
    provider: str,
    age_h1: float,
    price: float,
    frames_label: str,
    signal_ts: Optional[datetime],
    sl: Optional[float],
    tp: Optional[float],
    rr_text: str,
    macro_score: int,
) -> str:
    """
    Build a Telegram-ready card using build_signal_card().

    SL/TP/R:R:
      - For BUY/SELL, sl/tp/rr_text may be populated.
      - For WAIT or any failure, they are left as None / "n/a".
    """
    score16 = _map_score_to_16(score_0_100)

    if signal_ts is not None:
        signal_time_utc = signal_ts.astimezone(timezone.utc).strftime(
            "%Y-%m-%d %H:%M"
        )
    else:
        signal_time_utc = "n/a"

    age_str = f"{age_h1:.2f}"
    risk_level = "high" if weak or macro_score < 3 else "normal"

    entry_str = f"{price:.5f}" if price > 0 else "n/a"
    sl_str = f"{sl:.5f}" if sl is not None else "n/a"
    tp_str = f"{tp:.5f}" if tp is not None else "n/a"
    rr_str = rr_text if rr_text and rr_text != "n/a" else "n/a"
    spread_str = "n/a"  # real spread wiring will be added in a later step

    # Human-readable technical reason
    if decision == "BUY":
        core_reason = "Bullish EMA & RSI alignment on H1/H4/D1."
    elif decision == "SELL":
        core_reason = "Bearish EMA & RSI alignment on H1/H4/D1."
    else:
        core_reason = "No clean EMA & RSI alignment; waiting for better setup."

    # Macro stub line (will be replaced once 0/6–6/6 engine is live)
    macro_line = f"📰 Macro: {macro_score}/6 (not checked yet)."

    # Two-line reason block: technical line + separate macro line
    reason = f"{core_reason}\n{macro_line}"

    ind = {
        "action": decision,
        "score": score16,
        "extra": macro_score,
        "reason": reason,
        "risk": risk_level,
        "signal_time_utc": signal_time_utc,
        "entry": entry_str if entry_str != "n/a" else None,
        "sl": sl_str if sl is not None else None,
        "tp": tp_str if tp is not None else None,
        "rr": rr_str,
        "spread": spread_str,
    }

    return build_signal_card(pair, "H1+H4+D1", ind, df=None)


def send_card(txt: str, dry: bool = False) -> bool:
    """Send card to Telegram, or print only when dry-run."""
    if dry:
        print("[alerts_runner] DRY RUN — would send:\n", txt)
        return True
    try:
        ok, info = telegramalert.send_message(txt)
    except Exception as e:
        print(f"[alerts_runner] send exception: {e}", file=sys.stderr)
        return False
    if not ok:
        print(f"[alerts_runner] send failed: {info}", file=sys.stderr)
    return bool(ok)


# ---------------------------------------------------------------------------
# Main run_once loop
# ---------------------------------------------------------------------------


def run_once(
    symbol: str,
    min_score: int,
    include_wait: bool,
    provider: str,
    dry: bool,
) -> Tuple[str, int]:
    """
    Single snapshot cycle for one symbol:

      1. Parse snapshot
      2. Decide BUY/SELL/WAIT
      3. Compute H1 age and apply hard age gate
      4. Compute SL/TP/R:R for BUY/SELL
      5. Gate on score and include_wait
      6. Build and send card
    """
    frames = parse_snapshot(symbol)
    if not frames:
        print(f"[alerts_runner] {symbol}: no frames → WAIT")
        return ("WAIT", 0)

    decision, score, weak, price, h1_ts = decide(frames)
    age_h1 = age_hours(h1_ts)

    frames_present = [tf for tf in ("H1", "H4", "D1") if tf in frames]
    frames_label = ",".join(frames_present) if frames_present else "none"

    # Default: no SL/TP/R:R
    sl: Optional[float] = None
    tp: Optional[float] = None
    rr_text: str = "n/a"

    # Compute SL/TP/R:R for BUY/SELL only
    if decision in ("BUY", "SELL"):
        sl, tp, rr_text = compute_levels(decision, frames, price)

    print(
        f"[alerts_runner] {symbol}: decision={decision} "
        f"score={score} weak={weak} price={price:.5f} "
        f"age_h1={age_h1:.2f} frames={frames_label} "
        f"SL={sl} TP={tp} RR={rr_text}"
    )

    # Decide whether to send an alert at all
    should = False
    if decision in ("BUY", "SELL"):
        should = score >= min_score
    elif decision == "WAIT" and include_wait:
        should = True

    # Hard age gate
    if age_h1 > MAX_H1_AGE_HOURS:
        if DEBUG_SNAPSHOT:
            print(
                f"[alerts_runner] {symbol}: BLOCKED by age gate "
                f"({age_h1:.2f} > {MAX_H1_AGE_HOURS})"
            )
        should = False

    macro_score = 0  # placeholder for future sentiment engine

    if should:
        card = format_card(
            pair=symbol,
            decision=decision,
            score_0_100=score,
            weak=weak,
            provider=provider,
            age_h1=age_h1,
            price=price,
            frames_label=frames_label,
            signal_ts=h1_ts,
            sl=sl,
            tp=tp,
            rr_text=rr_text,
            macro_score=macro_score,
        )
        ok = send_card(card, dry=dry)
        if not ok:
            print(f"[alerts_runner] {symbol}: send failed", file=sys.stderr)

    return (decision, score)


def main() -> None:
    check_prereqs()

    ap = argparse.ArgumentParser(
        description="BotA snapshot alert runner (with SL/TP/R:R stub)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument(
        "symbols",
        help="Comma-separated symbols, e.g. EURUSD,GBPUSD",
    )
    ap.add_argument(
        "--loop",
        type=int,
        default=0,
        help="Seconds between runs (0 = run once then exit)",
    )
    ap.add_argument(
        "--include-wait",
        action="store_true",
        help="Send WAIT cards as well as BUY/SELL",
    )
    ap.add_argument(
        "--min-score",
        type=int,
        default=60,
        help="Minimum 0–100 score for BUY/SELL alerts",
    )
    ap.add_argument(
        "--provider",
        default="YF",
        help="Provider label for the card (e.g. YF, TV, MIX)",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Print cards instead of sending to Telegram",
    )

    args = ap.parse_args()
    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    if not symbols:
        die("No symbols provided")

    def tick() -> None:
        for s in symbols:
            run_once(
                symbol=s,
                min_score=args.min_score,
                include_wait=args.include_wait,
                provider=args.provider,
                dry=args.dry_run,
            )

    if args.loop <= 0:
        tick()
        return

    print(
        f"[alerts_runner] Starting loop: interval={args.loop}s "
        f"symbols={','.join(symbols)} min_score={args.min_score} "
        f"include_wait={args.include_wait} dry_run={args.dry_run}"
    )
    print(
        f"[alerts_runner] Config: MAX_H1_AGE_H={MAX_H1_AGE_HOURS} "
        f"DEBUG_ALLOW_FUTURE={DEBUG_ALLOW_FUTURE} "
        f"CLOCK_SKEW_TOLERANCE={CLOCK_SKEW_TOLERANCE_SEC}s"
    )

    while True:
        start = time.time()
        try:
            tick()
        except Exception as e:
            print(f"[alerts_runner] loop exception: {e}", file=sys.stderr)
        elapsed = time.time() - start
        slp = max(args.loop - int(elapsed), 1)
        time.sleep(slp)


if __name__ == "__main__":
    main()
