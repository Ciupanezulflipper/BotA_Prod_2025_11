#!/usr/bin/env python3
import os, json, sys
from pathlib import Path
HOME = Path(os.path.expanduser("~"))
CACHE = HOME/"BotA"/"cache"
for p in sorted(CACHE.glob("*.json")):
    try:
        with p.open() as f:
            d=json.load(f)
        print(f"{p.name}: ts={d.get('timestamp')} vote={d.get('vote')} close={d.get('close')}")
    except Exception as e:
        print(f"{p.name}: error {e}")
