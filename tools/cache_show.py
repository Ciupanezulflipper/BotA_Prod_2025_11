#!/usr/bin/env python3
import os, json, sys
from pathlib import Path
HOME = Path(os.path.expanduser("~"))
CACHE = HOME/"BotA"/"cache"
for p in sorted(CACHE.glob("*.json")):
    try:
        with p.open() as f:
            d=json.load(f)
        print(f"{p.name}: price={d.get('price')} adx={d.get('adx')} rsi={d.get('rsi')} age_min={d.get('age_min')} pair={d.get('pair')} tf={d.get('timeframe')}")
    except Exception as e:
        print(f"{p.name}: error {e}")
