#!/usr/bin/env python3
import os, time, json, hashlib, datetime as dt
import urllib.parse, urllib.request

def _now_utc(): return dt.datetime.now(dt.timezone.utc)
def _read(k): return os.environ.get(k, "")
def _http_get(url: str, headers: dict = None, timeout=12):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8")

# in-proc throttle
_BUCKET = {}
def _throttle(name: str, per_min: int):
    if per_min <= 0: return
    now = time.time()
    hist = [t for t in _BUCKET.get(name, []) if now - t < 60]
    if len(hist) >= per_min:
        sleep_s = 60 - (now - hist[0])
        if sleep_s > 0: time.sleep(sleep_s)
        now = time.time()
        hist = [t for t in hist if now - t < 60]
    hist.append(time.time()); _BUCKET[name] = hist

def _dedupe(x: list):
    seen, out = set(), []
    for it in x:
        k = it.get("id") or hashlib.sha1((it.get("url","")+it.get("title","")).encode()).hexdigest()[:12]
        if k in seen: continue
        seen.add(k); it["id"] = k; out.append(it)
    return out

def _fetch_marketaux(symbol: str, window_h: int, limit: int):
    key = _read("MARKETAUX_API_KEY")
    if not key: raise RuntimeError("MARKETAUX_API_KEY missing")
    _throttle("marketaux", int(os.environ.get("MARKETAUX_RATE_PER_MIN","3")))
    base = "https://api.marketaux.com/v1/news/all"
    q = urllib.parse.quote_plus(f"{symbol} OR forex OR currency")
    after = (_now_utc() - dt.timedelta(hours=window_h)).isoformat(timespec="seconds")
    url = f"{base}?api_token={key}&limit={limit}&filter_entities=true&language=en&q={q}&published_after={after}"
    data = json.loads(_http_get(url))
    items = []
    for d in data.get("data", []):
        items.append({"source":"marketaux","title":d.get("title",""),"url":d.get("url",""),
                      "published_at":d.get("published_at",""),"summary":d.get("snippet") or d.get("description","")})
    return _dedupe(items)

def _fetch_newsapi(symbol: str, window_h: int, limit: int):
    key = _read("NEWS_API_KEY")
    if not key: raise RuntimeError("NEWS_API_KEY missing")
    _throttle("newsapi", int(os.environ.get("NEWSAPI_RATE_PER_MIN","2")))
    base = "https://newsapi.org/v2/everything"
    q = urllib.parse.quote_plus(f"{symbol} OR forex OR currency")
    after = (_now_utc() - dt.timedelta(hours=window_h)).isoformat(timespec="seconds")
    url = f"{base}?q={q}&language=en&pageSize={limit}&from={after}&apiKey={key}"
    data = json.loads(_http_get(url))
    items = []
    for a in data.get("articles", []):
        items.append({"source":"newsapi","title":a.get("title",""),"url":a.get("url",""),
                      "published_at":a.get("publishedAt",""),"summary":a.get("description","")})
    return _dedupe(items)

def _fetch_eodhd(symbol: str, window_h: int, limit: int):
    key = _read("EODHD_API_KEY")
    if not key: raise RuntimeError("EODHD_API_KEY missing")
    _throttle("eodhd_news", int(os.environ.get("EODHD_NEWS_RATE_PER_MIN","2")))
    base = "https://eodhd.com/api/news"
    q = urllib.parse.quote_plus(f"{symbol} forex currency")
    after = int((_now_utc() - dt.timedelta(hours=window_h)).timestamp())
    url = f"{base}?api_token={key}&limit={limit}&offset=0&q={q}&from={after}"
    data = json.loads(_http_get(url))
    items = []
    for d in data:
        items.append({"source":"eodhd","title":d.get("title",""),"url":d.get("link",""),
                      "published_at":d.get("date",""),"summary":d.get("content","")})
    return _dedupe(items)

def fetch_headlines(symbol: str, window_hours: int = 12, limit: int = 8):
    errs = []
    for fn in (_fetch_marketaux, _fetch_newsapi, _fetch_eodhd):
        try:
            out = fn(symbol, window_hours, limit)
            if out: return out
        except Exception as e:
            errs.append(str(e))
    raise RuntimeError("All news providers failed: " + " | ".join(errs))

if __name__ == "__main__":
    import json, os
    sym = os.environ.get("TEST_SYMBOL","EURUSD")
    print(json.dumps(fetch_headlines(sym), indent=2))
