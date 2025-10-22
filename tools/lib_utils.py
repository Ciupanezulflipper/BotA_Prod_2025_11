#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unified utilities for Bot-A (Termux-friendly).
No external deps, home-directory only, safe file locking, and all helpers
expected by runner/digest/outbox scripts.
"""

import os, io, json, time, hashlib, contextlib, datetime as dt
from typing import Any, Iterable, Optional

# ========= Paths (Termux-safe) =========
BASE_DIR = os.path.expanduser("~/bot-a")
DATA_DIR = os.path.join(BASE_DIR, "data")
LOGS_DIR = os.path.join(BASE_DIR, "logs")

def _choose_tmp_dir() -> str:
    """
    Pick a writable tmp dir (in order):
      1) $TMPDIR (Termux sets to .../usr/tmp)
      2) ~/bot-a/tmp
    """
    candidates = []
    env_tmp = os.environ.get("TMPDIR")
    if env_tmp:
        candidates.append(env_tmp)
    candidates.append(os.path.join(BASE_DIR, "tmp"))
    for c in candidates:
        try:
            os.makedirs(c, exist_ok=True)
            test = os.path.join(c, ".writetest")
            with open(test, "w") as f:
                f.write("ok")
            os.remove(test)
            return c
        except Exception:
            continue
    # last resort: inside BASE_DIR
    fback = os.path.join(BASE_DIR, "tmp")
    os.makedirs(fback, exist_ok=True)
    return fback

TMP_DIR = _choose_tmp_dir()

def ensure_dir(path: str, exist_ok: bool = True) -> None:
    if path:
        os.makedirs(path, exist_ok=exist_ok)

# ensure base structure always exists
for _d in (BASE_DIR, DATA_DIR, LOGS_DIR, TMP_DIR):
    try:
        ensure_dir(_d, exist_ok=True)
    except Exception:
        pass

def secure_files(paths: Iterable[str], mode: int = 0o600) -> None:
    for p in paths:
        try:
            os.chmod(p, mode)
        except Exception:
            pass

def lock_path(name: str) -> str:
    """Return absolute lockfile path inside TMP_DIR."""
    ensure_dir(TMP_DIR, exist_ok=True)
    return os.path.join(TMP_DIR, name)

# ========= Time helpers =========
def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)

def utcstr(ts: Optional[dt.datetime] = None) -> str:
    """UTC timestamp as string (human)."""
    if ts is None: ts = utcnow()
    return ts.astimezone(dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

def utcdate(ts: Optional[dt.datetime] = None) -> str:
    """UTC date string (YYYY-MM-DD)."""
    if ts is None: ts = utcnow()
    return ts.astimezone(dt.timezone.utc).strftime("%Y-%m-%d")

def is_fx_closed_now(now: Optional[dt.datetime] = None) -> bool:
    """Close window (Sun 21:00z–Fri 21:00z open)."""
    if now is None:
        now = utcnow()
    now = now.astimezone(dt.timezone.utc)
    wd = now.weekday()                      # Mon=0 ... Sun=6
    hm = now.hour + now.minute/60.0
    if wd == 4 and hm >= 21.0:  # Fri after 21z
        return True
    if wd == 5:                 # Saturday
        return True
    if wd == 6 and hm < 21.0:   # Sunday before 21z
        return True
    return False

def hours_to_next_fx_open(now: Optional[dt.datetime] = None) -> float:
    """Hours until next Sun 21:00 UTC from 'now'."""
    if now is None: now = utcnow()
    now = now.astimezone(dt.timezone.utc)
    if not is_fx_closed_now(now):
        return 0.0
    days_ahead = (6 - now.weekday()) % 7
    next_sun = (now + dt.timedelta(days=days_ahead)).replace(
        hour=21, minute=0, second=0, microsecond=0
    )
    if next_sun <= now:
        next_sun += dt.timedelta(days=7)
    return round((next_sun - now).total_seconds()/3600.0, 2)

# ========= JSON helpers =========
def read_json(path: str, default: Any = None) -> Any:
    try:
        with io.open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default
    except Exception:
        return default

def write_json(path: str, obj: Any) -> None:
    ensure_dir(os.path.dirname(path), exist_ok=True)
    with io.open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

def write_json_atomic(path: str, obj: Any) -> None:
    ensure_dir(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.tmp.{int(time.time()*1000)}"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.flush(); os.fsync(f.fileno())
    os.replace(tmp, path)

# ========= CSV / hash helpers =========
def rotate_csv_daily(csv_path: str, current_date: dt.date) -> None:
    try:
        st = os.stat(csv_path)
    except FileNotFoundError:
        return
    file_date = dt.datetime.fromtimestamp(st.st_mtime, tz=dt.timezone.utc).date()
    if file_date != current_date:
        base, ext = os.path.splitext(csv_path)
        dst = f"{base}.{file_date.isoformat()}{ext}"
        try:
            os.replace(csv_path, dst)
        except Exception:
            pass

def digest_checksum(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:10]

def hash_signal(symbol: str, side: str, score: Any, sent_ok: bool = True, extra: str = "") -> str:
    raw = f"{symbol}|{side}|{score}|{int(sent_ok)}|{extra}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()[:8]

# ========= Locking / single-instance =========
@contextlib.contextmanager
def file_lock(name_or_path: str, timeout_sec: float = 1.0):
    """
    Very small cross-process lock using O_EXCL. Stores lock file under TMP_DIR
    unless an absolute path is passed.
    """
    if os.path.isabs(name_or_path):
        lf = name_or_path
        ensure_dir(os.path.dirname(lf), exist_ok=True)
    else:
        lf = lock_path(name_or_path)
    start = time.time()
    fd = None
    try:
        while True:
            try:
                fd = os.open(lf, os.O_CREAT | os.O_EXCL | os.O_RDWR)
                os.write(fd, str(os.getpid()).encode("utf-8"))
                break
            except FileExistsError:
                if time.time() - start >= timeout_sec:
                    raise TimeoutError(f"lock busy: {lf}")
                time.sleep(0.05)
        yield
    finally:
        try:
            if fd is not None: os.close(fd)
            if os.path.exists(lf): os.unlink(lf)
        except Exception:
            pass

@contextlib.contextmanager
def single_instance(instance_name: str = "runner"):
    """Ensure only one instance by pid lock under TMP_DIR."""
    with file_lock(f"{instance_name}.pid.lock", timeout_sec=0.5):
        yield

# ========= Tiny logging / alert =========
def _log_path(name: str) -> str:
    ensure_dir(LOGS_DIR, exist_ok=True)
    return os.path.join(LOGS_DIR, name)

def append_text(path: str, content: str) -> None:
    ensure_dir(os.path.dirname(path), exist_ok=True)
    with io.open(path, "a", encoding="utf-8") as f:
        f.write(content)

def alert(msg: str, level: str = "INFO") -> None:
    """
    Minimal alert logger used by scripts that 'from lib_utils import alert'.
    Writes to logs/alerts.log and prints to stdout (so you see it in Termux).
    """
    line = f"[{level}] {utcstr()} {msg}\n"
    try:
        append_text(_log_path("alerts.log"), line)
    finally:
        try:
            print(line, end="")
        except Exception:
            pass

# ========= Convenience =========
def read_text(path: str, default: str = "") -> str:
    try:
        with io.open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return default

def write_text(path: str, content: str) -> None:
    ensure_dir(os.path.dirname(path), exist_ok=True)
    with io.open(path, "w", encoding="utf-8") as f:
        f.write(content); f.flush(); os.fsync(f.fileno())
