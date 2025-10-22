#!/usr/bin/env python3
from __future__ import annotations
import os, csv
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict, Counter
from typing import Dict, Any, List

from tools.news_weight import load_news, apply_news_to_signal, _parse_iso

ISO = "%Y-%m-%dT%H:%M:%SZ"

HOME = Path.home()
LOGS = HOME / "bot-a" / "logs"
DAILY = LOGS / "daily"
DAILY.mkdir(parents=True, exist_ok=True)

def _today_utc():
    return datetime.now(timezone.utc)

def _day_tag(dt: datetime) -> str:
    return dt.strftime("%Y%m%d")

def _load_csv(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        return list(rdr)

def _write_csv(path: Path, rows: List[Dict[str, Any]]):
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        fieldnames = list(rows[0].keys())
        wr = csv.DictWriter(f, fieldnames=fieldnames)
        wr.writeheader()
        for r in rows:
            wr.writerow({k: r.get(k, "") for k in fieldnames})

def main():
    # ENV knobs (safe defaults)
    day = os.getenv("COLLECT_DAY") or _day_tag(_today_utc())
    lookback_min = int(os.getenv("NEWS_LOOKBACK_MIN", "180"))   # last 3h
    base_boost = int(os.getenv("NEWS_BOOST", "10"))             # +/- 10 points
    # files for the day
    sig_file = LOGS / f"signals-{day}.csv"
    news_file = LOGS / f"news-{day}.csv"

    signals = _load_csv(sig_file)
    news = _load_csv(news_file)

    news_by_symbol = load_news(news)

    merged: List[Dict[str, Any]] = []
    for s in signals:
        # normalize bare minimum fields we rely on
        s_symbol = (s.get("symbol") or "").upper()
        s_time = _parse_iso(s.get("time_utc") or s.get("asof_utc") or "")
        if not s_symbol or not s_time:
            continue

        combined_score, combined_side, tag = apply_news_to_signal(
            s, news_by_symbol, lookback_min=lookback_min, base_boost=base_boost
        )

        row = dict(s)  # copy original signal fields
        row["combined_score"] = round(combined_score, 2)
        row["combined_side"] = combined_side
        if tag:
            row["why"] = (s.get("why") or "") + (("" if not s.get("why") else " | ") + tag)
            row["with_news"] = "1"
        else:
            row["with_news"] = "0"

        merged.append(row)

    # write merged file
    merged_out = DAILY / f"merged-{day}.csv"
    _write_csv(merged_out, merged if merged else [])

    # build summary (compact for telegram_summary.py)
    sym_stats: Dict[str, Dict[str, Any]] = {}
    for r in merged:
        sym = (r.get("symbol") or "").upper()
        sym_stats.setdefault(sym, {"count":0,"bull":0,"bear":0,"neut":0,"avg":0.0,"with_news":0})
        st = sym_stats[sym]
        st["count"] += 1
        st["avg"] += float(r.get("combined_score") or 0)
        if r.get("with_news") == "1":
            st["with_news"] += 1
        side = (r.get("combined_side") or "").capitalize()
        if side == "Bullish":
            st["bull"] += 1
        elif side == "Bearish":
            st["bear"] += 1
        else:
            st["neut"] += 1

    summary_rows: List[Dict[str, Any]] = []
    for sym, st in sym_stats.items():
        avg = (st["avg"] / st["count"]) if st["count"] else 0.0
        summary_rows.append({
            "symbol": sym,
            "signals": st["count"],
            "bull": st["bull"],
            "bear": st["bear"],
            "neut": st["neut"],
            "avg_score": round(avg, 2),
            "with_news": st["with_news"],
            "day": day,
        })

    # Always write a summary, even if empty (so telegram can say "0 signals")
    summary_out = DAILY / f"summary-{day}.csv"
    _write_csv(summary_out, summary_rows if summary_rows else [{"symbol":"(none)","signals":0,"bull":0,"bear":0,"neut":0,"avg_score":0.0,"with_news":0,"day":day}])

    # Optional: send a short collector notice when run from cron with --telegram flag.
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--telegram", action="store_true")
    args = ap.parse_args()

    if args.telegram:
        chat = (os.getenv("TELEGRAM_CHAT_ID") or "").strip()
        token = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
        if chat and token:
            msg = (
                f"📦 Nightly collector — {day}\n"
                f"Signals: {len(merged)}  •  News: {len(news)}\n"
                f"Merged:  {merged_out}\n"
                f"Summary: {summary_out}"
            )
            try:
                import json, urllib.request
                url = f"https://api.telegram.org/bot{token}/sendMessage"
                data = json.dumps({"chat_id": int(chat), "text": msg}).encode("utf-8")
                req = urllib.request.Request(url, data=data, headers={"Content-Type":"application/json"})
                with urllib.request.urlopen(req, timeout=15) as resp:
                    _ = resp.read()
            except Exception:
                pass

    print({"day": day, "signals_file": str(sig_file), "news_file": str(news_file),
           "merged_out": str(merged_out), "summary_out": str(summary_out)})

if __name__ == "__main__":
    raise SystemExit(main())
