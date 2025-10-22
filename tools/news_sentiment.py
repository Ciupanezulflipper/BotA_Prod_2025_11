import os, time, json, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone

# Simple lexicons (title + description)
POS = set("beat beats expansion strong accelerate improving cools eases dovish stimulus optimistic gain rebound bullish upside upgrade".split())
NEG = set("miss misses contraction weak slow slowing slump deteriorate surge inflation hawkish downgrade risk bearish downside".split())

def _now_utc():
    return datetime.now(timezone.utc)

def _ts_iso(dt):  # RFC3339-ish
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

def _fetch_url(url, timeout=12):
    req = urllib.request.Request(url, headers={"User-Agent":"tomabot/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode()

def _score_text(txt:str) -> float:
    if not txt: return 0.0
    s = txt.lower()
    score = 0
    for w in POS:
        if w in s: score += 1
    for w in NEG:
        if w in s: score -= 1
    # clamp to -3..+3 then normalize to -1..+1
    if score > 3: score = 3
    if score < -3: score = -3
    return score / 3.0

def _weighted_article_score(a):
    title = a.get("title","") or ""
    desc  = a.get("description","") or a.get("summary","") or ""
    s = 0.7*_score_text(title) + 0.3*_score_text(desc)
    # tiny weight if obviously irrelevant to FX
    text = (title + " " + desc).lower()
    if all(k not in text for k in ["eur","euro","usd","dollar","ecb","fed","fomc","inflation","cpi","hike","cut","pmi","zew","ifo","germany","eurozone"]):
        s *= 0.4
    return max(-1,min(1,s))

def _direction_bias(text):
    # +1 if EUR-bullish / USD-bearish; -1 if USD-bullish / EUR-bearish
    t = text.lower()
    eur_bias = any(k.strip() in t for k in (os.environ.get("NEWS_EUR_KEYWORDS","").split(",")))
    usd_bias = any(k.strip() in t for k in (os.environ.get("NEWS_USD_KEYWORDS","").split(",")))
    if eur_bias and not usd_bias: return +1
    if usd_bias and not eur_bias: return -1
    return 0

def fetch_and_score(pair="EURUSD"):
    if os.environ.get("NEWS_ON","1") != "1":
        return 0.0, {"provider":"off","count":0,"details":[]}

    lookback = int(os.environ.get("NEWS_LOOKBACK_MIN","180"))
    limit = int(os.environ.get("NEWS_MAX_ARTICLES","25"))
    to_dt = _now_utc()
    from_dt = to_dt - timedelta(minutes=lookback)

    q_list = ["EURUSD","EUR USD","euro dollar","ECB","FOMC","Federal Reserve","inflation eurozone","US CPI","Eurozone PMI"]
    q = urllib.parse.quote(" OR ".join(q_list))

    # Provider 1: NewsAPI
    key = os.environ.get("NEWS_API_KEY")
    articles = []
    provider = None
    if key:
        provider = "newsapi"
        url = (f"https://newsapi.org/v2/everything?"
               f"q={q}&language=en&from={_ts_iso(from_dt)}&to={_ts_iso(to_dt)}"
               f"&pageSize={limit}&sortBy=publishedAt&apiKey={key}")
        try:
            j = json.loads(_fetch_url(url))
            if j.get("status")=="ok":
                for a in j.get("articles",[]):
                    articles.append({"title":a.get("title"),"description":a.get("description")})
        except Exception as e:
            provider = None

    # Provider 2: Finnhub (fallback)
    if not articles:
        fk = os.environ.get("FINNHUB_API_KEY")
        if fk:
            provider = "finnhub"
            # economic news proxy via forex keyword
            url = f"https://finnhub.io/api/v1/news?category=forex&from={from_dt.date()}&to={to_dt.date()}&token={fk}"
            try:
                j = json.loads(_fetch_url(url))
                for a in j[:limit]:
                    articles.append({"title":a.get("headline"),"description":a.get("summary")})
            except Exception as e:
                provider = None

    # Provider 3: MarketAux (fallback)
    if not articles:
        mk = os.environ.get("MARKETAUX_API_KEY")
        if mk:
            provider = "marketaux"
            url = (f"https://api.marketaux.com/v1/news/all?"
                   f"filter_entities=true&language=en&limit={limit}&"
                   f"api_token={mk}&query={q}")
            try:
                j = json.loads(_fetch_url(url))
                for a in j.get("data",[]):
                    articles.append({"title":a.get("title"),"description":a.get("description")})
            except Exception as e:
                provider = None

    if not articles:
        return 0.0, {"provider":"none","count":0,"details":[]}

    details = []
    raw = []
    for a in articles:
        s = _weighted_article_score(a)
        bias = _direction_bias((a.get("title","") or "") + " " + (a.get("description","") or ""))
        raw.append( (s,bias,a) )

    if not raw:
        return 0.0, {"provider":provider,"count":0,"details":[]}

    # EURUSD score: EUR-bullish (+) vs USD-bullish (-)
    adj = []
    for s,b,a in raw:
        if b==0:
            adj.append(s*0.4)
        else:
            adj.append(s*b*1.0)
        details.append({"title":a.get("title","")[:96], "s":round(s,2), "bias":b})

    # average & clamp to [-1..+1]
    if adj:
        avg = sum(adj)/len(adj)
        if avg > 1: avg = 1
        if avg < -1: avg = -1
    else:
        avg = 0.0

    return avg, {"provider":provider,"count":len(details),"details":details[:6]}
