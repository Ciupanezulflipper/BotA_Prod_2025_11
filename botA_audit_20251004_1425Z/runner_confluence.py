#!/usr/bin/env python3
"""
runner_confluence.py - BotA signal generator with data-quality gates,
dedupe, and enhanced card output (RR ratio, pip distances, spread impact, ATR regime)
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone

import pandas as pd

from .data_quality import validate_ohlc
from .dedupe_cache import should_send_signal, mark_signal_sent, cleanup_old
from .circuit_breaker import should_allow_send


BOT_VERSION = os.getenv("BOT_VERSION", "dev")
MIN_BARS = 120

# Gates / thresholds (env-overridable)
MIN_ATR_PIPS = float(os.getenv("MIN_ATR_PIPS", "5.0"))
MAX_STALENESS_MIN = int(os.getenv("MAX_STALENESS_MIN", "45"))
MIN_SCORE16 = int(os.getenv("MIN_SCORE16", "12"))
MIN_SCORE6 = int(os.getenv("MIN_SCORE6", "4"))
DEDUP_TIME_MIN = int(os.getenv("DEDUP_TIME_MIN", "60"))
DEDUP_PRICE_PIPS = float(os.getenv("DEDUP_PRICE_PIPS", "4.0"))

# Targets (env-overridable)
ATR_SL_MULT = float(os.getenv("ATR_SL_MULT", "1.5"))
ATR_TP1_MULT = float(os.getenv("ATR_TP1_MULT", "1.5"))
ATR_TP2_MULT = float(os.getenv("ATR_TP2_MULT", "3.0"))

def _pip_size(pair: str) -> float:
    return 0.01 if pair.upper().endswith("JPY") else 0.0001

def _get_spread_pips(pair: str):
    src = os.getenv("SPREAD_SOURCE", "auto").lower()
    commission = float(os.getenv("COMMISSION_PIPS", "0.0"))

    if src == "manual":
        try:
            spread = float(os.getenv("SPREAD_PIPS", "1.5"))
        except Exception:
            spread = 1.5
        return spread + commission, "manual"

    # simple heuristic fallback for auto
    if pair.upper() == "EURUSD":
        return 1.5 + commission, "auto"
    return None, "auto"

def _compute_atr(df: pd.DataFrame, period: int) -> float:
    if len(df) < period:
        raise ValueError(f"Need {period}+ bars, got {len(df)}")

    high = df["high"]
    low = df["low"]
    close = df["close"]
    prev_close = close.shift(1)

    tr1 = (high - low).abs()
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    # Simple MA of TR (intentionally not Wilder smoothing, per prior file)
    atr = tr.rolling(window=period, min_periods=period).mean()
    atr_values = atr.dropna()
    if len(atr_values) == 0:
        raise ValueError("ATR produced no values")

    return float(atr_values.iloc[-1])

def _compute_targets(action: str, price: float, atr: float,
                     sl_mult: float, tp1_mult: float, tp2_mult: float):
    out = {}
    if action == "BUY":
        out["sl"]  = price - sl_mult * atr
        out["tp1"] = price + tp1_mult * atr
        out["tp2"] = price + tp2_mult * atr
        out["tp3"] = price + (tp2_mult * 1.5) * atr
    elif action == "SELL":
        out["sl"]  = price + sl_mult * atr
        out["tp1"] = price - tp1_mult * atr
        out["tp2"] = price - tp2_mult * atr
        out["tp3"] = price - (tp2_mult * 1.5) * atr
    return out

def _atr_regime_label(atr_pips: float) -> str:
    # simple bands; feel free to tune later
    if atr_pips < 5:
        return "Low Volatility"
    if atr_pips < 8:
        return "Normal Volatility"
    return "High Volatility"

def _send_alert(msg: str):
    monitor_chat = os.getenv("TELEGRAM_MONITOR_CHAT_ID")
    if not monitor_chat:
        return
    try:
        from BotA.tools.telegramalert import send_telegram_message
        send_telegram_message(f"🚨 BotA Alert\n{msg}")
    except Exception:
        pass

def _log_jsonl(entry: dict):
    try:
        with open("signals.jsonl", "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass

def _log_csv(entry: dict):
    import csv
    exists = os.path.exists("signals.csv")
    try:
        with open("signals.csv", "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=entry.keys())
            if not exists:
                writer.writeheader()
            writer.writerow(entry)
    except Exception:
        pass

def run_analysis(pair: str, tf: str, bars: int, dry_run: bool, force: bool):
    # ----- Fetch -----
    try:
        from BotA.tools.providers import get_ohlc
    except Exception as e:
        print(f"✗ Provider import failed: {e}")
        _send_alert(f"Provider import failed: {e}")
        sys.exit(1)

    try:
        rows, source = get_ohlc(pair, tf, bars)
    except Exception as e:
        print(f"✗ Fetch failed: {e}")
        _send_alert(f"Fetch failed {pair} {tf}: {e}")
        sys.exit(1)

    if not rows or (len(rows) < MIN_BARS and not force):
        msg = f"Insufficient data: {len(rows) if rows else 0} bars (need {MIN_BARS})"
        print(f"✗ {msg}")
        _send_alert(msg)
        sys.exit(1)

    # ----- Normalize -----
    try:
        df = pd.DataFrame(rows)
        for col in ["open", "high", "low", "close"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df["time"] = pd.to_datetime(df["time"], utc=True, errors="coerce")
        df = df.dropna(subset=["time", "close"]).sort_values("time")
        df = df.set_index("time")
    except Exception as e:
        print(f"✗ Data normalization failed: {e}")
        sys.exit(1)

    # ----- ATR -----
    atr_period = int(os.getenv("ATR_PERIOD", "14"))
    pip = _pip_size(pair)
    try:
        atr_price = _compute_atr(df, atr_period)
        atr_pips = atr_price / pip
    except Exception as e:
        print(f"⚠ ATR failed: {e}")
        atr_price = None
        atr_pips = None

    # ----- Data quality gates -----
    valid, errors = validate_ohlc(rows, tf, MAX_STALENESS_MIN, MIN_ATR_PIPS, atr_pips)
    if not valid and not force:
        msg = f"Data quality failed: {'; '.join(errors)}"
        print(f"✗ {msg}")
        _send_alert(msg)
        sys.exit(1)
    elif not valid and force:
        # still continue, but log a warning
        print(f"⚠ Data quality issues (forced): {'; '.join(errors)}")

    # ----- Indicators -----
    try:
        from .indicators_adapter import analyze_indicators
        analysis = analyze_indicators(df, pair)
        if analysis is None:
            analysis = {}
    except Exception as e:
        print(f"⚠ Analysis failed: {e}")
        analysis = {}

    original_action = str(analysis.get("action", "WAIT")).upper()
    score16 = analysis.get("score16", 0)
    score6 = analysis.get("score6", 0)
    reason = str(analysis.get("reason", "n/a"))

    action = original_action
    rejection_reason = None

    if not force:
        if score16 < MIN_SCORE16:
            action = "WAIT"
            rejection_reason = f"score16={score16} < {MIN_SCORE16}"
        elif score6 < MIN_SCORE6:
            action = "WAIT"
            rejection_reason = f"score6={score6} < {MIN_SCORE6}"
        elif atr_pips and atr_pips < MIN_ATR_PIPS:
            action = "WAIT"
            rejection_reason = f"ATR={atr_pips:.1f} < {MIN_ATR_PIPS}"

    price = float(df["close"].iloc[-1])
    signal_time = df.index[-1]

    # ----- Targets (only when ATR and directional) -----
    targets = None
    if atr_price and action in ("BUY", "SELL"):
        targets = _compute_targets(action, price, atr_price, ATR_SL_MULT, ATR_TP1_MULT, ATR_TP2_MULT)

    # ----- Spread / ratio gate -----
    spread_pips, spread_src = _get_spread_pips(pair)
    spread_max_ratio = float(os.getenv("SPREAD_ATR_MAX", "0.35"))
    gated = False
    ratio = None

    if spread_pips and atr_pips and atr_pips > 0 and not force:
        ratio = spread_pips / atr_pips
        if ratio > spread_max_ratio:
            action = "WAIT"
            rejection_reason = f"spread/ATR={ratio:.2%} > {spread_max_ratio:.0%}"
            gated = True

    # ----- Dedup -----
    if action in ("BUY", "SELL") and not force:
        should_send, dedup_reason = cleanup_old(); should_send_signal(
            pair, action, price, DEDUP_TIME_MIN, DEDUP_PRICE_PIPS, pip
        )
        if not should_send:
            action = "WAIT"
            rejection_reason = dedup_reason

    # ----- Card build -----
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    card_lines = []
    card_lines.append(f"📊 {pair} ({tf})")
    card_lines.append(f"🕒 {now_str}")
    card_lines.append(f"📈 Action: {action}")
    card_lines.append(f"📊 Score: {score16}/16 + {score6}/6")
    card_lines.append(f"🧠 Reason: {reason}")

    # Risk & targets block
    if targets and atr_pips:
        atr_regime = _atr_regime_label(atr_pips)
        # pip distances
        sl_pips  = abs(price - targets['sl'])  / pip
        tp1_pips = abs(targets['tp1'] - price) / pip
        tp2_pips = abs(targets['tp2'] - price) / pip
        tp3_pips = abs(targets['tp3'] - price) / pip

        # RR based on tp1 vs sl
        rr = (tp1_pips / sl_pips) if sl_pips > 0 else 0.0

        card_lines.append("")
        card_lines.append("📐 Risk & Targets")
        card_lines.append(f"ATR(14): {atr_pips:.1f} pips")
        card_lines.append(f"ATR Regime: {atr_regime}")
        card_lines.append(f"Entry:  {price:.5f}")
        card_lines.append(f"SL:     {targets['sl']:.5f}  ({sl_pips:.1f} pips)")
        card_lines.append(f"TP1:    {targets['tp1']:.5f}  ({tp1_pips:.1f} pips)  (1R)")
        card_lines.append(f"TP2:    {targets['tp2']:.5f}  ({tp2_pips:.1f} pips)  (2R)")
        card_lines.append(f"TP3:    {targets['tp3']:.5f}  ({tp3_pips:.1f} pips)")
        card_lines.append(f"Risk/Reward: 1:{rr:.2f}")

        if ratio is None and spread_pips and atr_pips > 0:
            ratio = spread_pips / atr_pips

        if ratio is not None:
            card_lines.append(f"Spread Impact: {ratio*100:.1f}% of ATR")
        if gated:
            card_lines.append("⚠️ Spread high vs ATR")

    # Always show spread line if known
    if spread_pips:
        card_lines.append(f"\n📉 Spread: {spread_pips:.1f} pips")

    card_lines.append(f"\nPrice source: close")
    card_lines.append(f"Source: {source}\n")
        # Circuit breaker: skip send on recent losing streak
    if not should_allow_send():
        print("⊗ Rejected: circuit breaker (too many recent losses)"); return
if dry_run:
        card_lines.append("Tip: use --dry-run to preview or --force to send.")

    card = "\n".join(card_lines)

    # ----- logs -----
    csv_entry = {
        "timestamp": signal_time.isoformat(),
        "pair": pair,
        "timeframe": tf,
        "action": action,
        "original_action": original_action,
        "entry_price": f"{price:.5f}",
        "stop_loss": f"{targets['sl']:.5f}" if targets else "n/a",
        "tp1": f"{targets['tp1']:.5f}" if targets else "n/a",
        "tp2": f"{targets['tp2']:.5f}" if targets else "n/a",
        "tp3": f"{targets['tp3']:.5f}" if targets else "n/a",
        "spread": spread_pips if spread_pips else "n/a",
        "atr": f"{atr_pips:.1f}" if atr_pips else "n/a",
        "score16": score16,
        "score6": score6,
        "reason": reason,
        "rejection_reason": rejection_reason or "",
    }
    _log_csv(csv_entry)

    jsonl_entry = {
        "version": BOT_VERSION,
        "timestamp": signal_time.isoformat(),
        "signal": csv_entry,
        "context": {
            "bars_fetched": len(df),
            "data_span_hours": (df.index[-1] - df.index[0]).total_seconds() / 3600 if len(df) else 0,
            "env": {
                "ATR_PERIOD": atr_period,
                "MIN_ATR_PIPS": MIN_ATR_PIPS,
                "MIN_SCORE16": MIN_SCORE16,
                "MIN_SCORE6": MIN_SCORE6,
                "SPREAD_ATR_MAX": spread_max_ratio,
                "ATR_SL_MULT": ATR_SL_MULT,
                "ATR_TP1_MULT": ATR_TP1_MULT,
                "ATR_TP2_MULT": ATR_TP2_MULT,
            },
        },
        "card": card,
        "sent": False,
    }
    _log_jsonl(jsonl_entry)

    # ----- output / send -----
    print(card)

    if dry_run:
        print(f"\n[DRY RUN] Would send: {action}")
        return

    if action == "WAIT":
        if rejection_reason:
            print(f"⊗ Rejected: {rejection_reason}")
        else:
            print("⊗ Rejected: WAIT")
        return

    try:
        from BotA.tools.telegramalert import send_telegram_message
        ok, err = send_telegram_message(card)
    except Exception as e:
        print(f"✗ Telegram failed: {e}")
        mark_signal_sent(pair, action, price, sent=False)
        sys.exit(1)

    if ok:
        print("✓ Sent to Telegram")
        mark_signal_sent(pair, action, price, sent=True)
        jsonl_entry["sent"] = True
        _log_jsonl(jsonl_entry)
        sys.exit(0)
    else:
        print(f"✗ Send failed: {err}")
        mark_signal_sent(pair, action, price, sent=False)
        sys.exit(1)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pair", required=True)
    ap.add_argument("--tf", required=True)
    ap.add_argument("--bars", type=int, default=200)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    run_analysis(args.pair.upper(), args.tf.upper(), args.bars, args.dry_run, args.force)

if __name__ == "__main__":
    main()
