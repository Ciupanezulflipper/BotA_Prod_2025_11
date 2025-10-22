#!/usr/bin/env python3
"""
news.py — headline fetch + event classification + analog-aware scoring

Outputs, per symbol:
  {
    "symbol": "EURUSD",
    "score": +3,                    # [-5..+5], positive = bullish for the SYMBOL
    "bias": "Bearish/Bullish/Neutral",
    "why": "Hawkish Fed rhetoric → USD↑ → EURUSD↓ (news +3)",
    "event_risk": true/false,       # true if high-impact release imminent
    "asof_utc": "YYYY-mm-ddTHH:MM:SSZ"
  }
"""

import os, re, json, time, math, datetime as dt
from pathlib import Path
from typing import Dict, List, Tuple
import feedparser

# Optional sentiment (kept lightweight)
try:
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    _VADER = SentimentIntensityAnalyzer()
except Exception:
    _VADER = None

HOME = Path.home()
LOGS = HOME / "bot-a" / "logs"
DATA = HOME / "bot-a" / "data"
CACHE = LOGS / "news-cache.json"
IMPACT_CSV = DATA / "event_impact.csv"

FEEDS = [
    # Add/remove feeds as you like (RSS only; no API keys)
    "https://www.forexlive.com/feed/news/",
    "https://www.fxstreet.com/rss",
    "https://www.reuters.com/markets/feeds/rss",
    "https://www.investing.com/rss/news.rss",
]

SYMBOL_MAP = {
    # base-quote → which side gains when BASE strengthens
    # For EURUSD: USD↑ → EURUSD↓ ; USD↓ → EURUSD↑
    "EURUSD": {"USD_up":"Bearish", "USD_down":"Bullish", "EUR_up":"Bullish", "EUR_down":"Bearish"},
    "XAUUSD": {"USD_up":"Bearish", "USD_down":"Bullish"},
}

HIGH_IMPACT_HINTS = [
    r"\b(CPI|inflation)\b", r"\bNFP\b", r"\bnonfarm\b",
    r"\bFOMC\b", r"\b(rate decision|hike|cut)\b",
    r"\bPMI\b", r"\bGDP\b",
]

EVENT_PATTERNS = [
    ("US_CPI",  re.compile(r"\b(US|U\.S\.|United States).*(CPI|inflation)\b", re.I)),
    ("US_NFP",  re.compile(r"\b(US|U\.S\.|United States).*(NFP|nonfarm)\b", re.I)),
    ("US_FED",  re.compile(r"\b(Fed|FOMC|Powell|Federal Reserve)\b", re.I)),
    ("EU_ECB",  re.compile(r"\b(ECB|Lagarde|European Central Bank)\b", re.I)),
    ("EU_PMI",  re.compile(r"\b(Eurozone|EU).*(PMI)\b", re.I)),
    ("US_PMI",  re.compile(r"\b(US|U\.S\.|United States).*(PMI)\b", re.I)),
    ("GEN_RATES", re.compile(r"\b(rate decision|rate hike|rate cut|tighten|ease)\b", re.I)),
]

def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)

def _load_impact_table() -> Dict[Tuple[str,str], Dict[str,float]]:
    """
    CSV: event_key,symbol,mean_pips_30m,mean_pips_2h,count,last_seen_utc
    """
    out = {}
    if not IMPACT_CSV.exists():
        return out
    for line in IMPACT_CSV.read_text().splitlines():
        if not line.strip() or line.startswith("#"): continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 6: continue
        ek, sym, m30, m2h, cnt, last = parts[:6]
        try:
            out[(ek, sym)] = {
                "mean_pips_30m": float(m30 or 0),
                "mean_pips_2h":  float(m2h or 0),
                "count":         int(cnt or 0),
                "last_seen_utc": last,
            }
        except:
            continue
    return out

def _headline_sentiment(text: str) -> float:
    if not text: return 0.0
    if _VADER is None: return 0.0
    s = _VADER.polarity_scores(text)
    return s.get("compound", 0.0)  # [-1..+1]

def _classify_event(title: str, summary: str) -> str:
    t = (title or "") + " " + (summary or "")
    for key, rx in EVENT_PATTERNS:
        if rx.search(t):
            return key
    return "OTHER"

def _high_impact_flag(title: str, summary: str) -> bool:
    t = (title or "") + " " + (summary or "")
    return any(re.search(p, t, re.I) for p in HIGH_IMPACT_HINTS)

def _fetch_headlines(max_items=50) -> List[Dict]:
    items: List[Dict] = []
    for url in FEEDS:
        try:
            feed = feedparser.parse(url)
            for e in feed.entries[:max_items]:
                title = getattr(e, "title", "")
                summary = getattr(e, "summary", "") or getattr(e, "description", "")
                published = getattr(e, "published", "") or getattr(e, "updated", "")
                items.append({
                    "title": title,
                    "summary": summary,
                    "published": published,
                    "event_key": _classify_event(title, summary),
                    "sent": _headline_sentiment(title + " " + summary),
                    "hi": _high_impact_flag(title, summary),
                })
        except Exception:
            continue
    # simple recency sort (feedparser published is not always reliable)
    return items[:max_items*len(FEEDS)]

