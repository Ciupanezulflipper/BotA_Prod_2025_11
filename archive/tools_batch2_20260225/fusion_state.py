#!/usr/bin/env python3
import json, os, time, hashlib
from dataclasses import dataclass

STATE_PATH = os.path.expanduser("~/.bot-a/fusion_state.json")
os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)

def _now_ts() -> int:
    return int(time.time())

def _load() -> dict:
    if not os.path.exists(STATE_PATH):
        return {"by_symbol": {}}
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"by_symbol": {}}

def _save(data: dict) -> None:
    tmp = STATE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, STATE_PATH)

@dataclass
class DecisionGate:
    cooldown_min: int = 45    # suppress repeats inside this window
    max_age_min: int = 240    # forget old signals after this

    def signature(self, symbol: str, decision: str, tech_bucket: str, news_bucket: str) -> str:
        raw = f"{symbol}|{decision}|{tech_bucket}|{news_bucket}"
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()

    def should_send(self, symbol: str, sig_hex: str) -> bool:
        st = _load()
        by_sym = st.get("by_symbol", {})
        now = _now_ts()
        entry = by_sym.get(symbol)

        if not entry:
            by_sym[symbol] = {"ts": now, "sig": sig_hex}
            st["by_symbol"] = by_sym
            _save(st)
            return True

        # forget too-old entries
        if now - entry.get("ts", 0) > self.max_age_min * 60:
            by_sym[symbol] = {"ts": now, "sig": sig_hex}
            st["by_symbol"] = by_sym
            _save(st)
            return True

        # identical signature inside cooldown → skip
        if entry.get("sig") == sig_hex and (now - entry.get("ts", 0)) < self.cooldown_min * 60:
            return False

        # new signature or cooldown expired → allow and update
        by_sym[symbol] = {"ts": now, "sig": sig_hex}
        st["by_symbol"] = by_sym
        _save(st)
        return True
