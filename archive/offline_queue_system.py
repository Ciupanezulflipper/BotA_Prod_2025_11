#!/usr/bin/env python3
"""
Offline Queue System - Critical for 6-hour dinner gap
Saves signals when no internet, sends when reconnected

GOALS:
- Zero deprecated datetime.utcnow() usage (Python 3.12+)
- Preserve ALL existing timestamp string formats:
  - filename: "%Y%m%d_%H%M%S"
  - summary:  "%Y-%m-%d %H:%M" + " UTC"
  - test_signal timestamp: "%Y-%m-%d %H:%M:%S"
- Keep CLI behavior:
  - python3 offline_queue_system.py send
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import subprocess
import hashlib
from pathlib import Path
import datetime as dt

import requests

# --- UTC helpers (timezone-aware; avoids datetime.utcnow() DeprecationWarning) ---
UTC = getattr(dt, "UTC", dt.timezone.utc)


def _utc_now() -> dt.datetime:
    return dt.datetime.now(UTC)


def _utc_strftime(fmt: str) -> str:
    return _utc_now().strftime(fmt)


# --- Repo paths ---
ROOT = Path(__file__).resolve().parents[1]  # .../BotA
QUEUE_DIR = ROOT / "queue"
QUEUE_DIR.mkdir(parents=True, exist_ok=True)


def atomic_write(filepath: Path | str, data: str) -> None:
    """Write atomically to prevent corruption (safe for power loss / interrupts)."""
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp_", suffix=".partial")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        shutil.move(tmp_path, str(path))
    except Exception:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
        raise


def is_online() -> bool:
    """Quick check if internet is available."""
    try:
        requests.get("https://www.google.com", timeout=3)
        return True
    except Exception:
        return False


def cleanup_old_signals(max_signals: int = 100) -> None:
    """Keep only the most recent signals to prevent overflow."""
    try:
        signals = sorted(
            QUEUE_DIR.glob("signal_*.json"),
            key=lambda p: p.stat().st_mtime if p.exists() else 0.0,
        )
    except Exception:
        return

    if len(signals) <= max_signals:
        return

    to_delete = signals[:-max_signals]
    deleted = 0
    for file in to_delete:
        try:
            file.unlink()
            print(f"🗑️ Deleted old signal: {file.name}")
            deleted += 1
        except Exception:
            pass

    if deleted:
        print(f"✅ Cleaned up {deleted} old signals")


def queue_signal(signal_data: dict) -> None:
    """
    Save signal to queue when offline.
    """
    cleanup_old_signals(100)

    stamp = str(signal_data.get("timestamp", ""))
    pair = str(signal_data.get("pair", ""))
    action = str(signal_data.get("action", ""))
    entry = str(signal_data.get("entry", ""))
    raw = f"{stamp}|{pair}|{action}|{entry}".encode("utf-8", errors="ignore")
    signal_id = hashlib.sha256(raw).hexdigest()[:16]
    signal_data["signal_id"] = signal_id

    # Preserve EXACT prior filename timestamp format
    timestamp = _utc_strftime("%Y%m%d_%H%M%S")
    filename = QUEUE_DIR / f"signal_{timestamp}.json"

    atomic_write(filename, json.dumps(signal_data, indent=2, ensure_ascii=False))

    print(f"📥 Queued offline: {filename.name}")

    # Also log to text file for easy reading
    log_file = QUEUE_DIR / "offline_signals.log"
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"\n{'='*60}\n")
            f.write(f"Time: {signal_data.get('timestamp','')}\n")
            f.write(f"Action: {signal_data.get('action','')} {signal_data.get('pair','')}\n")
            f.write(f"Entry: {signal_data.get('entry','')}\n")

            sl = signal_data.get("sl", "")
            tp = signal_data.get("tp", "")
            reason = signal_data.get("reason", "")

            try:
                sl_pips = float(signal_data.get("sl_pips", 0.0))
            except Exception:
                sl_pips = 0.0
            try:
                tp_pips = float(signal_data.get("tp_pips", 0.0))
            except Exception:
                tp_pips = 0.0
            try:
                vol = float(signal_data.get("volatility", 0.0))
            except Exception:
                vol = 0.0

            f.write(f"SL: {sl} (-{sl_pips:.1f} pips)\n")
            f.write(f"TP: {tp} (+{tp_pips:.1f} pips)\n")
            f.write(f"Volatility: {vol:.3f}%\n")
            f.write(f"Reason: {reason}\n")
    except Exception:
        pass


def _find_tg_send() -> Path:
    """
    Resolve tg_send.py reliably across:
      - ~/BotA/tools/tg_send.py   (your current repo)
      - ~/bot-a/tools/tg_send.py  (legacy path)
    """
    candidates = [
        ROOT / "tools" / "tg_send.py",
        Path.home() / "bot-a" / "tools" / "tg_send.py",
        Path.home() / "BotA" / "tools" / "tg_send.py",
    ]
    for p in candidates:
        if p.exists():
            return p
    # default to repo-local (best guess)
    return ROOT / "tools" / "tg_send.py"


def send_queued_signals() -> None:
    """Send all queued signals when internet returns."""
    if not is_online():
        print("📴 Still offline, skipping send")
        return

    files = sorted(QUEUE_DIR.glob("signal_*.json"))

    if not files:
        print("📭 No queued signals")
        return

    print(f"📬 Found {len(files)} queued signals, sending...")

    summary = "🔄 OFFLINE SIGNALS SUMMARY\n"
    summary += f"Reconnected: {_utc_strftime('%Y-%m-%d %H:%M')} UTC\n"
    summary += f"Signals missed: {len(files)}\n\n"

    for i, file in enumerate(files, 1):
        try:
            with open(file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue

        summary += f"Signal #{i} ({data.get('timestamp','')})\n"
        summary += f"  {data.get('action','')} @ {data.get('entry','')}\n"
        summary += f"  SL: {data.get('sl','')} / TP: {data.get('tp','')}\n"
        try:
            summary += f"  Vol: {float(data.get('volatility',0.0)):.3f}%\n\n"
        except Exception:
            summary += "  Vol: 0.000%\n\n"

    tg_script = _find_tg_send()
    if not tg_script.exists():
        print(f"❌ Send failed: tg_send.py not found (looked for {tg_script})")
        return

    try:
        result = subprocess.run(
            ["python3", str(tg_script), summary],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except Exception as e:
        print(f"❌ Send failed: {e}")
        return

    if "SUCCESS" in (result.stdout or ""):
        print("✅ Sent summary to Telegram")

        archive_dir = QUEUE_DIR / "sent"
        archive_dir.mkdir(parents=True, exist_ok=True)

        archived = 0
        for file in files:
            try:
                file.rename(archive_dir / file.name)
                archived += 1
            except Exception:
                pass

        print(f"📦 Archived {archived} signals")
    else:
        out = (result.stdout or "").strip()
        err = (result.stderr or "").strip()
        if err and out:
            print(f"❌ Send failed: {out} | {err}")
        elif err:
            print(f"❌ Send failed: {err}")
        else:
            print(f"❌ Send failed: {out}")


def _main() -> int:
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "send":
        send_queued_signals()
        return 0

    print("🧪 Testing offline queue...")

    test_signal = {
        "timestamp": _utc_strftime("%Y-%m-%d %H:%M:%S"),
        "pair": "EURUSD",
        "action": "BUY",
        "entry": 1.17089,
        "sl": 1.16926,
        "tp": 1.17362,
        "sl_pips": 16.3,
        "tp_pips": 27.3,
        "volatility": 0.37,
        "score": 0.21,
        "reason": "Test signal",
    }

    queue_signal(test_signal)

    print("\nTo send queued signals:")
    print("  python3 offline_queue_system.py send")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
