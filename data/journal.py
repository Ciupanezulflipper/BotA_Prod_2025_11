import os, csv, json, datetime as dt
from typing import Dict, Any

def _logdir() -> str:
    d = os.getenv("JOURNAL_DIR", os.path.expanduser("~/bot-a/logs"))
    os.makedirs(d, exist_ok=True)
    return d

def _today_name() -> str:
    return dt.datetime.utcnow().strftime("%Y%m%d")

def _csv_path() -> str:
    return os.path.join(_logdir(), f"signals-{_today_name()}.csv")

def _jsonl_path() -> str:
    return os.path.join(_logdir(), f"signals-{_today_name()}.jsonl")

CSV_HEADERS = [
    "run_id","time_utc","symbol","tf","type","score","bias","note",
    "posted","why","cadence_min","watchlist","engine","entry","stop","target","rr"
]

def append_csv(run_id: str, row: Dict[str, Any]) -> None:
    path = _csv_path()
    exists = os.path.exists(path)
    with open(path, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        if not exists:
            w.writeheader()
        w.writerow({
            "run_id": run_id,
            "time_utc": row.get("time_utc"),
            "symbol": row.get("symbol"),
            "tf": row.get("tf"),
            "type": row.get("type"),
            "score": row.get("score"),
            "bias": row.get("bias"),
            "note": row.get("note",""),
            "posted": row.get("posted",0),
            "why": row.get("why",""),
            "cadence_min": row.get("cadence_min"),
            "watchlist": row.get("watchlist"),
            "engine": row.get("engine","v2b"),
            "entry": row.get("entry"),
            "stop": row.get("stop"),
            "target": row.get("target"),
            "rr": row.get("rr"),
        })

def append_jsonl(row: Dict[str, Any]) -> None:
    path = _jsonl_path()
    with open(path, "a") as f:
        f.write(json.dumps(row, separators=(",",":")) + "\n")

def heartbeat(run_id: str, symbols: str, tf: str, cadence_min: int, engine: str):
    nowz = dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    row = dict(
        time_utc=nowz, symbol=symbols, tf=tf, type="heartbeat",
        score="", bias="", note="alive", posted="", why="",
        cadence_min=cadence_min, watchlist=symbols, engine=engine,
        entry="", stop="", target="", rr=""
    )
    append_csv(run_id, row); append_jsonl(dict(run_id=run_id, **row))
