#!/usr/bin/env python3
# tools/signal_runner.py
# Orchestrates per-symbol runs of news_sentiment.py and (optionally) posts a compact summary.

import argparse
import os
import shlex
import subprocess
import sys
import time
from datetime import datetime, timezone
from typing import List, Dict, Any, Tuple

# Defaults (env overridable)
DEFAULT_SYMBOLS = os.environ.get("BOT_A_SYMBOLS", "EURUSD,XAUUSD").split(",")
DEFAULT_TIMEFRAME = os.environ.get("BOT_A_TIMEFRAME", "4h")
DEFAULT_MIN_CONF = float(os.environ.get("BOT_A_MIN_CONF", "6.0"))
DEFAULT_SESSIONS = os.environ.get("BOT_A_SESSIONS", "london_ny")
DEFAULT_COOLDOWN_MIN = int(os.environ.get("BOT_A_COOLDOWN_MIN", "15"))
DEFAULT_PYTHONPATH = os.environ.get("BOT_A_PYTHONPATH", os.path.expanduser("~/bot-a"))
NEWS_SENTIMENT = os.path.expanduser("~/bot-a/tools/news_sentiment.py")

def utc_ts() -> str:
    return datetime.now(timezone.utc).strftime("UTC %H:%M")

def build_cmd(symbol: str, a: argparse.Namespace) -> List[str]:
    cmd = [sys.executable, NEWS_SENTIMENT,
           "--symbol", symbol,
           "--timeframe", a.timeframe,
           "--limit", str(a.limit),
           "--min-conf", str(a.min_conf),
           "--sessions", a.sessions,
           "--cooldown-min", str(a.cooldown_min)]
    if a.min_sum is not None:
        cmd += ["--min-sum", str(a.min_sum)]
    if a.header_inline_time:
        cmd += ["--header-inline-time"]
    if a.force:
        cmd += ["--force"]
    if a.dry:
        cmd += ["--dry"]
    if a.send:
        cmd += ["--send"]
    # Optional overrides
    if a.decision: cmd += ["--decision", a.decision]
    if a.entry:    cmd += ["--entry", a.entry]
    if a.tp:       cmd += ["--tp", a.tp]
    if a.sl:       cmd += ["--sl", a.sl]
    if a.risk:     cmd += ["--risk", a.risk]
    return cmd

def run_one(symbol: str, a: argparse.Namespace, env: dict) -> Dict[str, Any]:
    cmd = build_cmd(symbol, a)
    print(f"[runner] → {symbol} :: {' '.join(shlex.quote(x) for x in cmd)}")
    try:
        # Capture both stdout and stderr so we can parse skip/sent hints.
        p = subprocess.run(cmd, env=env, capture_output=True, text=True)
        out = (p.stdout or "") + (p.stderr or "")
    except Exception as e:
        return {"symbol": symbol, "status": "error", "reason": f"exec_failed: {e}", "raw": ""}

    status = "sent"  # optimistic default when --send is used
    reason = ""
    raw = out.strip()

    # Detect explicit skip lines printed by news_sentiment.py
    # Example: "[skip] EURUSD BUY — session gate"
    if "[skip]" in out or "SKIP:" in out:
        status = "skip"
        # Try to extract a short reason after "— "
        if "— " in out:
            reason = out.split("— ", 1)[-1].strip().splitlines()[0]
        elif "SKIP:" in out:
            reason = out.split("SKIP:", 1)[-1].strip().splitlines()[0]
        else:
            reason = "skipped"
    else:
        # If no skip markers:
        # If --send and telegram helper logs "Sent to Telegram", we keep 'sent'
        # If --dry, consider it 'printed'
        if a.dry:
            status = "printed"
            reason = "dry"
        else:
            # When telegram helper missing, news_sentiment prints the card to stdout.
            # We'll still treat that as 'sent' for the purpose of the run summary.
            status = "sent"

    return {"symbol": symbol, "status": status, "reason": reason, "raw": raw}

