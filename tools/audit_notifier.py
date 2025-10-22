#!/usr/bin/env python3

"""
Runs the signal auditor, then posts the markdown summary to Telegram.
- Respects VERIFY_SSL via telegramalert.
- Skips send if there are no signals or the summary is empty.
ENV knobs (optional):
  SIGNALS_CSV   defaults to ~/BotA/logs/signals.csv
  SUMMARY_MD    defaults to ~/BotA/logs/audit_summary.md
  AUDIT_PAIR    defaults to EURUSD
  AUDIT_TF      defaults to M15
  AUDIT_LOOKAHEAD_BARS defaults to 96 (24h on M15)
"""

import os
import sys
import subprocess
from pathlib import Path

DEFAULT_SIGNALS = str(Path("~/BotA/logs/signals.csv").expanduser())
DEFAULT_SUMMARY = str(Path("~/BotA/logs/audit_summary.md").expanduser())

def run_auditor() -> int:
    # Invoke as a module so we don’t depend on internal functions
    cmd = [sys.executable, "-m", "BotA.tools.signal_auditor"]
    env = os.environ.copy()
    return subprocess.call(cmd, env=env)

def read_summary() -> str:
    path = os.getenv("SUMMARY_MD", DEFAULT_SUMMARY)
    p = Path(path).expanduser()
    if not p.exists():
        return ""
    try:
        return p.read_text(encoding="utf-8").strip()
    except Exception:
        return ""

def signals_exist() -> bool:
    path = os.getenv("SIGNALS_CSV", DEFAULT_SIGNALS)
    return Path(path).expanduser().exists()

def send_telegram(md: str) -> bool:
    try:
        from BotA.tools.telegramalert import send_telegram_message
    except Exception as e:
        print(f"✗ telegram module error: {e}")
        return False
    # Telegram supports Markdown; the report is markdown-safe.
    ok, err = send_telegram_message(md)
    if not ok:
        print(f"✗ Telegram send failed: {err}")
    else:
        print("✓ Audit summary sent to Telegram")
    return ok

def main():
    if not signals_exist():
        print("ℹ No signals.csv yet — skipping auditor send.")
        sys.exit(0)

    rc = run_auditor()
    if rc != 0:
        print(f"✗ Auditor exited with code {rc}")
        sys.exit(rc)

    md = read_summary()
    if not md:
        print("ℹ audit_summary.md is empty — nothing to send.")
        sys.exit(0)

    send_telegram(md)

if __name__ == "__main__":
    main()
