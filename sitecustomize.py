# SEP v3.3 — Telegram send gate & CSV side-writer (Termux-safe)
# Runs automatically because its name is "sitecustomize.py"
# If you see "bash: syntax error", you pasted Python into bash—use this heredoc.

import os, re, time, threading
from datetime import datetime
from urllib.parse import urlparse
import json

# --- simple, safe logger ------------------------------------------------------
_LOG_PATH = os.path.expanduser("~/BotA/run.log")
def _log(msg: str):
    try:
        os.makedirs(os.path.dirname(_LOG_PATH), exist_ok=True)
        with open(_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(msg.rstrip()+"\n")
    except Exception:
        pass  # best effort only

# --- env helpers --------------------------------------------------------------
def _getenv_str(k, default=""):
    v = os.getenv(k)
    return v if v is not None and v != "" else default

def _getenv_float(k, default):
    v = _getenv_str(k, "")
    try:
        return float(v)
    except Exception:
        return float(default)

def _getenv_int(k, default):
    v = _getenv_str(k, "")
    try:
        return int(v)
    except Exception:
        return int(default)

# --- CSV writer ---------------------------------------------------------------
_CSV_PATH = os.path.expanduser("~/BotA/trades.csv")
def _csv_append(row):
    try:
        os.makedirs(os.path.dirname(_CSV_PATH), exist_ok=True)
        import csv
        with open(_CSV_PATH, "a", newline="") as f:
            csv.writer(f).writerow(row)
        _log("[SITE] csv wrote: " + "|".join(map(str,row)))
    except Exception as e:
        _log(f"[SITE] csv error: {e}")

# --- parse helpers ------------------------------------------------------------
_utc_re_full = re.compile(r"t=([0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z)")
_utc_re_day  = re.compile(r"t=([0-9]{4}-[0-9]{2}-[0-9]{2})Z")
_vote_re     = re.compile(r"^(H1|H4|D1):.*?\bvote=([+\-]?\d)\b", re.M)
_rsi_re      = re.compile(r"^(H1|H4|D1):.*?\bRSI14=([0-9.]+)\b", re.M)
_pair_re     = re.compile(r"^===\s*([A-Z]{6}|[A-Z]+/[A-Z]+)\s*snapshot\s*===", re.M)
_dir_re      = re.compile(r"\bSignal:\s*(BUY|SELL)\b")
_num = r"([0-9]+\.[0-9]+)"
_entry_re    = re.compile(r"\bEntry:\s*"+_num)
_tp_re       = re.compile(r"\bTP:\s*"+_num)
_sl_re       = re.compile(r"\bSL:\s*"+_num)
_atr_re      = re.compile(r"\bATR:\s*"+_num)

def _to_epoch_utc(s: str):
    # Accept full UTC "YYYY-MM-DDTHH:MM:SSZ" or date-only "YYYY-MM-DDZ"
    try:
        if "T" in s:
            dt = datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ")
        else:
            dt = datetime.strptime(s, "%Y-%m-%d")
        return int(dt.replace(tzinfo=None).timestamp())
    except Exception:
        return None

def _parse_time_stamps(text: str):
    ts = []
    for m in _utc_re_full.finditer(text):
        e = _to_epoch_utc(m.group(1))
        if e: ts.append(e)
    for m in _utc_re_day.finditer(text):
        e = _to_epoch_utc(m.group(1))
        if e: ts.append(e)
    return ts

def _parse_votes(text: str):
    votes = {"H1":0,"H4":0,"D1":0}
    for tf, v in _vote_re.findall(text):
        try:
            votes[tf] = int(v)
        except Exception:
            pass
    weighted = votes["H1"]*1 + votes["H4"]*2 + votes["D1"]*3
    return votes, weighted

def _parse_fields(text: str):
    pair = None
    m = _pair_re.search(text)
    if m: pair = m.group(1)
    direction = (_dir_re.search(text) or [None, None])[1]
    entry     = (_entry_re.search(text) or [None, None])[1]
    tp        = (_tp_re.search(text)    or [None, None])[1]
    sl        = (_sl_re.search(text)    or [None, None])[1]
    atr       = (_atr_re.search(text)   or [None, None])[1]
    return pair, direction, entry, tp, sl, atr

def _rsi_chop(text: str):
    # If RSI is shown for H1 (or any tf), block when in 45–55 zone
    found = False
    for tf, r in _rsi_re.findall(text):
        try:
            v = float(r)
            if 45.0 <= v <= 55.0:
                found = True
                break
        except Exception:
            pass
    return found

# --- session guards -----------------------------------------------------------
def _within_session():
    start = _getenv_str("TRADE_UTC_START", "00:00")
    end   = _getenv_str("TRADE_UTC_END",   "23:59")
    try:
        now_hm = time.strftime("%H:%M", time.gmtime())
        return (start <= now_hm <= end)
    except Exception:
        return True  # fail-open

def _weekend_cutoffs():
    fri_cut = _getenv_str("FRIDAY_UTC_CUTOFF","")
    mon_start = _getenv_str("MONDAY_UTC_START","")
    wd = int(time.strftime("%w", time.gmtime()))  # 0=Sun..6=Sat
    hm = time.strftime("%H:%M", time.gmtime())
    # Friday cutoff
    if wd == 5 and fri_cut and hm >= fri_cut:
        return False
    # Saturday block always
    if wd == 6:
        return False
    # Monday delayed start
    if wd == 1 and mon_start and hm < mon_start:
        return False
    return True

# --- dedupe -------------------------------------------------------------------
_last_allow_lock = threading.Lock()
_last_allow_ts = 0

def _cooldown_ok():
    global _last_allow_ts
    win_min = _getenv_int("DEDUPE_WINDOW_MIN", 30)
    if win_min <= 0: 
        return True
    with _last_allow_lock:
        now = time.time()
        if now - _last_allow_ts < win_min*60:
            return False
        return True

# --- ATR sanity ---------------------------------------------------------------
def _atr_ok(atr_str: str):
    if not atr_str: 
        return False, "ATR missing"
    try:
        atr = float(atr_str)
    except Exception:
        return False, "ATR parse"
    floor = _getenv_float("ATR_MIN_FLOOR", 0.0020)
    cap   = _getenv_float("ATR_SPIKE_ABS", 0.0200)  # 200 pips hard cap
    if atr < floor:
        return False, f"ATR below floor ({atr} < {floor})"
    if atr > cap:
        return False, f"ATR spike ({atr} > {cap})"
    return True, ""

# --- time-skew guard ----------------------------------------------------------
def _skew_ok(text: str):
    # Collect timeframe timestamps present in message; ignore if < 2
    stamps = _parse_time_stamps(text)
    if len(stamps) < 2:
        return True, ""  # not enough info → do not block
    skew = max(stamps) - min(stamps)
    limit = _getenv_int("TIME_SKEW_SEC", 3600)  # default 1 hour
    if skew > limit:
        return False, f"skew {skew}s > {limit}s"
    return True, ""

# --- vote threshold check -----------------------------------------------------
def _weighted_ok(weighted: int):
    # Enforce weighted confluence (default ±4)
    th_buy  = _getenv_int("VOTE_BUY_THRESHOLD", 4)
    th_sell = _getenv_int("VOTE_SELL_THRESHOLD",-4)
    if weighted >= th_buy or weighted <= th_sell:
        return True
    return False

# --- Telegram monkeypatch -----------------------------------------------------
try:
    import requests as _requests
    if getattr(_requests, "_sep_wrapped", False) is not True:
        _real_post = _requests.post

        def patched_post(url, *args, **kwargs):
            try:
                # Only inspect Telegram sendMessage-like requests
                u = str(url)
                is_tg = "api.telegram.org" in u and (u.endswith("/sendMessage") or "/sendMessage?" in u)
                if not is_tg:
                    return _real_post(url, *args, **kwargs)

                # Extract text (supports json= or data= payloads)
                text = ""
                if "json" in kwargs and isinstance(kwargs["json"], dict):
                    text = kwargs["json"].get("text","")
                elif "data" in kwargs and isinstance(kwargs["data"], dict):
                    text = kwargs["data"].get("text","")
                else:
                    # If we cannot read the message, fail-open
                    return _real_post(url, *args, **kwargs)

                # Parse fields
                votes, weighted = _parse_votes(text)
                pair, direction, entry, tp, sl, atr = _parse_fields(text)

                # NEWS pause?
                if _getenv_int("NEWS_PAUSE", 0) == 1:
                    _log("[SITE] block: NEWS_PAUSE=1")
                    return _real_post(url, *args, **kwargs)

                # Session/time windows?
                if not _within_session():
                    _log("[SITE] block: outside trading hours")
                    return _real_post(url, *args, **kwargs)

                if not _weekend_cutoffs():
                    _log("[SITE] block: weekend/cutoff")
                    return _real_post(url, *args, **kwargs)

                # RSI chop guard?
                if _getenv_int("RSI_CHOP_GUARD", 0) == 1 and _rsi_chop(text):
                    _log("[SITE] block: RSI chop 45–55")
                    return _real_post(url, *args, **kwargs)

                # Timeframe skew guard
                ok_skew, why = _skew_ok(text)
                if not ok_skew:
                    _log(f"[SITE] block: time-skew {why}")
                    return _real_post(url, *args, **kwargs)

                # ATR sanity guard
                atr_ok, atr_why = _atr_ok(atr)
                if not atr_ok:
                    _log(f"[SITE] block: {atr_why}")
                    return _real_post(url, *args, **kwargs)

                # Weighted vote threshold
                if not _weighted_ok(weighted):
                    _log(f"[SITE] block: weighted below threshold ({weighted})")
                    return _real_post(url, *args, **kwargs)

                # Cooldown / dedupe window
                if not _cooldown_ok():
                    _log("[SITE] block: dedupe window")
                    return _real_post(url, *args, **kwargs)

                # Allow: record timestamp for dedupe
                global _last_allow_ts
                with _last_allow_lock:
                    _last_allow_ts = time.time()

                _log(f"[SITE] allow: weighted={weighted}")

                # Optional CSV side-write (must have key fields)
                if _getenv_int("SEP_CSV_FALLBACK", 0) == 1 and direction and entry and tp and sl:
                    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                    _csv_append([ts, pair or "", direction, entry, tp, sl, atr or "", str(weighted)])

                # Pass through to Telegram
                return _real_post(url, *args, **kwargs)

            except Exception as e:
                # Fail-open to avoid blocking bot on hook error
                _log(f"[SITE] error passthrough: {e}")
                return _real_post(url, *args, **kwargs)

        _requests.post = patched_post
        _requests._sep_wrapped = True
        _log("[SITE] SEP v3.3 hook active")
except Exception as e:
    _log(f"[SITE] hook init failed: {e}")
