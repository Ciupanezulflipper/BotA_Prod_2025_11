#!/usr/bin/env python3
"""
Block repeated sends for the same (pair, tf) within DUPE_WINDOW_MIN minutes.
State persisted in ~/bot-a/data/dupe_guard.json
"""
import os, json, time, pathlib, functools

DATA = pathlib.Path(os.path.expanduser('~/bot-a/data'))
DATA.mkdir(parents=True, exist_ok=True)
STATE = DATA / 'dupe_guard.json'

def _now(): return int(time.time())
def _load():
    try: return json.loads(STATE.read_text())
    except Exception: return {}
def _save(obj):
    try: STATE.write_text(json.dumps(obj, ensure_ascii=False))
    except Exception: pass

def key_from_kwargs(kwargs):
    # Try common names first, fall back to stringifying args
    pair = kwargs.get('pair') or kwargs.get('symbol') or 'NA'
    tf   = kwargs.get('tf')   or kwargs.get('timeframe') or 'NA'
    return f"{pair}_{tf}"

def anti_dupe_sender(send_fn, window_min=None, journal_append_fn=None):
    win = window_min or float(os.getenv('DUPE_WINDOW_MIN', '60'))
    win_s = int(win * 60)

    @functools.wraps(send_fn)
    def wrapped(*args, **kwargs):
        st = _load()
        k = key_from_kwargs(kwargs)
        last = int(st.get(k, 0))
        now = _now()
        if last and (now - last) < win_s:
            # Optional journal note
            if journal_append_fn:
                journal_append_fn(event="FILTERED",
                                  pair=kwargs.get('pair', 'NA'),
                                  tf=kwargs.get('tf', 'NA'),
                                  score=kwargs.get('score', 0),
                                  conf=kwargs.get('conf', 0),
                                  reason=f"dupe<{win}m>",
                                  signal_id=kwargs.get('signal_id', ''),
                                  source='anti_dupe_gate')
            return {"ok": False, "filtered": True, "why": f"dupe<{win}m>", "key": k}
        # pass through
        res = send_fn(*args, **kwargs)
        st[k] = now
        _save(st)
        return res
    return wrapped
