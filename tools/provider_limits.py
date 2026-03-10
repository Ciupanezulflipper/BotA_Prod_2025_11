#!/usr/bin/env python3
"""
Lightweight per-provider rate-limit/backoff registry.
Stores JSON in $REPO/state/provider_limits.json
"""

from __future__ import annotations
import json, time, os
from pathlib import Path
from typing import Dict

REPO = Path(os.getenv("REPO") or Path(__file__).resolve().parents[1])
STATE = Path(REPO, "state")
STATE.mkdir(parents=True, exist_ok=True)
DB = STATE / "provider_limits.json"

DEFAULTS = {
    "yahoo": {"last": 0.0, "cooldown": 90.0},     # Yahoo can 429 if hammered
    "finnhub": {"last": 0.0, "cooldown": 1.2},    # free tier ~60/min
}

def _load() -> Dict[str, Dict[str, float]]:
    if DB.exists():
        try:
            return json.loads(DB.read_text())
        except Exception:
            pass
    return DEFAULTS.copy()

def _save(d: Dict[str, Dict[str, float]]) -> None:
    tmp = DB.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, indent=2))
    tmp.replace(DB)

def ready(provider: str) -> bool:
    d = _load()
    now = time.time()
    cfg = d.get(provider, DEFAULTS.get(provider, {"last": 0.0, "cooldown": 1.0}))
    return (now - float(cfg.get("last", 0.0))) >= float(cfg.get("cooldown", 1.0))

def stamp(provider: str, *, cooldown: float | None = None) -> None:
    d = _load()
    now = time.time()
    entry = d.get(provider, {"last": 0.0, "cooldown": 1.0})
    entry["last"] = now
    if cooldown is not None:
        entry["cooldown"] = float(cooldown)
    d[provider] = entry
    _save(d)
