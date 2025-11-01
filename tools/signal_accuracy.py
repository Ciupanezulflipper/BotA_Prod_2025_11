#!/data/data/com.termux/files/usr/bin/python3
# FILE: tools/signal_accuracy.py
# MODE: MANUAL SMOKE — log-only; NO Telegram output; safe if triggered by cron.

import os, sys, time, csv, json, pathlib, datetime

ROOT = pathlib.Path(__file__).resolve().parents[1]
LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
ACC_LOG = LOG_DIR / "cron.accuracy.log"
ALERTS = ROOT / "logs" / "alerts.csv"

def log(msg: str):
    ts = datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z"
    with open(ACC_LOG, "a", encoding="utf-8") as f:
        f.write(f"[ACCURACY {ts}] {msg}\n")

def main():
    log("START (manual/log-only stub). Telegram is DISABLED in this build.")
    if not ALERTS.exists():
        log("alerts.csv missing; nothing to evaluate.")
        return 0

    try:
        with open(ALERTS, "r", encoding="utf-8") as f:
            rows = list(csv.reader(f))
    except Exception as e:
        log(f"ERROR reading alerts.csv: {e}")
        return 1

    if len(rows) <= 1:
        log("alerts.csv has header only; no rows to score.")
        return 0

    last = rows[-1]
    # timestamp,pair,timeframe,verdict,score,confidence,reasons,price,provider
    try:
        pair, tf, verdict, score, provider = last[1], last[2], last[3], float(last[4]), last[8]
    except Exception:
        pair, tf, verdict, score, provider = "UNKNOWN", "H1", "HOLD", 0.0, "unknown"

    # Purely log a summary; NO network, NO Telegram.
    log(f"summary pair={pair} tf={tf} verdict={verdict} score={score} provider={provider} (log-only)")
    log("END")
    return 0

if __name__ == "__main__":
    sys.exit(main())
