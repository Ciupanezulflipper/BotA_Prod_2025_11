#!/usr/bin/env python3
"""
auditor.py — Backtest BotA signals against future OHLC bars.

Reads signals.csv, fetches forward bars with BotA.providers.get_ohlc,
simulates trade outcomes (spread-aware), and writes trades.csv + prints a summary.

Key features:
- Spread-aware fills (TP needs price move +spread; SL triggers -spread in opposite direction)
- Path ambiguity handling (pessimistic | optimistic | strict modes)
- Dynamic / fixed horizon (bars to look ahead), env override HORIZON_BARS
- Robust CSV normalization and UTC timestamps
- Clear win/loss/NONE/AMBIG outcomes with R-multiples

Usage:
  python -m BotA.tools.auditor --signals signals.csv --out trades.csv --horizon 192 --pair EURUSD --tf M15
Env:
  HORIZON_BARS        (int)  — overrides --horizon
  DEFAULT_SPREAD_PIPS (float) default spread pips when signals.csv has no 'spread' column/value
  PATH_RULE           (str)  — pessimistic|optimistic|strict (default: pessimistic)
"""

import argparse
import os
import sys
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple

import pandas as pd


# ---------------------------
# CLI & IO
# ---------------------------

def parse_args():
    p = argparse.ArgumentParser(description="Audit forex signals against historical data")
    p.add_argument("--signals", default="signals.csv", help="Input signals CSV")
    p.add_argument("--out", default="trades.csv", help="Output trades CSV")
    p.add_argument("--horizon", type=int, default=96, help="Max bars to look ahead (per signal)")
    p.add_argument("--pair", default="EURUSD", help="Default pair if missing in signal")
    p.add_argument("--tf", default="M15", help="Default timeframe if missing in signal")
    return p.parse_args()


