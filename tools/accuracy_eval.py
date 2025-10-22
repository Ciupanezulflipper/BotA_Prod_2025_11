#!/usr/bin/env python3
import csv, time, math
from pathlib import Path

BASE = Path.home() / "bot-a"
CSV  = BASE / "data" / "signal_journal.csv"
OUT  = BASE / "data" / "accuracy_daily.json"

# Tunables
HORIZON_MIN = 240   # 4h look-ahead
TAKE_PIPS   = 15    # success threshold
MAX_ROWS    = 5000  # cap work

def pip_move_ok(pair, entry, future):
  # Very rough pip calculation (EURUSD etc. 1 pip = 0.0001)
  scale = 10000.0 if "JPY" not in pair else 100.0
  return abs((future - entry) * scale) >= TAKE_PIPS

def mock_future_price(entry):  # placeholder if you don’t have stored candles here
  # This keeps script safe if candles are missing.
  return entry  # neutral; will not count as win

def evaluate():
  if not CSV.exists():
    return dict(analyzed=0, wins=0, winrate=0.0)
  now = int(time.time())
  horizon = now + HORIZON_MIN*60
  rows = []
  with CSV.open() as f:
    r = csv.DictReader(f)
    for row in r:
      if row["event"] != "SEND": continue
      rows.append(row)
      if len(rows) >= MAX_ROWS: break
  analyzed = wins = 0
  for row in rows:
    pair = row["pair"]
    try:
      entry = float(row["score"]) * 0.0001 + 1.0  # stand-in if you don’t log price; replace later
    except:
      entry = 1.0
    future = mock_future_price(entry)
    ok = pip_move_ok(pair, entry, future)
    analyzed += 1
    wins += 1 if ok else 0
  winrate = (wins / analyzed * 100.0) if analyzed else 0.0
  return dict(analyzed=analyzed, wins=wins, winrate=round(winrate,2),
              horizon_min=HORIZON_MIN, take_pips=TAKE_PIPS)

def main():
  res = evaluate()
  OUT.write_text(str(res))
  print(res)

if __name__ == "__main__":
  main()
