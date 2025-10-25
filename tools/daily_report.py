#!/usr/bin/env python3
from __future__ import annotations
import os, sys, re, json, subprocess
from datetime import datetime, timezone, timedelta

ROOT = os.path.expanduser("~/BotA")
RUN_LOG = os.path.join(ROOT, "run.log")
TOOLS = os.path.join(ROOT, "tools")

HEADER_RE = re.compile(r"^===\s+([A-Z/]+)\s+snapshot\s+===$")
TF_RE = re.compile(
    r"^(H1|H4|D1):\s+t=([0-9:-]+\s?[0-9:]*Z)\s+close=([0-9.]+)\s+EMA9=([0-9.]+)\s+EMA21=([0-9.]+)\s+RSI14=([0-9.]+|NA)\s+MACD_hist=([-\d.]+|NA)\s+vote=([+\-]?\d+)"
)

def now_utc() -> datetime:
    return datetime.now(timezone.utc)

def parse_utc(ts: str) -> datetime:
    # e.g., 2025-10-24 04:00:54Z or 2025-10-24 00:00:00Z
    s = ts.strip().replace("Z", "")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            dt = datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            pass
    return now_utc()

def read_log(path: str) -> list[str]:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read().splitlines()
    except FileNotFoundError:
        return []

def collect_last_24h(lines: list[str]):
    cutoff = now_utc() - timedelta(hours=24)
    results = {}  # pair -> list of entries
    cur_pair = None
    for line in lines:
        h = HEADER_RE.match(line.strip())
        if h:
            cur_pair = h.group(1).replace("/", "").upper()
            continue
        m = TF_RE.match(line.strip())
        if m and cur_pair:
            tf, ts, close, e9, e21, rsi, macd, vote = m.groups()
            dt = parse_utc(ts)
            if dt >= cutoff:
                results.setdefault(cur_pair, []).append({
                    "tf": tf, "t": dt, "close": float(close),
                    "e9": float(e9), "e21": float(e21),
                    "rsi": None if rsi == "NA" else float(rsi),
                    "macd": None if macd == "NA" else float(macd),
                    "vote": int(vote),
                })
    return results

def summarize(results: dict) -> dict:
    out = {}
    for pair, entries in results.items():
        if not entries:
            continue
        total = len(entries)
        pos = sum(1 for e in entries if e["vote"] > 0)
        neg = sum(1 for e in entries if e["vote"] < 0)
        zero = total - pos - neg
        last = sorted(entries, key=lambda e: e["t"])[-1]
        out[pair] = {
            "count": total, "pos": pos, "neg": neg, "zero": zero,
            "last_tf": last["tf"],
            "last_t": last["t"].astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            "last_close": last["close"], "last_vote": last["vote"],
        }
    return out

def fmt_msg(summary: dict) -> str:
    lines = []
    lines.append("🗓️ <b>BotA — Daily Report (24h)</b>")
    lines.append(now_utc().strftime("%Y-%m-%d %H:%M:%S UTC"))
    lines.append("")
    if not summary:
        lines.append("No snapshot data in the last 24h.")
        return "\n".join(lines)
    for pair in sorted(summary.keys()):
        s = summary[pair]
        vis = pair if "/" in pair else (pair[:3] + "/" + pair[3:] if len(pair) == 6 else pair)
        lines.append(f"<b>{vis}</b>: count={s['count']}  +{s['pos']} / {s['zero']} / -{s['neg']}")
        lines.append(f"  last: {s['last_tf']} @ {s['last_t']}  close={s['last_close']:.5f}  vote={s['last_vote']:+d}")
    return "\n".join(lines)

def push_telegram(msg: str) -> bool:
    sender = os.path.join(TOOLS, "telegram_push.py")
    if not os.path.exists(sender):
        return False
    try:
        p = subprocess.run(["python3", sender, msg], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return p.returncode == 0
    except Exception:
        return False

def main() -> int:
    lines = read_log(RUN_LOG)
    data = collect_last_24h(lines)
    summary = summarize(data)
    msg = fmt_msg(summary)
    print(msg)
    if os.getenv("DRY", "0") not in ("1", "true", "TRUE", "yes", "YES"):
        pushed = push_telegram(msg)
        print("[daily_report] pushed" if pushed else "[daily_report] not pushed")
    else:
        print("[daily_report] DRY=1 (not pushed)")
    return 0

if __name__ == "__main__":
    sys.exit(main())
