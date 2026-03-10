import json, os
from datetime import datetime, timedelta

def _iter_jsonl(path):
    if not os.path.exists(path): return
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line=line.strip()
            if not line: continue
            try: yield json.loads(line)
            except: continue

def should_allow_send(jsonl_path="signals.jsonl", max_losses=3, lookback_hours=24):
    """Return True if it's OK to send (i.e., not too many recent losses)."""
    cutoff = datetime.utcnow() - timedelta(hours=lookback_hours)
    losses = 0
    for obj in _iter_jsonl(jsonl_path):
        ts = obj.get("timestamp")
        outcome = obj.get("outcome")
        try:
            when = datetime.fromisoformat(ts.replace("Z",""))
        except:
            continue
        if when >= cutoff and outcome == "loss":
            losses += 1
    return losses < max_losses
