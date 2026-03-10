import os, requests, textwrap

tok = os.environ["TELEGRAM_BOT_TOKEN"]
cid = os.environ["TELEGRAM_CHAT_ID"]
api = f"https://api.telegram.org/bot{tok}/sendMessage"

def send(text):
    r = requests.post(api, json={"chat_id": cid, "text": text, "disable_web_page_preview": True})
    print("HTTP", r.status_code, r.text[:160])

# Weak (should be BLOCK if hook is active & thresholds strict)
weak = textwrap.dedent("""\
    [SEP TEST]  🧪 Weak example (expect BLOCK)
    === EURUSD snapshot ===
    H1: … RSI14=49.9 … vote=0
    H4: … RSI14=47.2 … vote=-1
    D1: … RSI14=51.0 … vote=0

    Signal: SELL
    Entry: 1.23456
    SL: 1.24176
    TP: 1.22256
    ATR: 0.0060
    RR: 1:1.67
    Votes: {'H1': 0, 'H4': -1, 'D1': 0}
""")

# Strong (should be ALLOW)
strong = textwrap.dedent("""\
    [SEP TEST]  ✅ Strong example (expect ALLOW)
    === GBPUSD snapshot ===
    H1: … RSI14=38.2 … vote=-1
    H4: … RSI14=41.0 … vote=-1
    D1: … RSI14=40.4 … vote=-1

    Signal: SELL
    Entry: 1.33333
    SL: 1.34151
    TP: 1.32133
    ATR: 0.0061
    RR: 1:1.67
    Votes: {'H1': -1, 'H4': -1, 'D1': -1}
""")

print("=== Weak probe (expect BLOCK) ===")
send(weak)
print("=== Strong probe (expect ALLOW) ===")
send(strong)
