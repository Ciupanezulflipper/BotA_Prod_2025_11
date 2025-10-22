from __future__ import annotations
import os, pathlib, time, json, hashlib

# --- Load .env (simple, no external deps) ---
REPO = pathlib.Path(__file__).resolve().parents[1]
ENV_FILE = REPO / ".env"

def _parse_env_line(line: str):
    if not line or line.startswith("#") or "=" not in line:
        return None
    k, v = line.split("=", 1)
    return k.strip(), v.strip()

def _load_env_file():
    env = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            kv = _parse_env_line(line)
            if kv:
                k, v = kv
                env[k] = v
    return env

# Precedence: OS env > .env file
ENV = _load_env_file()
ENV.update({k: v for k, v in os.environ.items() if k})

def env_get(key: str, default: str | None = None) -> str | None:
    return ENV.get(key, default)

def env_bool(key: str, default: bool = False) -> bool:
    v = ENV.get(key)
    if v is None: return default
    return str(v).strip().lower() in {"1","true","yes","on"}

def env_int(key: str, default: int = 0) -> int:
    v = ENV.get(key)
    try:
        return int(v) if v is not None else default
    except Exception:
        return default

# basic cache dir for throttling/dedupe
VAR_DIR = REPO / "var"
VAR_DIR.mkdir(exist_ok=True)

def cache_path(name: str) -> pathlib.Path:
    safe = hashlib.sha256(name.encode()).hexdigest()[:16]
    return VAR_DIR / f"{safe}.json"

def cache_get(name: str, default=None):
    p = cache_path(name)
    if not p.exists(): return default
    try:
        return json.loads(p.read_text())
    except Exception:
        return default

def cache_put(name: str, obj) -> None:
    cache_path(name).write_text(json.dumps(obj), encoding="utf-8")

def now_ts() -> int:
    return int(time.time())
