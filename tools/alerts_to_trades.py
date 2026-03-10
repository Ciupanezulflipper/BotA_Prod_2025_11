#!/usr/bin/env python3
"""
alerts_to_trades.py — Wire alerts.csv into auditor.py's simulate_trade engine.
Stdlib-only rewrite (no pandas) for Termux compatibility.
"""
import re, os, sys, csv, argparse
from datetime import datetime, timezone

sys.path.insert(0, os.path.expanduser("~"))
sys.path.insert(0, os.path.expanduser("~/BotA"))
from tools.auditor import fetch_future_bars, simulate_trade, pip_size_for


def parse_sl_tp(reasons: str):
    m = re.search(r"SL:([\d.]+),TP:([\d.]+)", str(reasons))
    if m:
        return float(m.group(1)), float(m.group(2))
    return None, None


def parse_ts(s: str):
    s = str(s).strip()
    if not s:
        return None
    try:
        s = s.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--alerts", default="logs/alerts.csv")
    ap.add_argument("--out", default="logs/trades.csv")
    ap.add_argument("--horizon", type=int, default=96)
    ap.add_argument("--spread", type=float, default=1.5)
    ap.add_argument("--since", default="", help="Only process signals after this UTC datetime e.g. 2026-02-24T00:00:00")
    args = ap.parse_args()

    alerts_path = os.path.expanduser(f"~/BotA/{args.alerts}")
    out_path = os.path.expanduser(f"~/BotA/{args.out}")

    since_dt = None
    if args.since:
        since_dt = parse_ts(args.since)

    rows = []
    with open(alerts_path, newline="", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row = {k.strip().lower(): v for k, v in row.items() if k is not None}
            ts = parse_ts(row.get("timestamp", ""))
            if ts is None:
                continue
            row["_ts"] = ts
            if since_dt and ts < since_dt:
                continue
            rows.append(row)

    if since_dt:
        print(f"[since] Filtered to {len(rows)} signals after {since_dt.isoformat()}")

    results = []
    total = len(rows)
    for i, row in enumerate(rows):
        try:
            sl = float(row.get("sl") or 0)
            tp = float(row.get("tp") or 0)
            entry = float(row.get("entry") or row.get("price") or 0)
        except Exception:
            sl, tp, entry = 0, 0, 0

        if not sl or not tp:
            sl, tp = parse_sl_tp(row.get("reasons", ""))
        if not sl or not tp:
            results.append({**row, "outcome": "NO_SL_TP", "pips": 0, "r_multiple": 0})
            continue

        pair = str(row.get("pair", "EURUSD"))
        tf = str(row.get("tf", "M15"))
        direction = str(row.get("direction", "")).upper()
        if not entry or direction not in ("BUY", "SELL"):
            results.append({**row, "outcome": "SKIP", "pips": 0, "r_multiple": 0})
            continue

        bars = fetch_future_bars(pair, tf, row["_ts"], args.horizon)
        if bars is None:
            results.append({**row, "outcome": "NO_DATA", "pips": 0, "r_multiple": 0})
            continue

        try:
            empty = bars.empty
        except AttributeError:
            empty = len(bars) == 0

        if empty:
            results.append({**row, "outcome": "NO_DATA", "pips": 0, "r_multiple": 0})
            continue

        res = simulate_trade(
            action=direction, entry=entry,
            sl=sl, tp1=tp, tp2=tp, tp3=tp,
            signal_time=row["_ts"],
            future_bars=bars,
            spread_pips=args.spread,
            pip=pip_size_for(pair),
            path_rule="pessimistic"
        )
        outcome = res.get("outcome", "UNKNOWN")
        exit_price = res.get("exit_price", entry)
        pip_size = pip_size_for(pair)
        pips = ((exit_price - entry) if direction == "BUY" else (entry - exit_price)) / pip_size
        risk_pips = abs(entry - sl) / pip_size
        r_mult = round(pips / risk_pips, 2) if risk_pips else 0
        results.append({**row, "sl": sl, "tp": tp,
                        "outcome": outcome, "exit_price": exit_price,
                        "pips": round(pips, 1), "r_multiple": r_mult})

        if (i + 1) % 50 == 0:
            print(f"[progress] {i+1}/{total}")

    if not results:
        print("[alerts_to_trades] No results to write.")
        return

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    fieldnames = [f for f in list(results[0].keys()) if f != "_ts"]
    for r in results:
        r.pop("_ts", None)

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)

    wins = sum(1 for r in results if r.get("outcome") == "TP1")
    losses = sum(1 for r in results if r.get("outcome") == "SL")
    total_resolved = wins + losses
    wr = round(wins / total_resolved * 100, 1) if total_resolved else 0
    print(f"[alerts_to_trades] Done. {len(results)} records → {out_path}")
    print(f"[alerts_to_trades] WR={wr}% ({wins}W/{losses}L of {total_resolved} resolved)")


if __name__ == "__main__":
    main()
