import subprocess, json, datetime, os, pathlib
ROOT = pathlib.Path(__file__).parent.parent

def run(pair):
    r = subprocess.run(['python3', str(ROOT / 'tools' / 'emit_snapshot.py'), pair],
        capture_output=True, text=True)
    return r.stdout

def parse(raw):
    tfs = {}
    for line in raw.splitlines():
        if not line.startswith(('H1:','H4:','D1:')):
            continue
        parts = line.split()
        tf = parts[0].rstrip(':')
        d = {}
        for p in parts[1:]:
            if '=' in p:
                k,v = p.split('=',1)
                d[k] = v
        tfs[tf] = d
    return tfs

def vote_bar(v):
    try: v = int(v)
    except: return '⚪'
    if v >= 2: return '🟢'
    if v == 1: return '🟡'
    if v == -1: return '🟠'
    if v <= -2: return '🔴'
    return '⚪'

def macd_arrow(v):
    try: return '↗️' if float(v) >= 0 else '↘️'
    except: return '➡️'

def total_vote(tfs):
    try: return sum(int(tfs[t]['vote']) for t in ['H1','H4','D1'] if t in tfs)
    except: return 0

def bias(tv):
    if tv >= 5: return '🟢 STRONG BULL'
    if tv >= 2: return '🟢 BULL'
    if tv <= -5: return '🔴 STRONG BEAR'
    if tv <= -2: return '🔴 BEAR'
    return '⚪ NEUTRAL'

now = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
lines = [f'🕘 BotA Status — {now}', '']

for pair, label in [('EURUSD','EUR/USD'), ('GBPUSD','GBP/USD')]:
    raw = run(pair)
    tfs = parse(raw)
    if not tfs:
        lines.append(f'⚠️ {label} — no data')
        continue
    close = tfs.get('H1',{}).get('close','?')
    tv = total_vote(tfs)
    lines.append(f'━━━ {label} ━━━')
    lines.append(f'💰 {close}')
    for tf in ['H1','H4','D1']:
        if tf not in tfs: continue
        d = tfs[tf]
        rsi = float(d.get('rsi','rsi14'.split('=')[-1]) if 'rsi' in d else d.get('RSI14',0))
        # parse RSI14 key
        rsi_val = '?'
        for k,v in d.items():
            if 'rsi' in k.lower():
                try: rsi_val = f'{float(v):.1f}'
                except: pass
        vote = d.get('vote','0')
        macd = d.get('macd_hist') or d.get('MACD_hist','0')
        lines.append(f'📊 {tf}  RSI {rsi_val} | MACD {macd_arrow(macd)} | Vote {vote} {vote_bar(vote)}')
    lines.append(f'🧭 Bias: {bias(tv)} ({tv:+d}/9)')
    lines.append('')

print('\n'.join(lines))

# Append API usage line
import subprocess as _sp
_api = _sp.run(['python3', str(ROOT / 'tools' / 'api_credit_tracker.py'), 'status'],
    capture_output=True, text=True)
if _api.stdout.strip():
    print(_api.stdout.strip())