def load_signals(path: str) -> pd.DataFrame:
    """Load signals.csv and normalize column names and types."""
    df = pd.read_csv(path)
    df.columns = df.columns.str.strip().str.lower()

    # timestamp required
    if "timestamp" not in df.columns:
        raise ValueError("signals.csv must include 'timestamp' column (UTC)")

    # parse timestamp -> UTC
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    df = df.dropna(subset=["timestamp"])

    # Allow a few common header variants
    rename_map = {
        "timeframe": "tf",
        "pair": "pair",
        "entry": "entry_price",
        "entryprice": "entry_price",
        "stop": "stop_loss",
        "sl": "stop_loss",
    }
    for k, v in rename_map.items():
        if k in df.columns and v not in df.columns:
            df[v] = df[k]

    # Required trade fields
    required = ["action", "entry_price", "stop_loss", "tp1", "tp2", "tp3"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"signals.csv missing required columns: {missing}")

    # Optional fields
    for col in ["pair", "tf", "spread", "atr", "score6", "score16", "reason"]:
        if col not in df.columns:
            df[col] = "n/a"

    # Types
    for col in ["entry_price", "stop_loss", "tp1", "tp2", "tp3", "atr", "score6", "score16"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


# ---------------------------
# Market data helpers
# ---------------------------

def fetch_future_bars(pair: str, tf: str, after_time: datetime, bars: int) -> Optional[pd.DataFrame]:
    """
    Fetch future bars strictly after 'after_time' using BotA provider.
    Returns DataFrame indexed by UTC time with columns: [open, high, low, close].
    """
    try:
        from BotA.tools.providers import get_ohlc
    except ImportError as e:
        print(f"✗ Cannot import BotA.tools.providers: {e}")
        sys.exit(1)

    # Pull more than needed, we filter > after_time and then head(horizon)
    try:
        rows, source = get_ohlc(pair, tf, bars * 4)
    except Exception as e:
        print(f"⚠ Failed to fetch {pair} {tf}: {e}")
        return None

    if not rows:
        return None

    df = pd.DataFrame(rows)
    needed = ["time", "open", "high", "low", "close"]
    if any(col not in df.columns for col in needed):
        return None

    df["time"] = pd.to_datetime(df["time"], utc=True, errors="coerce")
    for c in ["open", "high", "low", "close"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    df = df.dropna(subset=["time", "close"]).sort_values("time")
    df = df[df["time"] > after_time].set_index("time")

    if len(df) == 0:
        return None

    return df.head(bars)


def pip_size_for(pair: str) -> float:
    return 0.01 if pair.upper().endswith("JPY") else 0.0001


# ---------------------------
# Trade simulation
# ---------------------------

def simulate_trade(
    action: str,
    entry: float,
    sl: float,
    tp1: float,
    tp2: float,
    tp3: float,
    signal_time: datetime,
    future_bars: pd.DataFrame,
    spread_pips: float,
    pip: float,
    path_rule: str = "pessimistic",
) -> Dict:
    """
    Simulate trade outcome by checking first level hit with spread-aware triggers.

    path_rule:
      - 'pessimistic': SL priority if both hit in same bar
      - 'optimistic' : TP priority if both hit in same bar
      - 'strict'     : if both hit in same bar -> AMBIG outcome (neither win/loss counted)
    """
    TOL = 1e-12
    action = str(action).upper()
    if action not in ("BUY", "SELL"):
        return _result("INVALID", "NONE", 0.0, signal_time, entry, 0)

    # Effective trigger adjustments due to spread
    spread_px = (spread_pips or 0.0) * pip

    # For BUY:
    #   To be FILLED at TP: market must print high >= TP + spread (we sell to close at the bid; mid->ask spread assumed)
    #   To be STOPPED at SL: bid must fall to SL, conservative -> low <= SL - spread
    # For SELL: symmetric inverse.
    def buy_hits(bar_high, bar_low):
        sl_hit = bar_low <= (sl - spread_px + TOL)
        tp1_hit = bar_high >= (tp1 + spread_px - TOL)
        tp2_hit = bar_high >= (tp2 + spread_px - TOL)
        tp3_hit = bar_high >= (tp3 + spread_px - TOL)
        return sl_hit, tp1_hit, tp2_hit, tp3_hit

    def sell_hits(bar_high, bar_low):
        sl_hit = bar_high >= (sl + spread_px - TOL)
        tp1_hit = bar_low <= (tp1 - spread_px + TOL)
        tp2_hit = bar_low <= (tp2 - spread_px + TOL)
        tp3_hit = bar_low <= (tp3 - spread_px + TOL)
        return sl_hit, tp1_hit, tp2_hit, tp3_hit

    # Walk forward bars
    for idx, row in future_bars.iterrows():
        h = float(row["high"])
        l = float(row["low"])

        if action == "BUY":
            sl_hit, tp1_hit, tp2_hit, tp3_hit = buy_hits(h, l)
            # same-bar ambiguity handling
            both_sl_tp = sl_hit and (tp1_hit or tp2_hit or tp3_hit)
            if both_sl_tp and path_rule == "strict":
                return _result("AMBIG", "AMBIG", 0.0, idx, entry, _mins(idx, signal_time))

            if sl_hit and (path_rule == "pessimistic" or not (tp1_hit or tp2_hit or tp3_hit)):
                return _result("LOSS", "SL", -1.0, idx, sl, _mins(idx, signal_time))

            if tp3_hit:
                return _result("WIN", "TP3", 3.0, idx, tp3, _mins(idx, signal_time))
            if tp2_hit:
                return _result("WIN", "TP2", 2.0, idx, tp2, _mins(idx, signal_time))
            if tp1_hit:
                return _result("WIN", "TP1", 1.0, idx, tp1, _mins(idx, signal_time))

            if both_sl_tp and path_rule == "optimistic":
                # if we got here, TP priority already handled; fallthrough means SL only
                return _result("LOSS", "SL", -1.0, idx, sl, _mins(idx, signal_time))

        else:  # SELL
            sl_hit, tp1_hit, tp2_hit, tp3_hit = sell_hits(h, l)
            both_sl_tp = sl_hit and (tp1_hit or tp2_hit or tp3_hit)
            if both_sl_tp and path_rule == "strict":
                return _result("AMBIG", "AMBIG", 0.0, idx, entry, _mins(idx, signal_time))

            if sl_hit and (path_rule == "pessimistic" or not (tp1_hit or tp2_hit or tp3_hit)):
                return _result("LOSS", "SL", -1.0, idx, sl, _mins(idx, signal_time))

            if tp3_hit:
                return _result("WIN", "TP3", 3.0, idx, tp3, _mins(idx, signal_time))
            if tp2_hit:
                return _result("WIN", "TP2", 2.0, idx, tp2, _mins(idx, signal_time))
            if tp1_hit:
                return _result("WIN", "TP1", 1.0, idx, tp1, _mins(idx, signal_time))

            if both_sl_tp and path_rule == "optimistic":
                return _result("LOSS", "SL", -1.0, idx, sl, _mins(idx, signal_time))

    # No hit within horizon -> NONE (flat outcome)
    if len(future_bars) > 0:
        last_time = future_bars.index[-1]
        last_close = float(future_bars["close"].iloc[-1])
        return _result("NONE", "NONE", 0.0, last_time, last_close, _mins(last_time, signal_time))

    return _result("NONE", "NONE", 0.0, signal_time, entry, 0)


def _mins(a: datetime, b: datetime) -> int:
    return int((a - b).total_seconds() / 60)


def _result(outcome: str, hit: str, R: float, t: datetime, px: float, mins: int) -> Dict:
    return {
        "outcome": outcome,
        "hit_level": hit,
        "R_multiple": float(R),
        "exit_time": t,
        "exit_price": float(px),
        "duration_minutes": int(mins),
    }


# ---------------------------
# Orchestration
# ---------------------------

def audit_signals(signals_df: pd.DataFrame, horizon: int, default_pair: str, default_tf: str) -> pd.DataFrame:
    """Process each BUY/SELL signal and simulate outcomes."""
    trades: List[Dict] = []
    total = len(signals_df)
    print(f"📊 Processing {total} signals...")

    # Global knobs
    env_horizon = int(os.getenv("HORIZON_BARS", str(horizon)))
    default_spread_pips = float(os.getenv("DEFAULT_SPREAD_PIPS", "1.5"))
    path_rule = os.getenv("PATH_RULE", "pessimistic").strip().lower()
    if path_rule not in ("pessimistic", "optimistic", "strict"):
        path_rule = "pessimistic"

    for i, row in signals_df.iterrows():
        action = str(row.get("action", "WAIT")).strip().upper()
        if action not in ("BUY", "SELL"):
            continue

        # pair / tf
        pair = (str(row.get("pair", default_pair)) or default_pair).strip().upper()
        tf = (str(row.get("tf", default_tf)) or default_tf).strip().upper()

        # prices
        try:
            entry = float(row["entry_price"])
            sl = float(row["stop_loss"])
            tp1 = float(row["tp1"]); tp2 = float(row["tp2"]); tp3 = float(row["tp3"])
        except Exception as e:
            print(f"⚠ Skipping row {i}: invalid price fields ({e})")
            continue

        # timestamp
        signal_time = row["timestamp"]
        if pd.isna(signal_time):
            print(f"⚠ Skipping row {i}: invalid timestamp")
            continue

        # spread (optional in CSV; fallback to env)
        spread_pips = row.get("spread", "n/a")
        if isinstance(spread_pips, str):
            try:
                spread_pips = float(spread_pips)
            except:
                spread_pips = default_spread_pips
        elif pd.isna(spread_pips):
            spread_pips = default_spread_pips

        pip = pip_size_for(pair)

        # grab forward bars
        future_bars = fetch_future_bars(pair, tf, signal_time, env_horizon)

        if future_bars is None or len(future_bars) == 0:
            result = _result("NONE", "NONE", 0.0, signal_time, entry, 0)
        else:
            # WEEKEND / massive-gap guard (optional soft check)
            # If first future bar is > 2 days away, consider market closed → treat as NONE
            first_future = future_bars.index[0]
            if (first_future - signal_time) > timedelta(days=2, hours=0):
                result = _result("NONE", "GAP>48H", 0.0, first_future, float(future_bars['close'].iloc[0]), _mins(first_future, signal_time))
            else:
                result = simulate_trade(
                    action, entry, sl, tp1, tp2, tp3, signal_time, future_bars,
                    spread_pips=spread_pips, pip=pip, path_rule=path_rule
                )

        trade = {
            "timestamp": signal_time.isoformat(),
            "pair": pair,
            "timeframe": tf,
            "action": action,
            "entry_price": f"{entry:.5f}",
            "stop_loss": f"{sl:.5f}",
            "tp1": f"{tp1:.5f}",
            "tp2": f"{tp2:.5f}",
            "tp3": f"{tp3:.5f}",
            "spread_pips": f"{float(spread_pips):.1f}",
            "outcome": result["outcome"],
            "hit_level": result["hit_level"],
            "R_multiple": f"{result['R_multiple']:.2f}",
            "exit_time": result["exit_time"].isoformat(),
            "exit_price": f"{result['exit_price']:.5f}",
            "duration_minutes": result["duration_minutes"],
            # Carry-through (if present)
            "atr": _safe_str(row.get("atr", "n/a")),
            "score6": _safe_str(row.get("score6", "n/a")),
            "score16": _safe_str(row.get("score16", "n/a")),
            "reason": _safe_str(row.get("reason", "")),
        }
        trades.append(trade)

        if (len(trades) % 10) == 0:
            print(f"  Processed {len(trades)}/{total} tradeable signals...")

    return pd.DataFrame(trades)


def _safe_str(v) -> str:
    if pd.isna(v):
        return "n/a"
    try:
        return str(v)
    except:
        return "n/a"


def print_summary(trades_df: pd.DataFrame):
    """Aggregate stats incl. win rate, average/total R, profit factor, and outcome counts."""
    if len(trades_df) == 0:
        print("\n⚠ No tradeable signals found (all WAIT or invalid)")
        return

    total_signals = len(trades_df)
    completed = trades_df[~trades_df["outcome"].isin(["NONE", "AMBIG", "INVALID"])].copy()
    completed["R_multiple"] = pd.to_numeric(completed["R_multiple"], errors="coerce")

    none_ct = int((trades_df["outcome"] == "NONE").sum())
    ambig_ct = int((trades_df["outcome"] == "AMBIG").sum())
    invalid_ct = int((trades_df["outcome"] == "INVALID").sum())

    print("\n📊 SUMMARY")
    print(f"Total trade rows: {total_signals} | NONE: {none_ct} | AMBIG: {ambig_ct} | INVALID: {invalid_ct}")

    if len(completed) == 0:
        print("⚠ No trades reached SL/TP within horizon")
        return

    wins = int((completed["outcome"] == "WIN").sum())
    losses = int((completed["outcome"] == "LOSS").sum())
    win_rate = (wins / len(completed) * 100.0) if len(completed) > 0 else 0.0

    avg_R = float(completed["R_multiple"].mean())
    total_R = float(completed["R_multiple"].sum())

    win_R = float(completed.loc[completed["outcome"] == "WIN", "R_multiple"].sum())
    loss_R = -float(completed.loc[completed["outcome"] == "LOSS", "R_multiple"].sum())  # make positive
    profit_factor = (win_R / loss_R) if loss_R > 0 else float("inf")

    print(f"Completed trades: {len(completed)} | Wins: {wins} | Losses: {losses}")
    print(f"Win Rate: {win_rate:.1f}%")
    print(f"Average R: {avg_R:.2f} | Total R: {total_R:.2f}")
    print(f"Profit Factor: {profit_factor:.2f}")


def main():
    args = parse_args()

    horizon_env = os.getenv("HORIZON_BARS")
    horizon = int(horizon_env) if horizon_env else args.horizon

    print("🔍 Auditor starting…")
    print(f"  Signals: {args.signals}")
    print(f"  Output : {args.out}")
    print(f"  Horizon: {horizon} bars (override via HORIZON_BARS)")
    print(f"  Defaults: pair={args.pair} tf={args.tf}")
    print()

    # Load signals
    try:
        signals_df = load_signals(args.signals)
    except Exception as e:
        print(f"✗ Failed to load signals: {e}")
        sys.exit(1)

    print(f"✓ Loaded {len(signals_df)} signals")

    # Process & simulate
    trades_df = audit_signals(signals_df, horizon, args.pair, args.tf)

    # Write output
    try:
        trades_df.to_csv(args.out, index=False)
        print(f"\n✓ Wrote {len(trades_df)} trades to {args.out}")
    except Exception as e:
        print(f"✗ Failed to write output: {e}")
        sys.exit(1)

    # Summary
    print_summary(trades_df)


if __name__ == "__main__":
    main()
