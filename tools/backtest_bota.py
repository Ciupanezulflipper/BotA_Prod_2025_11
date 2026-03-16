#!/usr/bin/env python3
"""
BotA Backtest Framework
=======================
Tests signal accuracy on 90 days of OANDA historical M15 data.
Simulates current scoring logic + optional Bollinger Bands layer.

Usage:
  python3 tools/backtest_bota.py                    # baseline
  python3 tools/backtest_bota.py --bb               # with Bollinger Bands
  python3 tools/backtest_bota.py --bb --days 60     # 60 days with BB
  python3 tools/backtest_bota.py --compare          # baseline vs BB side by side

Requirements:
  pip install pandas --break-system-packages
"""

from __future__ import annotations
import os, sys, json, argparse, urllib.request, datetime, math
from typing import List, Dict, Any, Optional, Tuple

# ── Config ────────────────────────────────────────────────────────────────────
OANDA_TOKEN = os.environ.get("OANDA_API_TOKEN", "")
OANDA_URL   = os.environ.get("OANDA_API_URL", "https://api-fxpractice.oanda.com")
PAIRS       = ["EUR_USD", "GBP_USD"]
TF          = "M15"
OANDA_GRAN  = "M15"

# Signal parameters (matching live bot)
EMA_FAST    = 9
EMA_SLOW    = 21
RSI_PERIOD  = 14
BB_PERIOD   = 20
BB_STD      = 2.0
SCORE_MIN   = float(os.environ.get("SCORE_MIN", "30"))  # lowered default for backtest
SCORE_H1_OVERRIDE = 85
SL_MULT     = float(os.environ.get("SCALP_SL_ATR_MULT", "2.0"))
TP_MULT     = float(os.environ.get("SCALP_TP_ATR_MULT", "4.0"))
ATR_PERIOD  = 14
MAX_BARS_OPEN = 96     # max bars to hold (24h at M15 = 96 bars)

# Session filter: London + NY only (07:00-20:00 UTC)
SESSION_START_UTC = 7
SESSION_END_UTC   = 20

