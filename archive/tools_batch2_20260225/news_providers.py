#!/usr/bin/env python3
"""
news_providers.py — no-key news sources with simple bias tags.

Providers (all optional; run whatever works):
- Google News RSS (no key) per symbol query
- Yahoo Finance RSS  (no key) per symbol query
- GDELT query API    (no key, sometimes rate-limited)

Bias tagging is heuristic: looks for ↑/bullish or ↓/bearish words in title+summary.
"""

from __future__ import annotations
import re, time, json
from datetime import datetime, timezone
from typing import Iterable, Dict, Any, List, Tuple

import feedparser  # pip install feedparser
import requests    # pip install requests

UTC = timezone.utc

# -------- symbol -> query terms (override via .env NEWS_QUERIES later if needed)
DEFAULT_QUERIES = {
    "EURUSD": ["EURUSD", "Euro Dollar", "EUR USD", "EUR/USD", "ECB", "Eurozone", "USD", "Fed"],
    "XAUUSD": ["XAUUSD", "gold price", "spot gold", "XAU USD", "XAU/USD", "gold futures", "Comex"],
}

# -------- quick bias lexicon (very small on purpose)
BULL = re.compile(r"\b(rise|rises|rising|gain|gains|higher|surge|bull|bullish|strengthens?)\b", re.I)
BEAR = re.compile(r"\b(fall|falls|falling|drop|drops|lower|plunge|bear|bearish|weakens?)\b", re.I)
USD_UP   = re.compile(r"\b(usd (rises?|strengthens?|higher)|dollar (rises?|strengthens?|higher))\b", re.I)
USD_DOWN = re.compile(r"\b(usd (falls?|weakens?|lower)|dollar (falls?|weakens?|lower))\b", re.I)
GOLD_UP   = re.compile(r"\b(gold (rises?|higher|gains?|surges?))\b", re.I)
GOLD_DOWN = re.compile(r"\b(gold (falls?|drops?|lower|plunges?))\b", re.I)
EUR_UP   = re.compile(r"\b(euro (rises?|strengthens?|higher))\b", re.I)
EUR_DOWN = re.compile(r"\b(euro (falls?|weakens?|lower))\b", re.I)

def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

def _bias_for(symbol: str, title: str, summary: str) -> Tuple[str, int, str]:
    """Return (bias, score, why). Score is a tiny 0..+/-5.”
    """
    text = f"{title} {summary}".lower()

    bias, score, why = "Neutral", 0, "no strong keywords"

    if symbol == "EURUSD":
        if USD_UP.search(text) or EUR_DOWN.search(text):
            return "Bearish", 3, "USD↑ or EUR↓"
        if USD_DOWN.search(text) or EUR_UP.search(text):
            return "Bullish", 3, "USD↓ or EUR↑"

    if symbol == "XAUUSD":
        if GOLD_UP.search(text):
            return "Bullish", 3, "Gold↑"
        if GOLD_DOWN.search(text):
            return "Bearish", 3, "Gold↓"

    if BULL.search(text):
        bias, score, why = "Bullish", 1, "bullish keyword"
    if BEAR.search(text):
        bias, score, why = "Bearish", 1, "bearish keyword"
    return bias, score, why

# ---------------- Google News RSS ----------------
def google_news(symbol: str, terms: List[str]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    query = " OR ".join(terms)
    url = f"https://news.google.com/rss/search?q={requests.utils.quote(query)}&hl=en-US&gl=US&ceid=US:en"
    feed = feedparser.parse(url)
    for e in feed.entries[:20]:
        title = e.get("title", "")
        summary = e.get("summary", "")
        link = e.get("link", "")
        published = e.get("published_parsed") or e.get("updated_parsed")
        asof = time.strftime("%Y-%m-%dT%H:%M:%SZ", published) if published else _now_iso()
        bias, score, why = _bias_for(symbol, title, summary)
        out.append(dict(
            provider="google_news", symbol=symbol, title=title, link=link,
            asof_utc=asof, bias=bias, score=score, why=why
        ))
    return out

# ---------------- Yahoo Finance RSS --------------
def yahoo_finance(symbol: str, terms: List[str]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    # general yahoo finance news
    url = "https://finance.yahoo.com/news/rssindex"
    feed = feedparser.parse(url)
    for e in feed.entries[:20]:
        title = e.get("title", "")
        if not any(t.lower() in title.lower() for t in terms):
            continue
        summary = e.get("summary", "")
        link = e.get("link", "")
        published = e.get("published_parsed") or e.get("updated_parsed")
        asof = time.strftime("%Y-%m-%dT%H:%M:%SZ", published) if published else _now_iso()
        bias, score, why = _bias_for(symbol, title, summary)
        out.append(dict(
            provider="yahoo_finance", symbol=symbol, title=title, link=link,
            asof_utc=asof, bias=bias, score=score, why=why
        ))
    return out

# ---------------- GDELT (no key; best-effort) ----
def gdelt(symbol: str, terms: List[str]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    query = " OR ".join(terms)
    url = ("https://api.gdeltproject.org/api/v2/doc/doc"
           f"?query={requests.utils.quote(query)}&maxrecords=20&format=json")
    try:
        r = requests.get(url, timeout=10)
        if r.status_code != 200:
            return out
        data = r.json()
        for rec in data.get("articles", []):
            title = rec.get("title", "")
            summary = rec.get("seendate", "")
            link = rec.get("url", "")
            asof = rec.get("seendate") or _now_iso()
            # GDELT’s seendate like 20230910123400 -> convert to ISO
            if asof and asof.isdigit() and len(asof) == 14:
                asof = f"{asof[0:4]}-{asof[4:6]}-{asof[6:8]}T{asof[8:10]}:{asof[10:12]}:{asof[12:14]}Z"
            bias, score, why = _bias_for(symbol, title, summary)
            out.append(dict(
                provider="gdelt", symbol=symbol, title=title, link=link,
                asof_utc=asof, bias=bias, score=score, why=why
            ))
    except Exception:
        pass
    return out

def fetch_for_symbol(symbol: str, terms: List[str]) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    for fn in (google_news, yahoo_finance, gdelt):
        try:
            results.extend(fn(symbol, terms))
        except Exception:
            continue
    # dedupe by title+provider
    seen = set()
    deduped: List[Dict[str, Any]] = []
    for r in results:
        key = (r["provider"], r["title"])
        if key in seen: 
            continue
        seen.add(key)
        deduped.append(r)
    return deduped
