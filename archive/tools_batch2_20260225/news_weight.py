#!/usr/bin/env python3
from __future__ import annotations
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, Iterable, Tuple

ISO = "%Y-%m-%dT%H:%M:%SZ"

def _utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)

def _parse_iso(s: str) -> Optional[datetime]:
    try:
        return _utc(datetime.strptime(s.strip(), ISO))
    except Exception:
        return None

@dataclass
class NewsRow:
    time_utc: datetime
    symbol: str
    bias: str          # "Bullish" | "Bearish" | "Neutral"
    score: float       # integer in our logs, but parse as float
    why: str

    @staticmethod
    def from_csv_row(row: Dict[str, str]) -> Optional["NewsRow"]:
        t = _parse_iso(row.get("time_utc") or row.get("asof_utc") or "")
        sym = (row.get("symbol") or "").strip().upper()
        bias = (row.get("bias") or "").strip().capitalize() or "Neutral"
        try:
            sc = float(row.get("score", "0").strip() or 0)
        except Exception:
            sc = 0.0
        why = (row.get("why") or "").strip()
        if not t or not sym:
            return None
        return NewsRow(t, sym, bias, sc, why)

def load_news(rows: Iterable[Dict[str, str]]) -> Dict[str, list[NewsRow]]:
    out: Dict[str, list[NewsRow]] = {}
    for r in rows:
        nr = NewsRow.from_csv_row(r)
        if not nr:
            continue
        out.setdefault(nr.symbol, []).append(nr)
    # sort per symbol by time desc (newest first)
    for v in out.values():
        v.sort(key=lambda x: x.time_utc, reverse=True)
    return out

def choose_recent(symbol_news: list[NewsRow], when: datetime, lookback: timedelta) -> Optional[NewsRow]:
    if not symbol_news:
        return None
    for n in symbol_news:
        if when - n.time_utc <= lookback and n.time_utc <= when:
            return n
    return None

def compute_tilt(bias: str, base_boost: int, max_abs: int) -> int:
    b = (bias or "").lower()
    if b == "bullish":
        val = base_boost
    elif b == "bearish":
        val = -base_boost
    else:
        val = 0
    # clamp
    if val > max_abs:
        val = max_abs
    if val < -max_abs:
        val = -max_abs
    return val

def clamp(v: float, lo: float, hi: float) -> float:
    return hi if v > hi else lo if v < lo else v

def apply_news_to_signal(
    sig: Dict[str, Any],
    news_by_symbol: Dict[str, list[NewsRow]],
    *,
    lookback_min: int,
    base_boost: int,
    max_abs_boost: Optional[int] = None,
) -> Tuple[float, str, Optional[str]]:
    """
    Returns (combined_score, combined_side, news_tag)
    - combined_side is "Bullish"/"Bearish"/"Neutral" after tilt
    - news_tag is a compact text we can store for audit (e.g. "news:+10 Bullish: CPI")
    """
    max_abs = max_abs_boost if max_abs_boost is not None else base_boost
    symbol = (sig.get("symbol") or "").upper()
    t = _parse_iso(sig.get("time_utc") or "")
    try:
        base_score = float(sig.get("score", 0) or 0)
    except Exception:
        base_score = 0.0

    side = (sig.get("side") or sig.get("bias") or "").capitalize() or "Neutral"
    if not symbol or not t:
        return base_score, side, None

    chosen = choose_recent(news_by_symbol.get(symbol, []), t, timedelta(minutes=lookback_min))
    if not chosen:
        return base_score, side, None

    boost = compute_tilt(chosen.bias, base_boost, base_boost if max_abs is None else max_abs)
    combined = clamp(base_score + boost, 0.0, 100.0)

    # Re-evaluate side based on combined score, but only if base side wasn't already explicit
    # Simple rule: score >= 50 -> Bullish, <= 50 -> Bearish, but keep "Neutral" if near 50
    if combined >= 55:
        combined_side = "Bullish"
    elif combined <= 45:
        combined_side = "Bearish"
    else:
        combined_side = "Neutral"

    tag = f"news:{'+' if boost>=0 else ''}{boost} {chosen.bias}: {chosen.why[:64]}"
    return combined, combined_side, tag
