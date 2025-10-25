#!/usr/bin/env python3
"""
Phase 10: Health ping — summarize BotA status and (optionally) push to Telegram.

Env:
  PAIRS_OVERRIDE="EURUSD GBPUSD"   # optional list; defaults to these two
  DRY=1                            # print only, do not send
"""
from __future__ import annotations
import os, sys, re, json, subprocess, time
from datetime import datetime, timezone
from typing import Dict, List

ROOT = os.path.expanduser("~/BotA")
RUN_LOG = os.path.join(ROOT, "run.log")
TOOLS = os.path.join(ROOT, "tools")

HEADER_RE = re.compile(r"^===\s+([A-Z/]+)\s+snapshot\s+===$")
TF_RE = re.compile(r"^(H1|H4|D1):\s+t=([0-9:-]+\s?[0-9:]*Z)\s+close=")

def utcnow_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

def read_log(path: str) -> List[str]:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read().splitlines()
    except FileNotFoundError:
        return []

def last_block_times(lines: List[str]) -> Dict[str, Dict[str, str]]:
    """
    Return {PAIR: {H1: ts, H4: ts, D1: ts}} for the latest block of each pair found.
    """
    out: Dict[str, Dict[str, str]] = {}
    i = 0
    while i < len(lines):
        m = HEADER_RE.match(lines[i].strip())
        if m:
          pair_hdr = m.group(1).replace("/", "").upper()
          tf_map: Dict[str, str] = {}
          j = i + 1
          while j < len(lines):
              s = lines[j].strip()
              if HEADER_RE.match(s):
                  break
              mm = TF_RE.match(s)
              if mm:
                  tf, ts = mm.groups()
                  tf_map.setdefault(tf, ts)
              j += 1
          if tf_map:
              out[pair_hdr] = tf_map
          i = j
        else:
          i += 1
    return out

def pgrep(pattern: str) -> int:
    try:
        p = subprocess.run(["pgrep", "-f", pattern], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if p.returncode != 0:
            return 0
        return len([x for x in p.stdout.splitlines() if x.strip()])
    except Exception:
        return 0

def push(msg: str) -> bool:
    if os.getenv("DRY","0") in ("1","true","TRUE","yes","YES"):
        print(msg)
        print("[health] DRY=1 (not pushed)")
        return True
    sender = os.path.join(TOOLS, "telegram_push.py")
    if not os.path.exists(sender):
        print("[health] telegram_push.py missing", file=sys.stderr)
        return False
    p = subprocess.run(["python3", sender, msg], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return p.returncode == 0

def main() -> int:
    pairs = os.getenv("PAIRS_OVERRIDE", "EURUSD GBPUSD").split()
    lines = read_log(RUN_LOG)
    blocks = last_block_times(lines)

    # process state
    procs = {
        "alert_loop": pgrep(os.path.join(TOOLS, "alert_loop.sh")),
        "supervise": pgrep(os.path.join(TOOLS, "supervise_bot.sh")),
    }

    # compose message (HTML)
    parts = []
    parts.append("🩺 <b>BotA — Health</b>")
    parts.append(utcnow_str())
    parts.append("")
    parts.append(f"proc: alert_loop={procs['alert_loop']} supervise={procs['supervise']}")
    parts.append("")
    for sym in pairs:
        key = sym.upper()
        tf = blocks.get(key, {})
        def vis(p: str) -> str:
            return p if "/" in p else (p[:3]+"/"+p[3:] if len(p)==6 else p)
        parts.append(f"<b>{vis(key)}</b>: H1={tf.get('H1','—')}  H4={tf.get('H4','—')}  D1={tf.get('D1','—')}")
    msg = "\n".join(parts)
    ok = push(msg)
    print("[health] pushed" if ok else "[health] push failed", file=sys.stderr if not ok else sys.stdout)
    return 0 if ok else 1

if __name__ == "__main__":
    sys.exit(main())
