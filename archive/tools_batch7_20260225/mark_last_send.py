#!/usr/bin/env python3
import sys, os, time, json
pair = sys.argv[1] if len(sys.argv)>1 else "EURUSD"
tf   = sys.argv[2] if len(sys.argv)>2 else "M15"
path = os.path.expanduser(f"~/bot-a/data/last_send_{pair}_{tf}.ts")
os.makedirs(os.path.dirname(path), exist_ok=True)
with open(path,"w") as f:
    f.write(str(time.time()))
print(f"marked last send for {pair} {tf} at {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}")
