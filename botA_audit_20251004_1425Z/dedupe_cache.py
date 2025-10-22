import json, os, threading
from datetime import datetime, timedelta

CACHE_PATH = os.path.join(os.getcwd(), "last_signal_cache.json")
TIME_WINDOW_MIN = int(os.getenv("DEDUP_TIME_MIN", "60")) if "DEDUP_TIME_MIN" in os.environ else 60
PRICE_WINDOW_PIPS = float(os.getenv("DEDUP_PRICE_PIPS", "4.0")) if "DEDUP_PRICE_PIPS" in os.environ else 4.0

_lock = threading.Lock()

def _load():
    if not os.path.exists(CACHE_PATH): return []
    try:
        with open(CACHE_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except: return []

def _save(data):
    tmp = CACHE_PATH + ".tmp"
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f)
    os.replace(tmp, CACHE_PATH)

def _pip_size(pair:str)->float:
    return 0.0001 if pair.upper().endswith(("USD","JPY","CHF","CAD","AUD","NZD","NOK","SEK","DKK","ZAR","TRY","PLN","HUF")) else 0.0001

def cleanup_old(max_age_hours=48):
    with _lock:
        data = _load()
        cutoff = datetime.utcnow() - timedelta(hours=max_age_hours)
        data = [e for e in data if _ts(e) and _ts(e) >= cutoff]
        _save(data)

def _ts(e):
    try: return datetime.fromisoformat(e['timestamp'])
    except: return None

def should_send_signal(pair, action, price, time_window_min=TIME_WINDOW_MIN, price_window_pips=PRICE_WINDOW_PIPS, pip=None):
    """Atomic check+reserve to prevent duplicate sends in overlapping runs."""
    pip = pip or _pip_size(pair)
    now = datetime.utcnow()
    with _lock:
        data = _load()
        # duplicate?
        for e in data:
            if e.get('pair')==pair and e.get('action')==action and e.get('status') in ('pending','sent'):
                age = (now - _ts(e)).total_seconds()/60.0 if _ts(e) else 9999
                dist_pips = abs(price - float(e.get('price', price))) / pip
                if age < time_window_min and dist_pips < price_window_pips:
                    return False, f"dedup: {int(age)}m & {dist_pips:.1f} pips"
        # reserve pending
        data.append({
            "pair": pair, "action": action, "price": price,
            "timestamp": now.isoformat(), "status": "pending"
        })
        _save(data)
        return True, None

def mark_signal_sent(pair, action, price, sent:bool):
    """Confirm/clear pending after send attempt."""
    with _lock:
        data = _load()
        for e in reversed(data):
            if e.get('pair')==pair and e.get('action')==action and e.get('status')=='pending':
                e['status'] = 'sent' if sent else 'failed'
                break
        _save(data)
