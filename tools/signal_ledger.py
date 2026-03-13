#!/usr/bin/env python3
"""
BotA Signal Quality Ledger
==========================
Reads alerts.csv, fetches post-signal candles, determines TP/SL outcome,
calculates win rate, avg pips, and suggests tighter SL/TP multipliers.

Usage:
  python3 tools/signal_ledger.py
  python3 tools/signal_ledger.py --lookback 48
  python3 tools/signal_ledger.py --report

Output:
  data/ledger.csv        — per-signal outcome record
  data/ledger_report.txt — summary report with SL/TP recommendations
"""

from __future__ import annotations
import os, sys, csv, json, pathlib, argparse, statistics
from datetime import datetime, timezone, timedelta
from typing import Optional

ROOT = pathlib.Path(__file__).resolve().parent.parent
ALERTS_CSV  = ROOT / "logs" / "alerts.csv"
LEDGER_CSV  = ROOT / "data" / "ledger.csv"
REPORT_FILE = ROOT / "data" / "ledger_report.txt"
CACHE_DIR   = ROOT / "cache"

COL_TIMESTAMP  = 0
COL_PAIR       = 1
COL_TF         = 2
COL_DIRECTION  = 3
COL_SCORE      = 4
COL_ENTRY      = 6
COL_SL         = 7
COL_TP         = 8
COL_REJECTED   = 10

LEDGER_HEADER = [
    "timestamp", "pair", "tf", "direction", "score",
    "entry", "sl", "tp",
    "sl_pips", "tp_pips", "rr_ratio",
    "outcome",
    "result_pips",
    "bars_to_close",
    "max_adverse",
    "max_favorable",
]

def pip_size(pair: str) -> float:
    pair = pair.upper()
    if "JPY" in pair:
        return 0.01
    return 0.0001

def pips(price_diff: float, pair: str) -> float:
    return round(price_diff / pip_size(pair), 1)

def fetch_candles_after(pair: str, tf: str, signal_time: datetime, lookback_hours: int) -> list:
    try:
        import urllib.request, urllib.parse
        tf_map = {"M15": "15m", "M5": "5m", "H1": "1h", "H4": "1h", "D1": "1d"}
        interval = tf_map.get(tf.upper(), "15m")
        symbol = pair.upper() + "=X"
        period1 = int(signal_time.timestamp())
        period2 = int((signal_time + timedelta(hours=lookback_hours)).timestamp())
        url = (
            f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}"
            f"?interval={interval}&period1={period1}&period2={period2}"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        result = data.get("chart", {}).get("result", [])
        if not result:
            return []
        r = result[0]
        timestamps = r.get("timestamp", [])
        quotes = r.get("indicators", {}).get("quote", [{}])[0]
        opens  = quotes.get("open",  [])
        highs  = quotes.get("high",  [])
        lows   = quotes.get("low",   [])
        closes = quotes.get("close", [])
        candles = []
        for i, ts in enumerate(timestamps):
            try:
                candles.append({
                    "t": ts,
                    "o": float(opens[i])  if opens[i]  is not None else None,
                    "h": float(highs[i])  if highs[i]  is not None else None,
                    "l": float(lows[i])   if lows[i]   is not None else None,
                    "c": float(closes[i]) if closes[i] is not None else None,
                })
            except Exception:
                continue
        return [c for c in candles if all(v is not None for v in c.values())]
    except Exception:
        return []

def evaluate_outcome(direction: str, entry: float, sl: float, tp: float,
                     candles: list, pair: str):
    if not candles:
        return "UNKNOWN", 0.0, 0, 0.0, 0.0
    direction = direction.upper()
    max_adv = 0.0
    max_fav = 0.0
    for i, bar in enumerate(candles):
        h = bar["h"]
        l = bar["l"]
        if direction == "BUY":
            if h >= tp:
                return "WIN", pips(tp - entry, pair), i + 1, pips(max_adv, pair), pips(tp - entry, pair)
            if l <= sl:
                return "LOSS", pips(sl - entry, pair), i + 1, pips(entry - sl, pair), pips(max_fav, pair)
            max_fav = max(max_fav, h - entry)
            max_adv = max(max_adv, entry - l)
        elif direction == "SELL":
            if l <= tp:
                return "WIN", pips(entry - tp, pair), i + 1, pips(max_adv, pair), pips(entry - tp, pair)
            if h >= sl:
                return "LOSS", pips(entry - sl, pair), i + 1, pips(sl - entry, pair), pips(max_fav, pair)
            max_fav = max(max_fav, entry - l)
            max_adv = max(max_adv, h - entry)
    return "OPEN", 0.0, len(candles), pips(max_adv, pair), pips(max_fav, pair)