# ── OANDA Data Fetch ──────────────────────────────────────────────────────────
def fetch_oanda_candles(instrument: str, granularity: str, count: int = 500) -> List[Dict]:
    """Fetch candles from OANDA in batches, returns list of {t, o, h, l, c}"""
    if not OANDA_TOKEN:
        raise RuntimeError("OANDA_API_TOKEN not set — run: source ~/BotA/.env")

    all_candles = []
    # Fetch in batches of 500 (OANDA max per request)
    batches = math.ceil(count / 500)
    to_time = None

    for _ in range(batches):
        url = f"{OANDA_URL}/v3/instruments/{instrument}/candles"
        params = f"?count=500&granularity={granularity}&price=M"
        if to_time:
            params += f"&to={to_time}"

        req = urllib.request.Request(
            url + params,
            headers={"Authorization": f"Bearer {OANDA_TOKEN}", "Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read())

        candles = data.get("candles", [])
        if not candles:
            break

        batch = []
        for c in candles:
            if not c.get("complete", True):
                continue
            try:
                dt = datetime.datetime.strptime(c["time"][:19] + "Z", "%Y-%m-%dT%H:%M:%SZ")
                dt = dt.replace(tzinfo=datetime.timezone.utc)
                m = c["mid"]
                batch.append({
                    "t": dt,
                    "o": float(m["o"]),
                    "h": float(m["h"]),
                    "l": float(m["l"]),
                    "c": float(m["c"]),
                })
            except Exception:
                continue

        if not batch:
            break

        batch.sort(key=lambda x: x["t"])
        all_candles = batch + all_candles
        to_time = batch[0]["t"].strftime("%Y-%m-%dT%H:%M:%SZ")

    all_candles.sort(key=lambda x: x["t"])
    return all_candles[-count:]


# ── Indicators ────────────────────────────────────────────────────────────────
def ema(values: List[float], period: int) -> List[float]:
    if len(values) < period:
        return [None] * len(values)
    k = 2.0 / (period + 1)
    result = [None] * (period - 1)
    result.append(sum(values[:period]) / period)
    for v in values[period:]:
        result.append(v * k + result[-1] * (1 - k))
    return result

def rsi(values: List[float], period: int = 14) -> List[float]:
    if len(values) < period + 1:
        return [None] * len(values)
    result = [None] * period
    gains, losses = [], []
    for i in range(1, period + 1):
        d = values[i] - values[i-1]
        gains.append(max(d, 0))
        losses.append(max(-d, 0))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        result.append(100.0)
    else:
        rs = avg_gain / avg_loss
        result.append(100 - 100 / (1 + rs))
    for i in range(period + 1, len(values)):
        d = values[i] - values[i-1]
        gain = max(d, 0)
        loss = max(-d, 0)
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
        if avg_loss == 0:
            result.append(100.0)
        else:
            rs = avg_gain / avg_loss
            result.append(100 - 100 / (1 + rs))
    return result

def atr(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> List[float]:
    if len(closes) < period + 1:
        return [None] * len(closes)
    trs = [highs[0] - lows[0]]
    for i in range(1, len(closes)):
        tr = max(highs[i] - lows[i], abs(highs[i] - closes[i-1]), abs(lows[i] - closes[i-1]))
        trs.append(tr)
    result = [None] * period
    result.append(sum(trs[:period]) / period)
    for i in range(period, len(trs)):
        result.append((result[-1] * (period - 1) + trs[i]) / period)
    return result

def bollinger_bands(values: List[float], period: int = 20, std_mult: float = 2.0) -> Tuple[List, List, List]:
    """Returns (upper, middle, lower) bands"""
    upper, middle, lower = [], [], []
    for i in range(len(values)):
        if i < period - 1:
            upper.append(None); middle.append(None); lower.append(None)
            continue
        window = values[i-period+1:i+1]
        sma = sum(window) / period
        std = math.sqrt(sum((x - sma) ** 2 for x in window) / period)
        upper.append(sma + std_mult * std)
        middle.append(sma)
        lower.append(sma - std_mult * std)
    return upper, middle, lower


# ── Scoring ───────────────────────────────────────────────────────────────────
def score_signal(candles: List[Dict], use_bb: bool = False) -> Dict[str, Any]:
    """
    Score a signal at the last candle.
    Returns: {direction, score, atr_val, entry, sl, tp, valid}
    """
    closes = [c["c"] for c in candles]
    highs  = [c["h"] for c in candles]
    lows   = [c["l"] for c in candles]

    if len(closes) < 30:
        return {"valid": False}

    ema_fast = ema(closes, EMA_FAST)
    ema_slow = ema(closes, EMA_SLOW)
    rsi_vals = rsi(closes, RSI_PERIOD)
    atr_vals = atr(highs, lows, closes, ATR_PERIOD)

    ef = ema_fast[-1]
    es = ema_slow[-1]
    r  = rsi_vals[-1]
    a  = atr_vals[-1]
    price = closes[-1]

    if any(v is None for v in [ef, es, r, a]):
        return {"valid": False}

    # Base score (matching signal_engine.py logic)
    ema_dist  = (ef - es) / price * 1000.0
    rsi_bias  = r - 50.0
    base_score = abs(ema_dist) * 2.0 + abs(rsi_bias) * 1.2
    score = max(0, min(100, base_score))

    # Direction
    if ef > es and r >= 55:
        direction = "BUY"
    elif ef < es and r <= 45:
        direction = "SELL"
    else:
        return {"valid": False, "score": score}

    # Bollinger Bands boost/penalty
    bb_bonus = 0
    if use_bb and len(closes) >= BB_PERIOD:
        bb_upper, bb_mid, bb_lower = bollinger_bands(closes, BB_PERIOD, BB_STD)
        bu = bb_upper[-1]
        bl = bb_lower[-1]
        bm = bb_mid[-1]

        if bu is not None and bl is not None:
            band_width = bu - bl
            squeeze = band_width < (bm * 0.005) if bm else False  # tight band = low volatility

            if squeeze:
                # Penalize signals during squeeze — low volatility, likely to fail
                bb_bonus = -10
            elif direction == "SELL" and price >= bu * 0.9998:
                # Price at upper band + SELL = strong confluence
                bb_bonus = +8
            elif direction == "BUY" and price <= bl * 1.0002:
                # Price at lower band + BUY = strong confluence
                bb_bonus = +8
            elif direction == "SELL" and price > bm:
                # Price above midline + SELL = mild confluence
                bb_bonus = +3
            elif direction == "BUY" and price < bm:
                # Price below midline + BUY = mild confluence
                bb_bonus = +3
            else:
                # Counter-band direction = penalty
                bb_bonus = -5

    score = max(0, min(100, score + bb_bonus))

    if score < SCORE_MIN:
        return {"valid": False, "score": score}

    # SL/TP
    if direction == "BUY":
        sl = price - SL_MULT * a
        tp = price + TP_MULT * a
    else:
        sl = price + SL_MULT * a
        tp = price - TP_MULT * a

    rr = abs(tp - price) / abs(sl - price) if abs(sl - price) > 0 else 0
    if rr < 1.4:
        return {"valid": False, "score": score}

    return {
        "valid": True,
        "direction": direction,
        "score": round(score, 1),
        "atr": round(a, 6),
        "entry": round(price, 5),
        "sl": round(sl, 5),
        "tp": round(tp, 5),
        "rr": round(rr, 2),
    }


# ── Session Filter ────────────────────────────────────────────────────────────
def in_session(dt: datetime.datetime) -> bool:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    """Returns True if datetime is within London+NY session (07:00-20:00 UTC, Mon-Fri)"""
    if dt.weekday() >= 5:  # Saturday=5, Sunday=6
        return False
    return SESSION_START_UTC <= dt.hour < SESSION_END_UTC


# ── Backtest Engine ───────────────────────────────────────────────────────────
def run_backtest(candles: List[Dict], use_bb: bool, pair: str, days: int) -> Dict:
    """
    Walk through candles, generate signals, check outcomes.
    Returns stats dict.
    """
    # Filter to requested days
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)
    candles = [c for c in candles if c["t"] >= cutoff]

    if len(candles) < 100:
        return {"error": f"insufficient candles: {len(candles)}"}

    warmup = max(EMA_SLOW, RSI_PERIOD, BB_PERIOD, ATR_PERIOD) + 10
    signals = []
    last_signal_bar = -96  # prevent overlapping signals

    for i in range(warmup, len(candles)):
        c = candles[i]

        # Session filter
        if not in_session(c["t"]):
            continue

        # Prevent signal spam — minimum 4 bars (1h) between signals
        if i - last_signal_bar < 4:
            continue

        window = candles[max(0, i-100):i+1]
        sig = score_signal(window, use_bb=use_bb)

        if not sig.get("valid"):
            continue

        # Walk forward to find outcome
        entry = sig["entry"]
        sl    = sig["sl"]
        tp    = sig["tp"]
        direction = sig["direction"]
        outcome = "OPEN"
        result_pips = 0.0
        pip = 0.01 if "JPY" in pair else 0.0001

        for j in range(i+1, min(i+1+MAX_BARS_OPEN, len(candles))):
            future = candles[j]
            if direction == "BUY":
                if future["h"] >= tp:
                    outcome = "WIN"
                    result_pips = round((tp - entry) / pip, 1)
                    break
                if future["l"] <= sl:
                    outcome = "LOSS"
                    result_pips = round((sl - entry) / pip, 1)
                    break
            else:  # SELL
                if future["l"] <= tp:
                    outcome = "WIN"
                    result_pips = round((entry - tp) / pip, 1)
                    break
                if future["h"] >= sl:
                    outcome = "LOSS"
                    result_pips = round((entry - sl) / pip, 1)
                    break

        if outcome == "OPEN":
            outcome = "EXPIRED"

        signals.append({
            "time": c["t"].strftime("%Y-%m-%d %H:%M"),
            "direction": direction,
            "score": sig["score"],
            "entry": entry,
            "sl": sl,
            "tp": tp,
            "rr": sig["rr"],
            "outcome": outcome,
            "pips": result_pips,
        })
        last_signal_bar = i

    if not signals:
        in_sess = sum(1 for c in candles if in_session(c["t"]))
        scored = 0
        for i in range(warmup, min(warmup+200, len(candles))):
            window = candles[max(0,i-100):i+1]
            sig = score_signal(window, use_bb=False)
            if sig.get("score", 0) > 0:
                scored += 1
        return {"error": f"no signals generated (in_session={in_sess}, candles={len(candles)}, warmup={warmup}, scored_sample={scored})"}

    closed = [s for s in signals if s["outcome"] in ("WIN", "LOSS")]
    wins   = [s for s in closed if s["outcome"] == "WIN"]
    losses = [s for s in closed if s["outcome"] == "LOSS"]
    expired = [s for s in signals if s["outcome"] == "EXPIRED"]

    total_pips = sum(s["pips"] for s in closed)
    win_rate   = len(wins) / len(closed) * 100 if closed else 0
    avg_score  = sum(s["score"] for s in signals) / len(signals)

    return {
        "pair": pair,
        "days": days,
        "use_bb": use_bb,
        "total_signals": len(signals),
        "closed": len(closed),
        "wins": len(wins),
        "losses": len(losses),
        "expired": len(expired),
        "win_rate": round(win_rate, 1),
        "total_pips": round(total_pips, 1),
        "avg_pips": round(total_pips / len(closed), 1) if closed else 0,
        "avg_score": round(avg_score, 1),
        "best_trade": round(max((s["pips"] for s in closed), default=0), 1),
        "worst_trade": round(min((s["pips"] for s in closed), default=0), 1),
        "signals": signals[-20:],  # last 20 for review
    }


# ── Report ────────────────────────────────────────────────────────────────────
def print_report(result: Dict, label: str = ""):
    if "error" in result:
        print(f"ERROR: {result['error']}")
        return

    tag = f" [{label}]" if label else ""
    print(f"\n{'='*60}")
    print(f"  BotA Backtest{tag} — {result['pair']} — {result['days']} days")
    print(f"  Bollinger Bands: {'ON' if result['use_bb'] else 'OFF'}")
    print(f"{'='*60}")
    print(f"  Total signals  : {result['total_signals']}")
    print(f"  Closed (W/L)   : {result['closed']} ({result['wins']}W / {result['losses']}L)")
    print(f"  Expired        : {result['expired']}")
    print(f"  Win Rate       : {result['win_rate']}%")
    print(f"  Total Pips     : {result['total_pips']:+.1f}")
    print(f"  Avg Pips/Trade : {result['avg_pips']:+.1f}")
    print(f"  Avg Score      : {result['avg_score']}")
    print(f"  Best Trade     : +{result['best_trade']} pips")
    print(f"  Worst Trade    : {result['worst_trade']} pips")
    print(f"{'='*60}")

    # Break-even win rate
    if result['wins'] > 0 and result['losses'] > 0:
        avg_win  = sum(s["pips"] for s in result["signals"] if s["outcome"] == "WIN") / result["wins"] if result["wins"] else 0
        avg_loss = abs(sum(s["pips"] for s in result["signals"] if s["outcome"] == "LOSS") / result["losses"]) if result["losses"] else 0
        if avg_loss > 0:
            breakeven_wr = avg_loss / (avg_win + avg_loss) * 100
            print(f"  Break-even WR  : {breakeven_wr:.1f}%")
            verdict = "✅ PROFITABLE" if result['win_rate'] > breakeven_wr else "❌ LOSING"
            print(f"  Verdict        : {verdict}")
    print()


def print_comparison(baseline: Dict, bb: Dict, pair: str):
    print(f"\n{'='*60}")
    print(f"  COMPARISON — {pair}")
    print(f"{'='*60}")
    print(f"  {'Metric':<20} {'Baseline':>12} {'With BB':>12} {'Delta':>10}")
    print(f"  {'-'*56}")

    metrics = [
        ("Win Rate", "win_rate", "%"),
        ("Total Pips", "total_pips", "p"),
        ("Avg Pips", "avg_pips", "p"),
        ("Signals", "total_signals", ""),
        ("Avg Score", "avg_score", ""),
    ]
    for label, key, unit in metrics:
        b = baseline.get(key, 0)
        w = bb.get(key, 0)
        delta = w - b
        sign = "+" if delta >= 0 else ""
        print(f"  {label:<20} {b:>11.1f}{unit} {w:>11.1f}{unit} {sign}{delta:>8.1f}{unit}")

    print(f"{'='*60}")
    if bb.get("win_rate", 0) > baseline.get("win_rate", 0):
        print(f"  ✅ Bollinger Bands IMPROVES win rate by {bb['win_rate'] - baseline['win_rate']:.1f}%")
    else:
        print(f"  ❌ Bollinger Bands does NOT improve win rate")
    print()


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description="BotA Backtest Framework")
    ap.add_argument("--days", type=int, default=90, help="Days to backtest (default: 90)")
    ap.add_argument("--bb", action="store_true", help="Enable Bollinger Bands scoring")
    ap.add_argument("--compare", action="store_true", help="Run baseline vs BB comparison")
    ap.add_argument("--pair", default="all", help="Pair to test: EURUSD, GBPUSD, or all")
    args = ap.parse_args()

    if not OANDA_TOKEN:
        print("ERROR: OANDA_API_TOKEN not set")
        print("Run: source ~/BotA/.env && source ~/BotA/config/strategy.env")
        sys.exit(1)

    pairs = PAIRS
    if args.pair.upper() == "EURUSD":
        pairs = ["EUR_USD"]
    elif args.pair.upper() == "GBPUSD":
        pairs = ["GBP_USD"]

    # Calculate candles needed: days * 24h * 4 (M15) + 20% buffer
    candles_needed = int(args.days * 24 * 4 * 1.2)
    # OANDA max per request is 500, so batch: fetch enough batches
    fetch_count = min(candles_needed, 5000)

    for instrument in pairs:
        pair_display = instrument.replace("_", "")
        print(f"\nFetching {fetch_count} M15 candles for {pair_display}...")

        try:
            candles = fetch_oanda_candles(instrument, OANDA_GRAN, fetch_count)
            print(f"Got {len(candles)} candles ({candles[0]['t'].date()} to {candles[-1]['t'].date()})")
        except Exception as e:
            print(f"ERROR fetching {instrument}: {e}")
            continue

        if args.compare:
            print(f"\nRunning baseline backtest...")
            baseline = run_backtest(candles, use_bb=False, pair=pair_display, days=args.days)
            print(f"Running Bollinger Bands backtest...")
            bb_result = run_backtest(candles, use_bb=True, pair=pair_display, days=args.days)

            print_report(baseline, "BASELINE")
            print_report(bb_result, "WITH BB")
            print_comparison(baseline, bb_result, pair_display)

        elif args.bb:
            result = run_backtest(candles, use_bb=True, pair=pair_display, days=args.days)
            print_report(result, "WITH BB")

        else:
            result = run_backtest(candles, use_bb=False, pair=pair_display, days=args.days)
            print_report(result, "BASELINE")


if __name__ == "__main__":
    main()

