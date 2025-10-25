#!/usr/bin/env python3
from __future__ import annotations
import os, sys, json, time
from typing import Dict, List

STATE_PATH = os.getenv("ALERT_STATE_PATH", os.path.expanduser("~/BotA/state/alert_state.json"))
COOL_MIN = int(os.getenv("COOL_DOWN_MIN", "30"))
UPDATE = os.getenv("UPDATE_STATE", "0") in ("1","true","TRUE","yes","YES")

def load_state() -> Dict:
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_state(st: Dict) -> None:
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    tmp = STATE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(st, f)
    os.replace(tmp, STATE_PATH)

def main() -> int:
    now = int(time.time())
    st = load_state()
    raw = sys.stdin.read()
    try:
        arr = json.loads(raw) if raw.strip() else []
    except Exception:
        arr = []
    out: List[Dict] = []
    for it in arr:
        pair = it.get("pair","")
        weighted = int(it.get("weighted", 0))
        last = st.get(pair, {})
        last_ts = int(last.get("ts", 0))
        last_w = int(last.get("weighted", 0))
        cooldown_ok = (now - last_ts) >= COOL_MIN * 60
        stronger = abs(weighted) > abs(last_w)
        if cooldown_ok or stronger:
            out.append(it)
            if UPDATE:
                st[pair] = {"ts": now, "weighted": weighted}
    if UPDATE:
        save_state(st)
    print(json.dumps(out, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    sys.exit(main())
