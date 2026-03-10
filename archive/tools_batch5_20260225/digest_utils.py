#!/data/data/com.termux/files/usr/bin/python3
# -*- coding: utf-8 -*-

"""
digest_utils.py
Utilities to build a safe, duplicate-proof daily digest from signals.csv.
- Reads CSV and aggregates per UTC day
- Adds strong-signal split and a simple hourly histogram
- Checksum guard: prevents duplicate sends per day
- Failover: writes the digest text to data/failed_digests/YYYY-MM-DD.txt on send failure
"""

import csv, hashlib, json, os, sys, tempfile, datetime as dt
from typing import Dict, List, Tuple

BOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BOT_DIR, "data")
LOGS_DIR = os.path.join(BOT_DIR, "logs")
CSV_PATH = os.path.join(DATA_DIR, "signals.csv")
FAILED_DIR = os.path.join(DATA_DIR, "failed_digests")

LOCK_PATH = os.path.join(tempfile.gettempdir(), "bot-a-digest.lock")  # app-safe tmp

DEFAULTS = {
    "confidence_threshold": 3.0,
    "strong_send_threshold": 6,
}

def _load_policy() -> Dict:
    p = os.path.join(BOT_DIR, "config", "policy.json")
    try:
        with open(p, "r") as f:
            pol = json.load(f)
            for k,v in DEFAULTS.items():
                pol.setdefault(k, v)
            return pol
    except Exception:
        return DEFAULTS.copy()

def _parse_row(row: List[str]) -> Tuple[dt.datetime, str, str, float, int]:
    # expected row: ISO_UTC,PAIR,SENTIMENT,CONFIDENCE,SENT_SCORE,HASH
    # (HASH may be absent; tolerate 5th/6th columns)
    ts = row[0]
    pair = row[1]
    sentiment = row[2].upper()
    conf = float(row[3])
    if len(row) >= 5:
        try:
            s6 = int(row[4])
        except Exception:
            s6 = 0
    else:
        s6 = 0
    try:
        t = dt.datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(dt.timezone.utc)
    except Exception:
        # last resort: treat as naive UTC
        t = dt.datetime.strptime(ts.split(".")[0], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=dt.timezone.utc)
    return t, pair, sentiment, conf, s6

def load_signals_for_date(target_date: dt.date) -> List[Tuple[dt.datetime, str, str, float, int]]:
    if not os.path.exists(CSV_PATH):
        return []
    out: List[Tuple[dt.datetime, str, str, float, int]] = []
    with open(CSV_PATH, "r", newline="") as f:
        r = csv.reader(f)
        for row in r:
            if not row or len(row) < 4: 
                continue
            try:
                t, pair, sent, conf, s6 = _parse_row(row)
            except Exception:
                continue
            if t.date() == target_date:
                out.append((t, pair, sent, conf, s6))
    return out

def summarize(signals: List[Tuple[dt.datetime, str, str, float, int]], policy: Dict) -> Dict:
    conf_gate = float(policy.get("confidence_threshold", 3.0))
    strong_gate = int(policy.get("strong_send_threshold", 6))

    counts = {"BUY":0, "SELL":0, "NEUTRAL":0}
    strong_counts = {"BUY":0, "SELL":0, "NEUTRAL":0}
    by_pair: Dict[str, Dict[str,int]] = {}
    hours = [0]*24
    confs: List[float] = []

    for t,pair,sent,conf,s6 in signals:
        sent_key = "NEUTRAL"
        if "BUY" in sent:  sent_key = "BUY"
        elif "SELL" in sent: sent_key = "SELL"
        counts[sent_key] += 1
        by_pair.setdefault(pair, {"BUY":0,"SELL":0,"NEUTRAL":0})
        by_pair[pair][sent_key] += 1
        confs.append(conf)
        hours[t.hour] += 1
        # "strong" if clears both gates
        if conf >= conf_gate and s6 >= strong_gate:
            strong_counts[sent_key] += 1

    avg_conf = (sum(confs)/len(confs)) if confs else 0.0
    return {
        "counts": counts,
        "strong_counts": strong_counts,
        "by_pair": by_pair,
        "hours": hours,
        "avg_conf": avg_conf
    }

def _histogram(hours: List[int]) -> str:
    if not hours or max(hours) == 0:
        return "–––––––––– no activity ––––––––––"
    m = max(hours)
    # scale to 10 blocks
    blocks = []
    for h,c in enumerate(hours):
        bar_len = int(round((c/m)*10))
        bar = ("█"*bar_len) if bar_len>0 else "·"
        blocks.append(f"{h:02d}:{bar}")
    # print in two rows of 12 for compactness
    row1 = "  ".join(blocks[:12])
    row2 = "  ".join(blocks[12:])
    return row1 + "\n" + row2

def build_digest_text(target_date: dt.date, summary: Dict) -> str:
    c = summary["counts"]; s = summary["strong_counts"]
    avg = summary["avg_conf"]
    by_pair = summary["by_pair"]
    hours = summary["hours"]

    lines = []
    lines.append(f"🧾 Daily Digest ({target_date.isoformat()})")
    lines.append(f"Signals: BUY={c['BUY']}, SELL={c['SELL']}, NEUTRAL={c['NEUTRAL']}")
    lines.append(f"Strong signals (conf≥thr & s6≥thr): BUY={s['BUY']}, SELL={s['SELL']}, NEUTRAL={s['NEUTRAL']}")
    lines.append(f"Average confidence: {avg:.1f}/10")
    lines.append("")
    if by_pair:
        lines.append("Per-pair:")
        for pair, cnts in sorted(by_pair.items()):
            lines.append(f"• {pair}: BUY={cnts['BUY']}, SELL={cnts['SELL']}, NEUTRAL={cnts['NEUTRAL']}")
        lines.append("")
    lines.append("Hourly activity (UTC):")
    lines.append(_histogram(hours))
    return "\n".join(lines)

def checksum(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()

def read_lock() -> Dict:
    try:
        with open(LOCK_PATH, "r") as f:
            return json.load(f)
    except Exception:
        return {}

def write_lock(day: str, chksum: str) -> None:
    try:
        with open(LOCK_PATH, "w") as f:
            json.dump({"date": day, "checksum": chksum}, f)
    except Exception:
        pass

def should_skip(day: str, chksum: str, force: bool=False) -> bool:
    if force: 
        return False
    lk = read_lock()
    if not lk: 
        return False
    return lk.get("date") == day and lk.get("checksum") == chksum

def save_failed_digest(day: str, text: str) -> None:
    os.makedirs(FAILED_DIR, exist_ok=True)
    path = os.path.join(FAILED_DIR, f"{day}.txt")
    try:
        with open(path, "w") as f:
            f.write(text)
    except Exception:
        pass
