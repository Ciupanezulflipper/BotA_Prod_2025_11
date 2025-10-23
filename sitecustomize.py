# -*- coding: utf-8 -*-
"""
SEP v3.3 hook
- Works without touching bot code (imported automatically as 'sitecustomize')
- Blocks/permits Telegram POSTs based on simple rules
- Appends compact rows to ~/BotA/trades.csv when a strong confluence signal is ALLOWed
  Now recognizes both:
    a) "=== <PAIR> snapshot ==="
    b) "<EMOJI> <PAIR> | <SIDE>" (live broadcast header)
"""
import os, re, time, csv, sys

RUNLOG = os.path.expanduser('~/BotA/run.log')
CSV_PATH = os.path.expanduser('~/BotA/trades.csv')  # symlinked by you to logs/trades.csv

def _log(msg: str):
    try:
        with open(RUNLOG, 'a', encoding='utf-8') as f:
            f.write(f"[SITE] {msg}\n")
    except Exception:
        pass

def _csv_append(row):
    try:
        os.makedirs(os.path.dirname(CSV_PATH), exist_ok=True)
        with open(CSV_PATH, 'a', newline='', encoding='utf-8') as f:
            csv.writer(f).writerow(row)
        _log(f"csv wrote: {row}")
    except Exception as e:
        _log(f"csv error: {e}")

def _in_window(now_utc):
    s = os.getenv('TRADE_UTC_START', '06:00')
    e = os.getenv('TRADE_UTC_END', '20:00')
    try:
        sh, sm = map(int, s.split(':')); eh, em = map(int, e.split(':'))
    except Exception:
        return True
    mins = now_utc.tm_hour*60 + now_utc.tm_min
    m_s = sh*60+sm; m_e = eh*60+em
    return m_s <= mins <= m_e

def _is_news_pause():
    return os.getenv('NEWS_PAUSE','0') == '1'

# robust pair/side/levels extraction
PAIR_PATTS = [
    # === GBPUSD snapshot ===
    re.compile(r"===\s*([A-Z]{6}|[A-Z]+/[A-Z]+)\s*snapshot\s*===", re.I),
    # 🔴 GBPUSD | SELL (header)
    re.compile(r"^\s*\S+\s+([A-Z]{6}|[A-Z]+/[A-Z]+)\s*\|\s*(BUY|SELL)\b", re.I | re.M),
]
SIDE_PATT = re.compile(r"\bSignal:\s*(BUY|SELL)\b", re.I)
ENTRY_PATT = re.compile(r"\bEntry:\s*([0-9]+\.[0-9]+)")
TP_PATT    = re.compile(r"\bTP:\s*([0-9]+\.[0-9]+)")
SL_PATT    = re.compile(r"\bSL:\s*([0-9]+\.[0-9]+)")
ATR_PATT   = re.compile(r"\bATR:\s*([0-9]+\.[0-9]+)")

def _extract(text):
    pair = None; side = None
    for patt in PAIR_PATTS:
        m = patt.search(text)
        if m:
            pair = m.group(1)
            if m.lastindex and m.lastindex >= 2 and not side:
                side = m.group(2).upper()
            break
    if not side:
        m = SIDE_PATT.search(text)
        if m: side = m.group(1).upper()
    def g(p):
        m = p.search(text); return m.group(1) if m else None
    entry = g(ENTRY_PATT); tp = g(TP_PATT); sl = g(SL_PATT); atr = g(ATR_PATT)
    return pair, side, entry, tp, sl, atr

def _weighted_from_votes(text):
    # crude but stable: count SELL as -1, BUY as +1 when present
    s = 0
    for k in ['H1','H4','D1']:
        m = re.search(rf"'{k}':\s*(-?1|0)", text)
        if m: s += int(m.group(1))
    return s  # -3..+3

def _should_allow(text, now_utc):
    # “strong” when votes are all -1 or all +1
    w = _weighted_from_votes(text)
    if not _in_window(now_utc): return False, "outside trading hours", w
    if _is_news_pause(): return False, "NEWS_PAUSE=1", w
    # block RSI chop if visible
    if re.search(r"RSI14=\s*(4[5-9]\.?|5[0-5]\.?)", text):  # 45–55
        return False, "RSI chop 45–55", w
    # strong confluence?
    strong = ("'H1': -1" in text and "'H4': -1" in text and "'D1': -1" in text) or \
             ("'H1': 1" in text and "'H4': 1" in text and "'D1': 1" in text)
    return strong, ("allow strong" if strong else "weak"), w

# ---- requests patch ----
def _wrap_requests():
    import requests
    if getattr(requests, "_sep_wrapped", False):  # idempotent
        return
    _real_post = requests.post

    def patched_post(url, *args, **kwargs):
        try:
            data = kwargs.get("data") or {}
            text = ""
            if isinstance(data, dict):
                text = (data.get("text") or data.get("caption") or "")
            elif isinstance(data, str):
                text = data
            now = time.gmtime()
            allow, reason, weighted = _should_allow(text, now)
            if allow:
                pair, side, entry, tp, sl, atr = _extract(text)
                _log(f"allow: {reason} weighted={weighted} pair={pair} side={side}")
                if side and entry and tp and sl:
                    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", now)
                    _csv_append([ts, pair or "", side, entry, tp, sl, atr or "", str(weighted)])
            else:
                _log(f"block: {reason} weighted={weighted}")
            return _real_post(url, *args, **kwargs)
        except Exception as e:
            _log(f"error passthrough: {e}")
            return _real_post(url, *args, **kwargs)

    requests.post = patched_post
    requests._sep_wrapped = True
    _log("SEP v3.3 hook active")

try:
    _wrap_requests()
except Exception as e:
    _log(f"hook init failed: {e}")