def _event_to_currency_bias(ev: Dict) -> List[Tuple[str,str]]:
    """
    Returns list of (currency, direction), e.g. [("USD","up")] for hawkish Fed headline.
    Uses rough rules + sentiment as a nudge.
    """
    ek = ev.get("event_key","OTHER")
    s  = ev.get("sent",0.0)
    up = "up"; down = "down"
    out: List[Tuple[str,str]] = []

    if ek in ("US_CPI","US_NFP","US_PMI"):
        out.append(("USD", up if s >= -0.05 else up))  # macro prints usually USD↑ on "hot"/"strong" framing
    elif ek == "US_FED":
        out.append(("USD", up if s >= 0 else up))      # hawkish tone bias
    elif ek == "EU_ECB":
        out.append(("EUR", up if s >= 0 else down))    # dovish tone -> EUR↓
    elif ek == "GEN_RATES":
        out.append(("USD", up if s >= 0 else down))
    else:
        # low info, no directional bias
        pass
    return out

def _currency_bias_to_symbol_bias(symbol: str, cur_bias: List[Tuple[str,str]]) -> Tuple[str,int,str]:
    """
    Map currency bias into symbol bias using SYMBOL_MAP.
    Returns (Bias, score_step, why_fragment)
    """
    m = SYMBOL_MAP.get(symbol.upper(), {})
    step = 0
    why = []
    out_bias = "Neutral"
    for cur, dirn in cur_bias:
        key = f"{cur}_up" if dirn=="up" else f"{cur}_down"
        b = m.get(key)
        if not b: continue
        # one contribution per mapping
        delta = 2 if dirn=="up" else -2  # base contribution
        # normalize to symbol sense
        if "Bullish" in b:
            step += +3
            out_bias = "Bullish"
            why.append(f"{cur}↑ → {symbol}↑")
        elif "Bearish" in b:
            step += +3
            out_bias = "Bearish"
            why.append(f"{cur}↑ → {symbol}↓")
    if step == 0: return ("Neutral", 0, "")
    return (out_bias, max(-5, min(5, step)), "; ".join(why))

def _analog_adjust(event_key: str, symbol: str, step: int, table: Dict[Tuple[str,str],Dict]) -> int:
    """
    Adjust raw step using historical analogs:
    - If mean_pips_30m (absolute) big → nudge magnitude up to ±5
    - If count is high → more confidence
    """
    info = table.get((event_key, symbol))
    if not info: return step
    mag = abs(info.get("mean_pips_30m", 0.0))
    cnt = max(1, info.get("count", 1))
    nudge = 0
    if mag >= 12: nudge += 1
    if mag >= 20: nudge += 1
    if cnt >= 10: nudge += 1
    if step > 0: return min(5, step + nudge)
    if step < 0: return max(-5, step - nudge)
    return step

def _blend_symbol(symbol: str, items: List[Dict], table) -> Dict:
    # Weight recent high-impact items stronger; take top 5
    scored = []
    for ev in items:
        cur_bias = _event_to_currency_bias(ev)
        if not cur_bias: continue
        bias, step, why_map = _currency_bias_to_symbol_bias(symbol, cur_bias)
        if step == 0: continue
        step = _analog_adjust(ev["event_key"], symbol, step, table)
        # weight by high-impact & sentiment magnitude
        w = (2.0 if ev.get("hi") else 1.0) * (1.0 + 0.5*abs(ev.get("sent",0.0)))
        scored.append((step, w, ev, bias, why_map))

    if not scored:
        return {
            "symbol": symbol, "score": 0, "bias": "Neutral",
            "why": "-", "event_risk": False, "asof_utc": utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        }

    # Weighted average, clamp
    num = sum(s*w for s,w,_,_,_ in scored[:5])
    den = sum(w for _,w,_,_,_ in scored[:5]) or 1.0
    score = max(-5, min(5, int(round(num/den))))

    # Build explanation from strongest item
    s0,w0,ev0,bias0,why0 = sorted(scored, key=lambda x: abs(x[0]*x[1]), reverse=True)[0]
    ek = ev0.get("event_key","OTHER").replace("_"," ")
    hi = " (high-impact)" if ev0.get("hi") else ""
    why = f"{ek}{hi}: {why0 or 'news flow bias'} (news {score:+d})"
    event_risk = any(ev.get("hi") for _,_,ev,_,_ in scored)

    return {
        "symbol": symbol,
        "score": score,
        "bias": "Bullish" if score>0 else "Bearish" if score<0 else "Neutral",
        "why": why,
        "event_risk": bool(event_risk),
        "asof_utc": utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

def news_for_symbols(symbols: List[str]) -> List[Dict]:
    LOGS.mkdir(parents=True, exist_ok=True)
    DATA.mkdir(parents=True, exist_ok=True)

    # cache throttle (refresh every 90s)
    if CACHE.exists():
        try:
            c = json.loads(CACHE.read_text())
            ts = c.get("_ts", 0)
            if time.time() - ts < 90:
                items = c.get("items", [])
            else:
                raise ValueError
        except Exception:
            items = _fetch_headlines()
    else:
        items = _fetch_headlines()

    c_out = {"_ts": time.time(), "items": items}
    try:
        CACHE.write_text(json.dumps(c_out, ensure_ascii=False))
    except Exception:
        pass

    table = _load_impact_table()
    out = [_blend_symbol(sym, items, table) for sym in symbols]
    return out

if __name__ == "__main__":
    wl = os.getenv("WATCHLIST","EURUSD,XAUUSD").split(",")
    wl = [s.strip().upper() for s in wl if s.strip()]
    res = news_for_symbols(wl)
    print(json.dumps(res, indent=2))
