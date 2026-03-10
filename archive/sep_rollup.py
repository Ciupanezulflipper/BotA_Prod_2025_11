import csv, os, sys, datetime as dt
TZ = dt.timezone.utc
today = dt.datetime.now(TZ).date()
p = os.path.expanduser('~/BotA/trades.csv')
if not os.path.exists(p):
    print("No trades.csv yet"); sys.exit(0)

rows=[]
with open(p) as f:
    for r in csv.reader(f):
        if len(r)>=8:
            ts = r[0]
            try:
                d = dt.datetime.fromisoformat(ts.replace('Z','+00:00')).date()
            except Exception:
                continue
            if d==today:
                rows.append(r)

out = []
for r in rows:
    ts,pair,side,entry,tp,sl,atr,weighted = r[:8]
    out.append(f"{ts} {pair} {side} E={entry} TP={tp} SL={sl} ATR={atr} W={weighted}")

summary = f"""[SEP ROLLUP] {today.isoformat()}
count={len(out)}
""" + "\n".join(out[-10:])  # show last 10 of today

os.makedirs(os.path.expanduser('~/BotA/logs'), exist_ok=True)
with open(os.path.expanduser('~/BotA/logs/sep_daily.txt'),'a') as f:
    f.write(summary+"\n\n")

print(summary)

# Optional Telegram push if SEND_ROLLUP=1 and token/chat set
if os.getenv("SEND_ROLLUP")=="1":
    tok = os.getenv("TELEGRAM_TOKEN")
    chat = os.getenv("TELEGRAM_CHAT_ID")
    if tok and chat:
        import requests
        requests.post(f"https://api.telegram.org/bot{tok}/sendMessage",
                      json={"chat_id":chat,"text":summary})
