#!/usr/bin/env python3
# tools/nightly_digest.py
# Build a daily summary from signal logs and optionally send to Telegram.

import argparse, sys
from datetime import datetime, timezone, timedelta

from tools.signal_logger import summarize_day
# Optional Telegram helper
def send_to_telegram(text: str) -> bool:
    try:
        from tools.telegramalert import send_text
        send_text(text)
        return True
    except Exception as e:
        sys.stderr.write(f"[digest] Telegram send not available: {e}\n")
        print(text)
        return False

def format_digest(summary: dict) -> str:
    day = summary["day"]
    lines = []
    lines.append(f"*Bot-A Nightly Digest*  —  {day}")
    lines.append(f"• Total events: *{summary['total']}*")
    lines.append(f"• Sent: *{summary['sent']}*  |  Skipped: *{summary['skipped']}*  |  Errors: *{summary['errors']}*")
    lines.append("")
    if summary["by_symbol"]:
        lines.append("*By symbol*")
        for sym, counts in summary["by_symbol"].items():
            lines.append(f"• {sym}: send *{counts.get('send',0)}*, skip *{counts.get('skip',0)}*, err *{counts.get('error',0)}*")
    if summary["skip_reasons"]:
        lines.append("")
        lines.append("*Top skip reasons*")
        for reason, n in summary["skip_reasons"][:6]:
            lines.append(f"• {reason} — *{n}*")
    return "\n".join(lines)

def parse_args():
    ap = argparse.ArgumentParser(description="Nightly digest for Bot-A")
    ap.add_argument("--day", default=None, help='Day to summarize (YYYY-MM-DD). Default: today (UTC).')
    ap.add_argument("--yesterday", action="store_true", help="Summarize yesterday (UTC).")
    ap.add_argument("--send", action="store_true", help="Send to Telegram if available.")
    return ap.parse_args()

def main():
    args = parse_args()
    if args.yesterday and not args.day:
        day = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
    else:
        day = args.day  # could be None -> summarize_day handles
    summary = summarize_day(day)
    text = format_digest(summary)
    if args.send:
        ok = send_to_telegram(text)
        if ok:
            sys.stderr.write("[digest] Sent to Telegram.\n")
    else:
        print(text)

if __name__ == "__main__":
    main()
