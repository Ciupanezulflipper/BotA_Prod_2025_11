#!/usr/bin/env python3
"""
Bot A — Telegram Controller (long-polling)
Commands (from any chat you message the bot in):
  /start       -> alias for /start_alerts
  /stop        -> alias for /pause_alerts
  /start_alerts
  /pause_alerts
  /status
  /audit
  /help
Design goals:
- No changes to the proven alert loop. We only start/stop it as a process.
- Reads TELEGRAM_BOT_TOKEN from environment (export once; persists in your Termux session or tele_env.sh).
- Sends concise replies; uses existing metrics scripts when available.
"""

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.parse import urlencode

ROOT = Path(os.environ.get("HOME", "")) / "BotA"
TOOLS = ROOT / "tools"
STATE = ROOT / "state"
ALERT_LOG = ROOT / "alert.log"
RUN_LOG = ROOT / "run.log"
OFFSET_FILE = STATE / "tele_update_offset.txt"

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
if not TOKEN:
    sys.stderr.write("[tele_control] ERROR: TELEGRAM_BOT_TOKEN is not exported.\n")
    sys.stderr.write("  Tip: source $HOME/BotA/tools/tele_env.sh <CHAT_ID>\n")
    sys.exit(1)

API = f"https://api.telegram.org/bot{TOKEN}"

def _http_json(method: str, params: dict):
    data = urlencode(params).encode()
    req = Request(f"{API}/{method}", data=data, headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())

def send_msg(chat_id: int, text: str, parse_mode: str = "HTML"):
    try:
        _http_json("sendMessage", {"chat_id": chat_id, "text": text, "parse_mode": parse_mode, "disable_web_page_preview": 1})
    except Exception as e:
        sys.stderr.write(f"[tele_control] send_msg error: {e}\n")

def _proc_running() -> bool:
    try:
        out = subprocess.check_output(["pgrep", "-f", "tools/alert_loop.sh"], text=True)
        return bool(out.strip())
    except subprocess.CalledProcessError:
        return False

def _start_alert_loop() -> str:
    if _proc_running():
        return "🟢 <b>Alerts already running.</b>"
    try:
        subprocess.Popen(["nohup", str(TOOLS / "alert_loop.sh")], stdout=open(os.devnull, "w"), stderr=subprocess.STDOUT)
        return "✅ <b>Alerts started.</b>"
    except Exception as e:
        return f"❌ Failed to start alerts: {e}"

def _pause_alert_loop() -> str:
    if not _proc_running():
        return "⏸️ <b>Alerts already paused.</b>"
    try:
        subprocess.call(["pkill", "-f", "tools/alert_loop.sh"])
        return "⏸️ <b>Alerts paused.</b>"
    except Exception as e:
        return f"❌ Failed to pause alerts: {e}"

def _age_seconds(path: Path):
    try:
        return int(time.time() - path.stat().st_mtime)
    except Exception:
        return None

def _status_text() -> str:
    run_age = _age_seconds(RUN_LOG)
    alert_age = _age_seconds(ALERT_LOG)
    running = _proc_running()
    lines = [
        "🩺 <b>BotA — Status</b>",
        time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "",
        f"proc: alert_loop={'1' if running else '0'}",
        f"run.log age: {run_age if run_age is not None else 'n/a'}s",
        f"alert.log age: {alert_age if alert_age is not None else 'n/a'}s",
    ]
    return "\n".join(lines)

def _audit_text() -> str:
    """Prefer tools/metrics_verify.sh for a richer summary; else fallback to quick counts."""
    script = TOOLS / "metrics_verify.sh"
    if script.exists():
        try:
            out = subprocess.check_output([str(script)], text=True, timeout=60)
            # Trim excessive sections; keep the three summaries if present.
            keep = []
            capture = False
            for ln in out.splitlines():
                if ln.strip().startswith("=== metrics_signals ==="):
                    capture = True
                if capture:
                    keep.append(ln)
                if ln.strip().startswith("=== STATUS SUMMARY ==="):
                    keep.append(ln)
                    break
            body = "\n".join(keep) if keep else out
            return f"📊 <b>BotA — Audit</b>\n{time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}\n\n<code>{body}</code>"
        except Exception as e:
            return f"📊 <b>BotA — Audit</b>\n{time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}\n\n❌ metrics_verify.sh failed: {e}"
    # Fallback: quick counts from run.log
    h1 = h4 = d1 = errs = 0
    try:
        with RUN_LOG.open("r", errors="ignore") as f:
            for ln in f:
                if ln.startswith("H1: "): h1 += 1
                elif ln.startswith("H4: "): h4 += 1
                elif ln.startswith("D1: "): d1 += 1
                if "provider_error=" in ln: errs += 1
    except FileNotFoundError:
        pass
    return (
        "📊 <b>BotA — Audit</b>\n"
        f"{time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}\n\n"
        f"TF lines — H1:{h1} H4:{h4} D1:{d1}\n"
        f"provider_error lines: {errs}"
    )

HELP = (
    "🤖 <b>BotA — Controls</b>\n"
    "/start or /start_alerts — start signals\n"
    "/stop or /pause_alerts — pause signals\n"
    "/status — process & log health\n"
    "/audit — compact metrics summary\n"
)

CMD_MAP = {
    "/start": "start",
    "/start@": "start",  # in case of bot mention
    "/start_alerts": "start",
    "/stop": "pause",
    "/stop@": "pause",
    "/pause_alerts": "pause",
    "/status": "status",
    "/audit": "audit",
    "/help": "help",
}

def main():
    STATE.mkdir(parents=True, exist_ok=True)
    # Resume from last update_id if present
    offset = 0
    if OFFSET_FILE.exists():
        try:
            offset = int(OFFSET_FILE.read_text().strip())
        except Exception:
            offset = 0

    while True:
        try:
            updates = _http_json("getUpdates", {"timeout": 50, "offset": offset + 1})
        except Exception as e:
            sys.stderr.write(f"[tele_control] getUpdates error: {e}\n")
            time.sleep(3)
            continue

        if not updates.get("ok", False):
            time.sleep(3)
            continue

        for upd in updates.get("result", []):
            update_id = upd.get("update_id", 0)
            offset = max(offset, update_id)
            # persist offset robustly
            try:
                OFFSET_FILE.write_text(str(offset))
            except Exception:
                pass

            msg = upd.get("message") or upd.get("edited_message") or {}
            chat = msg.get("chat") or {}
            chat_id = chat.get("id")
            text = (msg.get("text") or "").strip()

            if not chat_id or not text:
                continue

            # Normalize command (strip bot mention if present)
            cmd = text.split()[0]
            base = cmd.split("@")[0]
            key = base if base in CMD_MAP else cmd
            action = CMD_MAP.get(key)

            if action == "start":
                send_msg(chat_id, _start_alert_loop())
            elif action == "pause":
                send_msg(chat_id, _pause_alert_loop())
            elif action == "status":
                send_msg(chat_id, _status_text())
            elif action == "audit":
                send_msg(chat_id, _audit_text(), parse_mode="HTML")
            elif action == "help":
                send_msg(chat_id, HELP)
            else:
                # Unknown: show help lightly
                if text.startswith("/"):
                    send_msg(chat_id, HELP)

        # Short idle before next poll iteration
        time.sleep(0.5)

if __name__ == "__main__":
    main()
