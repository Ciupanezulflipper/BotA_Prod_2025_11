import os, json

OUT_OF = 6

def _clamp(v, lo=0, hi=OUT_OF):
    try:
        v = int(v)
    except Exception:
        v = 0
    return max(lo, min(hi, v))

def load_sentiment(path=None):
    """
    Reads ~/bot-a/data/news_cache.json (or given path) and returns:
      (score:int 0..6, out_of:int 6, why:str, source:str)
    Falls back safely if file is missing or malformed.
    """
    if path is None:
        path = os.path.expanduser('~/bot-a/data/news_cache.json')
    try:
        with open(path, 'r', encoding='utf-8') as f:
            j = json.load(f)
        score = j.get('score_0_6', j.get('score', 0))
        score = _clamp(score)
        why = j.get('why') or 'auto'
        if isinstance(why, list):
            why = '; '.join(map(str, why))
        src = j.get('sources') or 'news_cache'
        if isinstance(src, list):
            src = ','.join(map(str, src))
        return score, OUT_OF, why, src
    except Exception:
        return 0, OUT_OF, 'empty_news', 'news_cache'

if __name__ == '__main__':
    print(load_sentiment())