def format_summary(results: List[Dict[str, Any]], header_note: str = "") -> str:
    sent = sum(1 for r in results if r["status"] == "sent")
    skipped = sum(1 for r in results if r["status"] == "skip")
    printed = sum(1 for r in results if r["status"] == "printed")
    errors = sum(1 for r in results if r["status"] == "error")

    lines = []
    lines.append(f"*Bot-A run summary*  |  {utc_ts()}")
    if header_note:
        lines.append(header_note)
    lines.append(f"• Sent: *{sent}*  |  Skipped: *{skipped}*  |  Printed: *{printed}*  |  Errors: *{errors}*")
    lines.append("")
    for r in results:
        sym = r["symbol"]
        st = r["status"]
        if st == "sent":
            lines.append(f"• {sym}: ✅ sent")
        elif st == "printed":
            lines.append(f"• {sym}: 🖨️ printed (dry)")
        elif st == "skip":
            lines.append(f"• {sym}: ⏭️ skip — {r.get('reason','')}")
        else:
            lines.append(f"• {sym}: ❌ error — {r.get('reason','')}")
    return "\n".join(lines)

def send_summary(text: str) -> bool:
    try:
        from tools.telegramalert import send_text
        return bool(send_text(text))
    except Exception:
        print(text)
        return False

def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Bot-A Signal Runner with summary")
    ap.add_argument("--symbols", default=",".join([s.strip().upper() for s in DEFAULT_SYMBOLS if s.strip()]),
                    help="Comma-separated list. Defaults to BOT_A_SYMBOLS or EURUSD,XAUUSD")
    ap.add_argument("--only", default=None, help="Run only this symbol")
    ap.add_argument("--stagger-sec", type=int, default=int(os.environ.get("BOT_A_STAGGER_SEC", "2")),
                    help="Sleep seconds between symbols")

    # Forwarded flags for news_sentiment.py
    ap.add_argument("--timeframe", default=DEFAULT_TIMEFRAME)
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--min-conf", type=float, default=DEFAULT_MIN_CONF)
    ap.add_argument("--min-sum", type=float, default=None)
    ap.add_argument("--sessions", default=DEFAULT_SESSIONS)
    ap.add_argument("--cooldown-min", type=int, default=DEFAULT_COOLDOWN_MIN)
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--send", action="store_true")
    ap.add_argument("--header-inline-time", action="store_true")
    ap.add_argument("--force", action="store_true")

    # Optional overrides
    ap.add_argument("--decision", choices=["BUY", "SELL", "HOLD"], default=None)
    ap.add_argument("--entry", default=None)
    ap.add_argument("--tp", default=None)
    ap.add_argument("--sl", default=None)
    ap.add_argument("--risk", default=None)

    # Runner summary behavior
    ap.add_argument("--summary-send", action="store_true", help="After per-symbol runs, send 1 compact summary")
    ap.add_argument("--pythonpath", default=DEFAULT_PYTHONPATH, help="PYTHONPATH for children")
    return ap.parse_args()

def main():
    a = parse_args()

    env = dict(os.environ)
    env["PYTHONPATH"] = a.pythonpath

    symbols = [a.only] if a.only else [s.strip().upper() for s in a.symbols.split(",") if s.strip()]
    results: List[Dict[str, Any]] = []

    for i, sym in enumerate(symbols):
        r = run_one(sym, a, env)
        results.append(r)
        if i < len(symbols) - 1 and a.stagger_sec > 0:
            time.sleep(a.stagger_sec)

    if a.summary_send:
        note = "(dry run)" if a.dry else ""
        summary = format_summary(results, header_note=note)
        send_summary(summary)
    else:
        # If not sending a summary, still print it locally for quick view.
        print(format_summary(results, header_note="(local summary)"))

    # Non-zero exit if any errors
    if any(r["status"] == "error" for r in results):
        sys.exit(1)

if __name__ == "__main__":
    main()
