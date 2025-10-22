#!/usr/bin/env python3
# tools/signal_logger.py
# Append-only JSON logs for Bot-A signals + daily summary helpers.

import os, json
from typing import Dict, Any, List, Tuple
from datetime import datetime, timezone

LOG_DIR = os.environ.get("BOT_A_LOG_DIR", os.path.expanduser("~/.bot-a/logs"))
SOURCE   = "news_sentiment"  # default source label; callers can override

def _ensure_dir():
    os.makedirs(LOG_DIR, exist_ok=True)

def _utc_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def _log_path(day: str) -> str:
    # day = "YYYY-MM-DD"
    return os.path.join(LOG_DIR, f"{SOURCE}_{day}.log")

def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")

def log_event(event: Dict[str, Any], day: str = None, source: str = None) -> str:
    """
    Write a single-line JSON event. Returns path written.
    """
    _ensure_dir()
    event = dict(event or {})
    event.setdefault("ts", _utc_iso())
    if source:
        event["source"] = source
    else:
        event.setdefault("source", SOURCE)
    day = day or _today()
    path = _log_path(day)
    tmp = path + ".tmp"
    with open(tmp, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")
    # atomic-ish append by rename
    with open(tmp, "r", encoding="utf-8") as rf, open(path, "a", encoding="utf-8") as wf:
        for line in rf:
            wf.write(line)
    # clear tmp
    open(tmp, "w").close()
    return path

# -------- High-level shortcuts (used by senders) -----------------------------

def log_send(payload: Dict[str, Any], ctx: Dict[str, Any] = None):
    data = {
        "type": "send",
        "symbol": payload.get("symbol"),
        "decision": payload.get("decision"),
        "confidence": payload.get("confidence"),
        "news_score": payload.get("news_score"),
        "tech_score": payload.get("tech_score"),
        "risk": payload.get("risk"),
        "timeframe": payload.get("timeframe"),
    }
    if ctx: data.update({f"ctx_{k}": v for k, v in ctx.items()})
    return log_event(data)

def log_skip(payload: Dict[str, Any], reason: str, ctx: Dict[str, Any] = None):
    data = {
        "type": "skip",
        "symbol": payload.get("symbol"),
        "decision": payload.get("decision"),
        "reason": reason,
        "confidence": payload.get("confidence"),
        "news_score": payload.get("news_score"),
        "tech_score": payload.get("tech_score"),
    }
    if ctx: data.update({f"ctx_{k}": v for k, v in ctx.items()})
    return log_event(data)

def log_error(message: str, ctx: Dict[str, Any] = None):
    data = {"type": "error", "message": message}
    if ctx: data.update({f"ctx_{k}": v for k, v in ctx.items()})
    return log_event(data)

# -------- Read & summarize ----------------------------------------------------

def read_day(day: str = None) -> List[Dict[str, Any]]:
    """
    Return list of JSON events for a given day.
    """
    day = day or _today()
    path = _log_path(day)
    events: List[Dict[str, Any]] = []
    if not os.path.exists(path):
        return events
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line: 
                continue
            try:
                events.append(json.loads(line))
            except Exception:
                # keep going on bad lines
                continue
    return events

def summarize_day(day: str = None) -> Dict[str, Any]:
    """
    Returns dict with totals, by_symbol, skip_reasons.
    """
    ev = read_day(day)
    total = len(ev)
    sent = [e for e in ev if e.get("type") == "send"]
    skipped = [e for e in ev if e.get("type") == "skip"]
    errors = [e for e in ev if e.get("type") == "error"]

    by_symbol: Dict[str, Dict[str, int]] = {}
    for e in ev:
        sym = (e.get("symbol") or "UNKNOWN").upper()
        by_symbol.setdefault(sym, {"send":0, "skip":0, "error":0})
        by_symbol[sym][e["type"]] = by_symbol[sym].get(e["type"], 0) + 1

    skip_reasons: Dict[str, int] = {}
    for s in skipped:
        r = s.get("reason") or "unknown"
        skip_reasons[r] = skip_reasons.get(r, 0) + 1

    return {
        "day": day or _today(),
        "total": total,
        "sent": len(sent),
        "skipped": len(skipped),
        "errors": len(errors),
        "by_symbol": by_symbol,
        "skip_reasons": sorted(skip_reasons.items(), key=lambda x: x[1], reverse=True),
    }
