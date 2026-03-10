#!/data/data/com.termux/files/usr/bin/python3
"""
BotA News/Sentiment Engine (Termux-safe, RSS-only)

GOAL
- Produce a conservative macro bias for FX pairs as:
    score  (float) ~ [-1..+1]
    macro6 (int)   0..6  (neutral = 3)

FAIL-CLOSED RULES
- If NEWS_ON=0/off/false -> macro6=3, provider="off"
- If no usable news OR no matched macro signals -> macro6=3, provider="none" or "rss"

OUTPUT CONTRACT (single-line JSON to stdout)
{
  "pair": "EURUSD",
  "score": -0.6,
  "macro6": 0,
  "meta": {
    "provider": "off|none|rss",
    "count": 12,
    "hits": 2,
    "hit_items": 2,
    "details": [],
    "errors": [...]
  }
}

IMPORTANT FIX (false positives like "Warsh" -> "war")
- Single-word keywords (e.g., "war") are matched using word-boundary regex (\bwar\b),
  not substring matching. This prevents "war" matching inside "Warsh".
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Dict, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET
import http.client


# -----------------------------------------------------------------------------
# Time utilities (UTC tz-aware)
# -----------------------------------------------------------------------------

def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _coerce_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def parse_rss_datetime(text: Optional[str]) -> Optional[datetime]:
    """
    Parse common RSS/Atom datetime formats and normalize to UTC (tz-aware).
    Returns None if parsing fails.
    """
    if not text:
        return None
    s = text.strip()

    fmts: List[Tuple[str, bool]] = [
        ("%a, %d %b %Y %H:%M:%S %z", True),     # RFC822 with numeric offset
        ("%a, %d %b %Y %H:%M:%S GMT", False),   # RFC822 with GMT
        ("%a, %d %b %Y %H:%M:%S %Z", False),    # RFC822 with named tz (assume UTC)
        ("%Y-%m-%dT%H:%M:%SZ", False),          # ISO8601 with Z
        ("%Y-%m-%d %H:%M:%S", False),           # naive -> assume UTC
    ]

    for fmt, has_tz in fmts:
        try:
            dt = datetime.strptime(s, fmt)
        except Exception:
            continue
        if has_tz and dt.tzinfo is not None:
            return dt.astimezone(timezone.utc)
        return dt.replace(tzinfo=timezone.utc)

    # fromisoformat fallback (handles "+00:00", etc.)
    try:
        dt = datetime.fromisoformat(s)
        return _coerce_utc(dt)
    except Exception:
        return None


# -----------------------------------------------------------------------------
# Env helpers
# -----------------------------------------------------------------------------

def env_str(name: str, default: str = "") -> str:
    v = os.getenv(name)
    return default if v is None else str(v)


def env_int(name: str, default: int, lo: int, hi: int) -> int:
    raw = env_str(name, "").strip()
    if not raw:
        return default
    try:
        v = int(raw)
    except Exception:
        return default
    if v < lo:
        return lo
    if v > hi:
        return hi
    return v


def env_float(name: str, default: float, lo: float, hi: float) -> float:
    raw = env_str(name, "").strip()
    if not raw:
        return default
    try:
        v = float(raw)
    except Exception:
        return default
    if v < lo:
        return lo
    if v > hi:
        return hi
    return v


def env_bool(name: str, default: bool = False) -> bool:
    raw = env_str(name, "").strip().lower()
    if raw == "":
        return default
    return raw in ("1", "true", "yes", "on")


# -----------------------------------------------------------------------------
# RSS configuration
# -----------------------------------------------------------------------------
# Default set intentionally excludes feeds that frequently fail in Termux DNS/403/parsing.
DEFAULT_RSS_FEEDS: List[str] = [
    "https://www.investing.com/rss/news_285.rss",
    "https://www.investing.com/rss/news_301.rss",
    "https://www.cnbc.com/id/100003114/device/rss/rss.html",
    "https://www.cnbc.com/id/10001147/device/rss/rss.html",
    "https://www.marketwatch.com/rss/topstories",
]


def get_rss_feed_urls() -> List[str]:
    override = env_str("NEWS_RSS_FEEDS", "").strip()
    if not override:
        return list(DEFAULT_RSS_FEEDS)
    urls: List[str] = []
    for part in override.split(","):
        u = part.strip()
        if u:
            urls.append(u)
    return urls or list(DEFAULT_RSS_FEEDS)


def bot_cache_dir() -> str:
    # Keep aligned with BotA project layout
    root = env_str("BOTA_ROOT", os.path.expanduser("~/BotA"))
    d = os.path.join(root, "cache", "rss_cache")
    os.makedirs(d, exist_ok=True)
    return d


def _cache_key(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8")).hexdigest()


def _cache_paths(url: str) -> Tuple[str, str]:
    # Returns (data_path, meta_path)
    key = _cache_key(url)
    d = bot_cache_dir()
    return (os.path.join(d, f"{key}.xml"), os.path.join(d, f"{key}.json"))


# -----------------------------------------------------------------------------
# Data model
# -----------------------------------------------------------------------------

@dataclass
class NewsItem:
    provider: str
    title: str
    summary: str
    published: Optional[datetime]  # tz-aware UTC or None


# -----------------------------------------------------------------------------
# HTTP fetch (with caching, size limit, partial reads)
# -----------------------------------------------------------------------------

def _http_read_limited(resp, max_bytes: int) -> bytes:
    """
    Read up to max_bytes. If server sends more, we stop early.
    """
    chunks: List[bytes] = []
    read_total = 0
    while True:
        # read in 8KB increments
        n = 8192
        if read_total + n > max_bytes:
            n = max(0, max_bytes - read_total)
        if n <= 0:
            break
        try:
            buf = resp.read(n)
        except http.client.IncompleteRead as e:
            # Use partial content and stop
            buf = e.partial or b""
            if buf:
                chunks.append(buf)
            break
        if not buf:
            break
        chunks.append(buf)
        read_total += len(buf)
    return b"".join(chunks)


def _fetch_url(url: str, timeout_sec: int, max_bytes: int, errors: List[str], debug: bool) -> Optional[bytes]:
    """
    Fetch raw bytes from URL. Returns bytes or None on failure.
    Uses file cache with TTL.
    """
    ttl = env_int("NEWS_RSS_CACHE_TTL_SEC", default=3600, lo=0, hi=86400)
    polite_sleep = env_float("NEWS_RSS_POLITE_SLEEP_SEC", default=0.0, lo=0.0, hi=2.0)

    data_path, meta_path = _cache_paths(url)

    # Try cache first
    if ttl > 0 and os.path.exists(data_path) and os.path.exists(meta_path):
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            fetched_at = float(meta.get("fetched_at", 0.0))
            age = time.time() - fetched_at
            if age >= 0 and age <= ttl:
                with open(data_path, "rb") as f:
                    b = f.read()
                if b:
                    if debug:
                        print(f"[news] RSS {url} -> cache_hit age={int(age)}s bytes={len(b)}", file=sys.stderr)
                    return b
        except Exception:
            # cache is optional; ignore failures
            pass

    headers = {
        "User-Agent": "BotA-News/2.0 (Termux; RSS macro; conservative)",
        "Accept": "application/rss+xml, application/xml;q=0.9, text/xml;q=0.8, */*;q=0.5",
        "Connection": "close",
    }
    req = Request(url, headers=headers)

    if polite_sleep > 0:
        time.sleep(polite_sleep)

    try:
        with urlopen(req, timeout=timeout_sec) as resp:
            b = _http_read_limited(resp, max_bytes=max_bytes)
    except HTTPError as e:
        errors.append(f"rss_http:{url}:{getattr(e, 'code', 'HTTPError')}")
        if debug:
            print(f"[news] RSS error {url}: HTTPError {getattr(e, 'code', '?')}", file=sys.stderr)
        return None
    except URLError:
        errors.append(f"rss_url:{url}:URLError")
        if debug:
            print(f"[news] RSS error {url}: URLError", file=sys.stderr)
        return None
    except TimeoutError:
        errors.append(f"rss_timeout:{url}:Timeout")
        if debug:
            print(f"[news] RSS error {url}: Timeout", file=sys.stderr)
        return None
    except Exception:
        errors.append(f"rss_exc:{url}:fetch_failed")
        if debug:
            print(f"[news] RSS error {url}: fetch_failed", file=sys.stderr)
        return None

    if not b:
        errors.append(f"rss_empty:{url}")
        if debug:
            print(f"[news] RSS error {url}: empty_body", file=sys.stderr)
        return None

    # Write cache
    if ttl > 0:
        try:
            with open(data_path, "wb") as f:
                f.write(b)
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump({"url": url, "fetched_at": time.time(), "bytes": len(b)}, f, separators=(",", ":"))
        except Exception:
            # cache best-effort
            pass

    return b


# -----------------------------------------------------------------------------
# RSS/Atom parser (xml.etree)
# -----------------------------------------------------------------------------

def _text_or_empty(x: Optional[str]) -> str:
    return (x or "").strip()


def _parse_rss_items(url: str, data: bytes) -> List[NewsItem]:
    """
    Lightweight RSS/Atom parser using xml.etree.
    Returns list of NewsItem (published normalized to UTC if parsed).
    """
    text = data.decode("utf-8", errors="ignore").strip()
    if not text:
        return []

    root = ET.fromstring(text)
    items: List[NewsItem] = []

    # RSS: <item>
    for item in root.findall(".//item"):
        title = _text_or_empty(item.findtext("title"))
        summary = _text_or_empty(item.findtext("description"))
        pub = (
            item.findtext("pubDate")
            or item.findtext("{http://purl.org/dc/elements/1.1/}date")
            or item.findtext("date")
            or ""
        )
        dt = parse_rss_datetime(pub) if pub else None
        if dt is not None:
            dt = _coerce_utc(dt)

        items.append(
            NewsItem(
                provider=url,
                title=title,
                summary=summary,
                published=dt,
            )
        )

    # Atom: <entry>
    if not items:
        atom_ns = "{http://www.w3.org/2005/Atom}"
        for entry in root.findall(f".//{atom_ns}entry"):
            title = _text_or_empty(entry.findtext(f"{atom_ns}title"))
            summary = _text_or_empty(entry.findtext(f"{atom_ns}summary"))
            pub = (
                entry.findtext(f"{atom_ns}updated")
                or entry.findtext(f"{atom_ns}published")
                or ""
            )
            dt = parse_rss_datetime(pub) if pub else None
            if dt is not None:
                dt = _coerce_utc(dt)

            items.append(
                NewsItem(
                    provider=url,
                    title=title,
                    summary=summary,
                    published=dt,
                )
            )

    return items


def fetch_rss_sources(lookback_min: int, errors: List[str], debug: bool) -> List[NewsItem]:
    """
    Fetch all RSS feeds and filter by lookback window.
    - Items with no parseable timestamp are included (but may not match anything).
    """
    timeout_sec = env_int("NEWS_RSS_TIMEOUT_SEC", default=6, lo=2, hi=30)
    max_bytes = env_int("NEWS_RSS_MAX_BYTES", default=262144, lo=4096, hi=1048576)

    urls = get_rss_feed_urls()
    cutoff = utc_now() - timedelta(minutes=lookback_min)

    all_items: List[NewsItem] = []

    for url in urls:
        raw = _fetch_url(url, timeout_sec=timeout_sec, max_bytes=max_bytes, errors=errors, debug=debug)
        if raw is None:
            continue

        try:
            items = _parse_rss_items(url, raw)
        except Exception:
            errors.append(f"rss_exc:{url}:parse_failed")
            if debug:
                print(f"[news] RSS error {url}: parse_failed", file=sys.stderr)
            continue

        fresh: List[NewsItem] = []
        for it in items:
            if it.published is None:
                # Include undated items (rarely useful, but harmless)
                fresh.append(it)
                continue
            if it.published >= cutoff:
                fresh.append(it)

        all_items.extend(fresh)

        if debug:
            # Mark "(cache)" if cache exists and TTL enabled (best-effort detection)
            data_path, meta_path = _cache_paths(url)
            cache_flag = ""
            ttl = env_int("NEWS_RSS_CACHE_TTL_SEC", default=3600, lo=0, hi=86400)
            if ttl > 0 and os.path.exists(data_path) and os.path.exists(meta_path):
                cache_flag = " (cache)"
            print(f"[news] RSS {url} -> {len(fresh)} fresh items{cache_flag}", file=sys.stderr)

    return all_items


# -----------------------------------------------------------------------------
# Keyword matching (FIX: single-word uses word boundaries)
# -----------------------------------------------------------------------------

_WORD_RE = re.compile(r"^[a-z0-9_]+$", flags=re.IGNORECASE)


@lru_cache(maxsize=4096)
def _word_boundary_regex(word: str) -> re.Pattern:
    # Single-word match as a whole token
    return re.compile(rf"\b{re.escape(word)}\b", flags=re.IGNORECASE)


def kw_in_text(keyword: str, text: str) -> bool:
    """
    Public helper: returns True if keyword matches text under BotA rules.
    - single word: word boundary regex
    - phrase/multiword: substring match (case-insensitive)
    """
    if not keyword or not text:
        return False

    kw = keyword.strip().lower()
    t = text.lower()

    if not kw:
        return False

    # single word -> word boundary regex
    if _WORD_RE.match(kw):
        return _word_boundary_regex(kw).search(t) is not None

    # phrase -> substring
    return kw in t


def _hits(keywords: List[str], text: str) -> List[str]:
    out: List[str] = []
    for k in keywords:
        if kw_in_text(k, text):
            out.append(k)
    return out


# -----------------------------------------------------------------------------
# Lexicons (conservative; may be extended)
# -----------------------------------------------------------------------------

_FALSE_POSITIVE_FILTERS: List[str] = [
    "eurovision",
    "euroleague",
    "euro truck",
    "dollar tree",
    "dollar general",
    "pound cake",
]

# Currency-specific macro phrases (minimal; conservative)
_EUR_POS: List[str] = [
    # Central bank events
    "ecb hikes", "ecb raises", "ecb hawkish", "lagarde hawkish",
    "ecb holds rates", "ecb pause", "ecb steady",
    # Inflation / data
    "eurozone inflation rises", "sticky inflation eurozone",
    "euro zone cpi", "eurozone cpi above", "inflation above target",
    "eurozone gdp beats", "eurozone pmi beats", "german gdp",
    "german ifo", "german zew",
    # Price action language
    "euro strengthens", "strong euro", "euro rises", "euro gains",
    "euro rallies", "eur usd rises", "eurusd rallies",
    "euro hits high", "euro climbs",
    # Risk / macro
    "risk on", "risk appetite", "dollar weakens",
]
_EUR_NEG: List[str] = [
    # Central bank events
    "ecb cuts", "ecb dovish", "ecb rate cut", "lagarde dovish",
    "ecb signals cut",
    # Economic weakness
    "eurozone recession", "euro weakens", "weak euro",
    "eurozone slowdown", "eurozone contraction", "eurozone gdp miss",
    "eurozone pmi below", "german recession", "germany contracts",
    # Price action language
    "euro falls", "euro drops", "euro slides", "euro tumbles",
    "eur usd falls", "eurusd drops", "euro hits low",
    # Risk / macro
    "risk off", "flight to safety", "dollar strengthens",
]

_USD_POS: List[str] = [
    # Central bank events
    "fed hikes", "fed raises", "fed hawkish", "powell hawkish",
    "fed holds", "fed steady", "fed pause hawkish",
    "treasury yields rise", "yields climb", "10 year yield rises",
    # Data beats
    "strong dollar", "dollar strengthens", "dollar rises",
    "hot us inflation", "cpi hotter", "us cpi above",
    "us jobs beat", "nfp beats", "payrolls beat",
    "us gdp beats", "us retail sales beat", "ism beats",
    "dollar index rises", "dxy rises", "dxy gains",
    # Price action
    "dollar rallies", "dollar climbs", "dollar hits high",
]
_USD_NEG: List[str] = [
    # Central bank events
    "fed cuts", "fed dovish", "fed rate cut", "powell dovish",
    "fed signals cut", "fed pivot",
    # Data misses
    "weak dollar", "dollar falls", "dollar drops",
    "us recession", "jobless claims rise", "us jobs miss",
    "nfp miss", "us gdp miss", "us cpi below",
    "dollar index falls", "dxy falls", "dxy drops",
    # Price action
    "dollar slides", "dollar tumbles", "dollar hits low",
    "yields fall", "treasury yields drop",
]

_GBP_POS: List[str] = [
    # Central bank events
    "boe hikes", "boe raises", "boe hawkish", "bailey hawkish",
    "boe holds", "boe steady", "boe pause",
    # Data beats
    "uk inflation rises", "uk cpi above", "uk gdp beats",
    "uk pmi beats", "uk retail sales beat",
    # Price action
    "sterling strengthens", "pound strengthens", "pound rises",
    "pound gains", "sterling gains", "gbp usd rises",
    "cable rises", "pound rallies", "pound climbs",
]
_GBP_NEG: List[str] = [
    # Central bank events
    "boe cuts", "boe dovish", "boe rate cut", "bailey dovish",
    "boe signals cut",
    # Economic weakness
    "uk recession", "uk contraction", "uk gdp miss",
    "uk pmi below", "uk slowdown",
    # Price action
    "sterling weakens", "pound falls", "pound drops",
    "pound slides", "sterling slides", "gbp usd falls",
    "cable falls", "pound tumbles", "pound hits low",
]

_JPY_POS: List[str] = [
    "boj hikes",
    "boj raises",
    "boj hawkish",
    "yen strengthens",
    "jpy intervention",
]
_JPY_NEG: List[str] = [
    "boj dovish",
    "yen weakens",
    "yen falls",
    "ultra-loose policy",
]

# Risk-on / risk-off
# NOTE: single-word "war" is now safe because it uses \bwar\b (won't match "Warsh").
_RISK_OFF: List[str] = [
    "flight to safety",
    "flight to quality",
    "safe haven",
    "market crash",
    "global recession",
    "banking crisis",
    "geopolitical tension",
    "tensions rise",
    "contagion",
    "systemic risk",
    "credit default",
    "liquidity crisis",
    "black swan",
    "equity selloff",
    "debt crisis",
    "yield curve inversion",
    "inverted yield curve",
    "war",
]
_RISK_ON: List[str] = [
    "risk appetite",
    "risk-on",
    "risk on",
    "stocks surge",
    "equity rally",
    "markets rally",
    "bull market",
    "risk sentiment improves",
]

# Export aliases (optional convenience)
RISK_OFF = _RISK_OFF
RISK_ON = _RISK_ON


# -----------------------------------------------------------------------------
# Scoring
# -----------------------------------------------------------------------------

def _apply_lex(scores: Dict[str, float], currency: str, phrases: List[str], text: str, delta: float) -> int:
    """
    Apply list of phrases to currency score; returns number of hits.
    """
    hits = 0
    for p in phrases:
        if kw_in_text(p, text):
            scores[currency] = scores.get(currency, 0.0) + delta
            hits += 1
    return hits


def score_item_for_pair(item: NewsItem, pair: str) -> Tuple[float, int, List[str]]:
    """
    Returns (bias, hits, labels)
      bias: (score[base] - score[quote]) with risk adjustments
      hits: total keyword hits
      labels: simple tags like ["risk_off"] for debug
    """
    pair = (pair or "").upper().strip()
    if len(pair) != 6:
        return 0.0, 0, []

    text = (item.title + " " + item.summary).strip()
    if not text:
        return 0.0, 0, []

    t = text.lower()

    for bad in _FALSE_POSITIVE_FILTERS:
        if bad in t:
            return 0.0, 0, []

    base = pair[:3]
    quote = pair[3:]

    scores: Dict[str, float] = {"EUR": 0.0, "USD": 0.0, "GBP": 0.0, "JPY": 0.0}
    total_hits = 0
    labels: List[str] = []

    total_hits += _apply_lex(scores, "EUR", _EUR_POS, t, +1.0)
    total_hits += _apply_lex(scores, "EUR", _EUR_NEG, t, -1.0)

    total_hits += _apply_lex(scores, "USD", _USD_POS, t, +1.0)
    total_hits += _apply_lex(scores, "USD", _USD_NEG, t, -1.0)

    total_hits += _apply_lex(scores, "GBP", _GBP_POS, t, +1.0)
    total_hits += _apply_lex(scores, "GBP", _GBP_NEG, t, -1.0)

    total_hits += _apply_lex(scores, "JPY", _JPY_POS, t, +1.0)
    total_hits += _apply_lex(scores, "JPY", _JPY_NEG, t, -1.0)

    # Risk overlays
    ro = _hits(_RISK_OFF, t)
    rn = _hits(_RISK_ON, t)

    if ro:
        labels.append("risk_off")
        total_hits += len(ro)
        # risk-off: USD & JPY benefit, EUR/GBP lose
        scores["USD"] += 0.3
        scores["JPY"] += 0.3
        scores["EUR"] -= 0.3
        scores["GBP"] -= 0.3

    if rn:
        labels.append("risk_on")
        total_hits += len(rn)
        # risk-on: EUR/GBP benefit relative to USD/JPY
        scores["USD"] -= 0.3
        scores["JPY"] -= 0.3
        scores["EUR"] += 0.3
        scores["GBP"] += 0.3

    if base not in scores or quote not in scores:
        return 0.0, 0, []

    bias = scores[base] - scores[quote]

    # Noise guard
    if abs(bias) < 0.1:
        return 0.0, 0, []

    # Clamp to a conservative bound so macro6 mapping is stable
    if bias > 1.0:
        bias = 1.0
    if bias < -1.0:
        bias = -1.0

    return bias, total_hits, labels


def macro6_from_bias(bias: float) -> int:
    """
    Map bias in [-1..+1] to macro6 [0..6], neutral=3.
    """
    if bias > 1.0:
        bias = 1.0
    if bias < -1.0:
        bias = -1.0

    if bias <= -0.6:
        return 0
    if bias <= -0.3:
        return 1
    if bias <= -0.1:
        return 2
    if bias < 0.1:
        return 3
    if bias < 0.3:
        return 4
    if bias < 0.6:
        return 5
    return 6


def aggregate(items: List[NewsItem], pair: str, debug: bool = False) -> Tuple[float, int, int, int]:
    """
    Returns: (score, macro6, hit_items, total_hits)
    score is averaged over USED items.
    """
    min_hit_items = env_int("NEWS_MIN_HIT_ITEMS", default=2, lo=1, hi=20)

    total = 0.0
    used = 0
    hit_items = 0
    total_hits = 0

    max_debug_matches = env_int("NEWS_DEBUG_MATCHES_MAX", default=10, lo=0, hi=200)
    dbg_printed = 0

    for it in items:
        bias, hits, labels = score_item_for_pair(it, pair)
        if bias == 0.0:
            continue
        used += 1
        total += bias
        if hits > 0:
            hit_items += 1
            total_hits += hits

        if debug and dbg_printed < max_debug_matches:
            # Show why this item matched
            labels_s = ",".join(labels) if labels else "-"
            print(
                f"[news] match pair={pair} hits={hits} bias={bias:+.3f} labels={labels_s} title={it.title}",
                file=sys.stderr,
            )
            dbg_printed += 1

    if used == 0 or hit_items < min_hit_items:
        # Fail-closed neutral
        return 0.0, 3, hit_items, total_hits

    score = total / float(used)
    # Clamp + map
    if score > 1.0:
        score = 1.0
    if score < -1.0:
        score = -1.0
    m6 = macro6_from_bias(score)
    return float(round(score, 4)), int(m6), int(hit_items), int(total_hits)


# -----------------------------------------------------------------------------
# Engine
# -----------------------------------------------------------------------------

def run_engine(pair: str, debug: bool = False) -> Dict[str, object]:
    pair = (pair or "").upper().strip()

    news_on = env_str("NEWS_ON", "1").strip().lower()
    if news_on in ("0", "false", "off", ""):
        return {
            "pair": pair,
            "score": 0.0,
            "macro6": 3,
            "meta": {"provider": "off", "count": 0, "hits": 0, "hit_items": 0, "details": []},
        }

    lookback = env_int("NEWS_LOOKBACK_MIN", default=360, lo=15, hi=4320)
    errors: List[str] = []

    items = fetch_rss_sources(lookback_min=lookback, errors=errors, debug=debug)

    provider = "none"
    if items:
        provider = "rss"

    score = 0.0
    macro6 = 3
    hit_items = 0
    total_hits = 0

    if items:
        score, macro6, hit_items, total_hits = aggregate(items, pair, debug=debug)

        if debug:
            print(
                f"[news] agg provider={provider} items={len(items)} hit_items={hit_items} total_hits={total_hits} score={score:.4f} macro6={macro6}",
                file=sys.stderr,
            )

        # If we had items but no usable signal -> treat as none (fail-closed)
        if hit_items == 0:
            provider = "rss"

    meta: Dict[str, object] = {
        "provider": provider,
        "count": int(len(items)),
        "hits": int(total_hits),
        "hit_items": int(hit_items),
        "details": [],
    }
    if errors:
        meta["errors"] = errors

    # If provider is rss but items==0 -> "none"
    if provider == "rss" and len(items) == 0:
        meta["provider"] = "none"

    return {"pair": pair, "score": float(score), "macro6": int(macro6), "meta": meta}


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description="BotA RSS macro engine (JSON output)")
    ap.add_argument("pair", nargs="?", default="EURUSD", help="FX pair, e.g. EURUSD")
    ap.add_argument("--debug", action="store_true", help="Debug logs to stderr")
    args = ap.parse_args()

    res = run_engine(args.pair, debug=args.debug)
    print(json.dumps(res, separators=(",", ":")))


if __name__ == "__main__":
    main()