def load_alerts(path: pathlib.Path) -> list:
    signals = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) < 11:
                continue
            rejected = row[COL_REJECTED].strip().lower()
            if rejected == "true":
                continue
            try:
                ts = datetime.fromisoformat(row[COL_TIMESTAMP].strip())
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                signals.append({
                    "timestamp":  ts,
                    "pair":       row[COL_PAIR].strip().upper(),
                    "tf":         row[COL_TF].strip().upper(),
                    "direction":  row[COL_DIRECTION].strip().upper(),
                    "score":      float(row[COL_SCORE].strip()),
                    "entry":      float(row[COL_ENTRY].strip()),
                    "sl":         float(row[COL_SL].strip()),
                    "tp":         float(row[COL_TP].strip()),
                })
            except Exception:
                continue
    return signals

def load_existing_ledger(path: pathlib.Path) -> set:
    seen = set()
    if not path.exists():
        return seen
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = f"{row['timestamp']}|{row['pair']}|{row['direction']}"
            seen.add(key)
    return seen

def write_ledger_row(path: pathlib.Path, row: dict):
    write_header = not path.exists()
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=LEDGER_HEADER)
        if write_header:
            writer.writeheader()
        writer.writerow(row)

def generate_report(ledger_path: pathlib.Path) -> str:
    if not ledger_path.exists():
        return "No ledger data yet."
    rows = []
    with open(ledger_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    if not rows:
        return "Ledger is empty."
    closed = [r for r in rows if r["outcome"] in ("WIN", "LOSS")]
    wins   = [r for r in closed if r["outcome"] == "WIN"]
    losses = [r for r in closed if r["outcome"] == "LOSS"]
    open_  = [r for r in rows if r["outcome"] == "OPEN"]
    win_rate = len(wins) / len(closed) * 100 if closed else 0
    result_pips = [float(r["result_pips"]) for r in closed]
    avg_result = statistics.mean(result_pips) if result_pips else 0
    total_pips = sum(result_pips)
    sl_pips_wins = [float(r["sl_pips"]) for r in wins if r["sl_pips"]]
    tp_pips_wins = [float(r["tp_pips"]) for r in wins if r["tp_pips"]]
    mae_wins     = [float(r["max_adverse"]) for r in wins if r["max_adverse"]]
    lines = [
        "=" * 60,
        "BotA SIGNAL QUALITY LEDGER REPORT",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "=" * 60,
        "",
        "── OVERVIEW ──────────────────────────────────────────────",
        f"  Total signals:     {len(rows)}",
        f"  Closed (TP/SL):    {len(closed)}",
        f"  Open (pending):    {len(open_)}",
        f"  Wins:              {len(wins)}",
        f"  Losses:            {len(losses)}",
        f"  Win rate:          {win_rate:.1f}%",
        f"  Total pips:        {total_pips:+.1f}",
        f"  Avg result/signal: {avg_result:+.1f} pips",
        "",
        "── SL/TP QUALITY ─────────────────────────────────────────",
    ]
    if mae_wins:
        avg_mae = statistics.mean(mae_wins)
        max_mae = max(mae_wins)
        lines += [
            f"  Avg max adverse (winning trades): {avg_mae:.1f} pips",
            f"  Max adverse seen on a winner:     {max_mae:.1f} pips",
            f"  => SL tighter than {max_mae:.1f} pips would have stopped winners early",
        ]
    if sl_pips_wins:
        lines += [f"  Avg SL distance (wins): {statistics.mean(sl_pips_wins):.1f} pips"]
    if tp_pips_wins:
        lines += [f"  Avg TP distance (wins): {statistics.mean(tp_pips_wins):.1f} pips"]
    if sl_pips_wins and tp_pips_wins:
        rr_wins = [float(r["rr_ratio"]) for r in wins if r["rr_ratio"]]
        if rr_wins:
            lines += [f"  Avg R:R on winners: {statistics.mean(rr_wins):.2f}"]
    lines += ["", "── PER PAIR ───────────────────────────────────────────────"]
    for pair in sorted(set(r["pair"] for r in rows)):
        pair_closed = [r for r in closed if r["pair"] == pair]
        pair_wins   = [r for r in pair_closed if r["outcome"] == "WIN"]
        wr = len(pair_wins) / len(pair_closed) * 100 if pair_closed else 0
        pp = sum(float(r["result_pips"]) for r in pair_closed)
        lines.append(f"  {pair}: {len(pair_closed)} closed | WR={wr:.0f}% | {pp:+.1f} pips")
    lines += ["", "── RECOMMENDATIONS ────────────────────────────────────────"]
    if mae_wins:
        avg_mae = statistics.mean(mae_wins)
        if avg_mae < 10:
            lines.append("  OK SL distance looks reasonable for M15 scalping")
        elif avg_mae > 15:
            lines.append("  WARNING High adverse excursion — consider tighter entry timing")
    if win_rate >= 60:
        lines.append("  OK Win rate above 60% — strategy performing well")
    elif win_rate >= 50:
        lines.append("  WATCH Win rate 50-60% — monitor for 20+ more signals")
    elif closed:
        lines.append("  ALERT Win rate below 50% — review signal filters")
    if total_pips > 0:
        lines.append(f"  OK Net positive: +{total_pips:.1f} pips total")
    elif closed:
        lines.append(f"  ALERT Net negative: {total_pips:.1f} pips — review SL/TP sizing")
    lines += ["", "=" * 60]
    return "\n".join(lines)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lookback", type=int, default=24,
                    help="Hours after signal to check for TP/SL hit (default 24)")
    ap.add_argument("--report", action="store_true",
                    help="Print existing report without fetching new data")
    args = ap.parse_args()
    if args.report:
        print(generate_report(LEDGER_CSV))
        return
    if not ALERTS_CSV.exists():
        print(f"[ledger] ERROR alerts.csv not found at {ALERTS_CSV}", file=sys.stderr)
        sys.exit(1)
    signals  = load_alerts(ALERTS_CSV)
    existing = load_existing_ledger(LEDGER_CSV)
    print(f"[ledger] Found {len(signals)} sent signals in alerts.csv")
    new_count = 0
    for sig in signals:
        key = f"{sig['timestamp'].isoformat()}|{sig['pair']}|{sig['direction']}"
        if key in existing:
            continue
        pair      = sig["pair"]
        direction = sig["direction"]
        entry     = sig["entry"]
        sl        = sig["sl"]
        tp        = sig["tp"]
        sl_p      = abs(pips(entry - sl, pair))
        tp_p      = abs(pips(entry - tp, pair))
        rr        = round(tp_p / sl_p, 2) if sl_p else 0
        print(f"[ledger] Processing {pair} {direction} @ {sig['timestamp'].strftime('%m-%d %H:%M')} ...", end=" ", flush=True)
        candles = fetch_candles_after(pair, sig["tf"], sig["timestamp"], args.lookback)
        outcome, result_pips, bars, max_adv, max_fav = evaluate_outcome(
            direction, entry, sl, tp, candles, pair
        )
        print(f"{outcome} {result_pips:+.1f} pips ({bars} bars)")
        row = {
            "timestamp":     sig["timestamp"].isoformat(),
            "pair":          pair,
            "tf":            sig["tf"],
            "direction":     direction,
            "score":         sig["score"],
            "entry":         entry,
            "sl":            sl,
            "tp":            tp,
            "sl_pips":       round(sl_p, 1),
            "tp_pips":       round(tp_p, 1),
            "rr_ratio":      rr,
            "outcome":       outcome,
            "result_pips":   round(result_pips, 1),
            "bars_to_close": bars,
            "max_adverse":   max_adv,
            "max_favorable": max_fav,
        }
        write_ledger_row(LEDGER_CSV, row)
        new_count += 1
    print(f"\n[ledger] Processed {new_count} new signals")
    print(f"[ledger] Ledger saved to {LEDGER_CSV}")
    report = generate_report(LEDGER_CSV)
    print("\n" + report)
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"[ledger] Report saved to {REPORT_FILE}")

if __name__ == "__main__":
    main()
