import csv, os, sys
p = os.path.expanduser("~/BotA/logs/trades.csv")
if not os.path.exists(p):
    print("No trades.csv yet")
    sys.exit(0)
with open(p, newline="", encoding="utf-8") as f:
    for row in csv.reader(f):
        print(",".join(row))
