#!/usr/bin/env python3
"""
BotA Signal Closer
==================
Reads ACTIVE signals from Supabase, fetches current candle data,
checks if TP or SL was hit, and updates signal status accordingly.

Rules:
- If price hit TP -> status=CLOSED, result_pips=positive
- If price hit SL -> status=CLOSED, result_pips=negative
- If signal older than MAX_AGE_HOURS -> status=CANCELLED, result_pips=0
"""

from __future__ import annotations
import os, sys, json, pathlib, argparse, urllib.request, urllib.parse
from datetime import datetime, timezone, timedelta

ROOT = pathlib.Path(__file__).resolve().parent.parent

SUPABASE_URL  = os.environ.get("SUPABASE_URL", "https://ozgkeslgjqbqfewojnmr.supabase.co")
SUPABASE_KEY  = os.environ.get("SUPABASE_SERVICE_KEY", "")
MAX_AGE_HOURS = int(os.environ.get("SIGNAL_MAX_AGE_HOURS", "24"))
LOG_FILE      = ROOT / "logs" / "signal_closer.log"

def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    line = f"[CLOSER {ts}] {msg}"
    print(line)
    try:
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass

def pip_size(pair: str) -> float:
    return 0.01 if "JPY" in pair.upper() else 0.0001

def pips(diff: float, pair: str) -> float:
    return round(diff / pip_size(pair), 1)

def supabase_request(method: str, path: str, body: dict = None) -> dict:
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    data = json.dumps(body).encode() if body else None
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())

def get_active_signals() -> list:
    path = "signals?status=eq.ACTIVE&select=id,pair,direction,entry_price,stop_loss,take_profit,created_at,timeframe"
    return supabase_request("GET", path)

def fetch_candles(pair: str, signal_time: datetime) -> list:
    try:
        symbol = pair.upper() + "=X"
        period1 = int(signal_time.timestamp())
        period2 = int(datetime.now(timezone.utc).timestamp())
        url = (
            f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}"
            f"?interval=15m&period1={period1}&period2={period2}"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
        result = data.get("chart", {}).get("result", [])
        if not result:
            return []
        r = result[0]
        timestamps = r.get("timestamp", [])
        quotes = r.get("indicators", {}).get("quote", [{}])[0]
        candles = []
        for i, ts in enumerate(timestamps):
            try:
                h = quotes.get("high", [])[i]
                l = quotes.get("low", [])[i]
                if h is not None and l is not None:
                    candles.append({"t": ts, "h": float(h), "l": float(l)})
            except Exception:
                continue
        return candles
    except Exception as e:
        log(f"ERROR fetching candles for {pair}: {e}")
        return []

def check_outcome(direction: str, entry: float, sl: float, tp: float,
                  candles: list, pair: str):
    direction = direction.upper()
    for bar in candles:
        h, l = bar["h"], bar["l"]
        if direction == "BUY":
            if h >= tp:
                return "WIN", pips(tp - entry, pair)
            if l <= sl:
                return "LOSS", pips(sl - entry, pair)
        elif direction == "SELL":
            if l <= tp:
                return "WIN", pips(entry - tp, pair)
            if h >= sl:
                return "LOSS", pips(entry - sl, pair)
    return "OPEN", 0.0

def close_signal(signal_id: str, status: str, result_pips: float, dry_run: bool):
    now = datetime.now(timezone.utc).isoformat()
    body = {
        "status": status,
        "result_pips": round(result_pips, 1),
        "closed_at": now,
    }
    if dry_run:
        log(f"DRY-RUN: would update {signal_id} -> {status} {result_pips:+.1f} pips")
        return
    try:
        path = f"signals?id=eq.{signal_id}"
        supabase_request("PATCH", path, body)
        log(f"CLOSED {signal_id} -> {status} {result_pips:+.1f} pips")
    except Exception as e:
        log(f"ERROR closing {signal_id}: {e}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not SUPABASE_KEY:
        log("ERROR: SUPABASE_SERVICE_KEY not set")
        sys.exit(1)

    log(f"Starting signal closer (max_age={MAX_AGE_HOURS}h, dry_run={args.dry_run})")

    try:
        signals = get_active_signals()
    except Exception as e:
        log(f"ERROR fetching active signals: {e}")
        sys.exit(1)

    log(f"Found {len(signals)} ACTIVE signals")

    now = datetime.now(timezone.utc)
    closed = cancelled = still_open = 0

    for sig in signals:
        sig_id    = sig["id"]
        pair      = sig["pair"]
        direction = sig["direction"]
        entry     = float(sig["entry_price"])
        sl        = float(sig["stop_loss"])
        tp        = float(sig["take_profit"])
        created   = datetime.fromisoformat(sig["created_at"].replace("Z", "+00:00"))
        age_hours = (now - created).total_seconds() / 3600

        if age_hours >= MAX_AGE_HOURS:
            log(f"EXPIRED {pair} {direction} entry={entry} age={age_hours:.1f}h -> CANCELLED")
            close_signal(sig_id, "CANCELLED", 0.0, args.dry_run)
            cancelled += 1
            continue

        candles = fetch_candles(pair, created)
        if not candles:
            log(f"WARN: no candles for {pair} {direction} entry={entry} — skipping")
            still_open += 1
            continue

        outcome, result_pips = check_outcome(direction, entry, sl, tp, candles, pair)

        if outcome in ("WIN", "LOSS"):
            log(f"{outcome} {pair} {direction} entry={entry} -> {result_pips:+.1f} pips")
            close_signal(sig_id, "CLOSED", result_pips, args.dry_run)
            closed += 1
        else:
            log(f"OPEN {pair} {direction} entry={entry} age={age_hours:.1f}h — still active")
            still_open += 1

    log(f"Done — closed={closed} cancelled={cancelled} still_open={still_open}")

if __name__ == "__main__":
    main()
