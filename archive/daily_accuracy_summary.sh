#!/usr/bin/env bash
set -euo pipefail
ROOT="${BOTA_ROOT:-$HOME/BotA}"
LOGDIR="$ROOT/logs"
CFG="$ROOT/config/signal.env"
CSV="$LOGDIR/accuracy.csv"
mkdir -p "$LOGDIR"

# --- load env from config + .env (without exporting globally)
kv() { awk -F= -v k="$1" 'tolower($1)==tolower(k){print $2}' "$2" 2>/dev/null | tail -n1; }

TG_TOKEN="$(kv TELEGRAM_BOT_TOKEN "$CFG")"
[ -z "$TG_TOKEN" ] && TG_TOKEN="$(kv TELEGRAM_BOT_TOKEN "$ROOT/.env")"
TG_CHAT="$(kv TELEGRAM_CHAT_ID "$CFG")"
[ -z "$TG_CHAT" ] && TG_CHAT="$(kv TELEGRAM_CHAT_ID "$ROOT/.env")"

ts(){ date -u +'%Y-%m-%d %H:%M:%S UTC'; }

if [ ! -s "$CSV" ]; then
  echo "[$(ts)] ⚠️ daily_summary: accuracy.csv missing/empty — nothing to summarize."
  exit 0
fi

# --- compute in Python (robust date math + CSV)
OUT_JSON="$(python3 - <<'PY'
import csv, sys, json
from datetime import datetime, timedelta, timezone
import os

ROOT = os.path.expanduser(os.environ.get("BOTA_ROOT","~/BotA"))
CSV  = os.path.join(ROOT,"logs","accuracy.csv")

def parse_ts(s):
    s = s.strip().replace(" UTC","")
    return datetime.strptime(s, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)

now = datetime.now(timezone.utc)
cut = now - timedelta(days=1)

hit=miss=neu=0
pending_stale=pending_dispute=0
n=0
abs_pips=[]
src_counts={"local":0,"yahoo":0,"stooq":0,"finnhub":0,"STALE":0,"":0}

with open(CSV,"r",encoding="utf-8") as f:
    r=csv.reader(f)
    hdr=next(r,None)
    # columns (by signal_accuracy.py):
    # 0 alert_ts_utc,1 pair,2 dir,3 window_min,4 entry,5 result,
    # 6 pips,7 truth_source,8 truth_price,9 truth_delta_pips,10 truth_age_sec,11 evaluated_at
    for row in r:
        try:
            eval_ts = parse_ts(row[11])
        except Exception:
            continue
        if eval_ts < cut: 
            continue
        res = (row[5] or "").strip().upper()
        n+=1
        if res=="HIT": hit+=1
        elif res=="MISS": miss+=1
        elif res=="NEUTRAL": neu+=1
        elif res.startswith("PENDING:STALE"): pending_stale+=1
        elif res.startswith("PENDING:DISPUTE"): pending_dispute+=1
        try:
            abs_pips.append(abs(float(row[6])))
        except Exception:
            pass
        src = (row[7] or "").lower()
        src_counts[src] = src_counts.get(src,0)+1

hitmiss = hit+miss
hit_rate = (hit/ hitmiss *100.0) if hitmiss>0 else 0.0
avg_abs = (sum(abs_pips)/len(abs_pips)) if abs_pips else 0.0

out = {
    "checked": n,
    "hit": hit, "miss": miss, "neutral": neu,
    "hit_rate": round(hit_rate,1),
    "avg_abs_pips": round(avg_abs,1),
    "pending_stale": pending_stale, "pending_dispute": pending_dispute,
    "truth_src": src_counts
}
print(json.dumps(out))
PY
)"
# shell parse fields
checked="$(echo "$OUT_JSON" | awk -F'"checked":' '{print $2}' | awk -F',' '{print $1}' )"
hit="$(echo "$OUT_JSON" | awk -F'"hit":' '{print $2}' | awk -F',' '{print $1}' )"
miss="$(echo "$OUT_JSON" | awk -F'"miss":' '{print $2}' | awk -F',' '{print $1}' )"
neu="$(echo "$OUT_JSON" | awk -F'"neutral":' '{print $2}' | awk -F',' '{print $1}' )"
rate="$(echo "$OUT_JSON" | awk -F'"hit_rate":' '{print $2}' | awk -F',' '{print $1}' )"
avgp="$(echo "$OUT_JSON" | awk -F'"avg_abs_pips":' '{print $2}' | awk -F',' '{print $1}' )"

# truth breakdowns (safe defaults)
get_src(){ echo "$OUT_JSON" | sed 's/[{}]//g' | tr ',' '\n' | grep -i "\"$1\"" | awk -F: '{print $NF}' | tr -d ' '; }
src_local="$(get_src local)"; [ -z "$src_local" ] && src_local=0
src_yahoo="$(get_src yahoo)"; [ -z "$src_yahoo" ] && src_yahoo=0
src_stooq="$(get_src stooq)"; [ -z "$src_stooq" ] && src_stooq=0
src_finnhub="$(get_src finnhub)"; [ -z "$src_finnhub" ] && src_finnhub=0
p_stale="$(echo "$OUT_JSON" | awk -F'"pending_stale":' '{print $2}' | awk -F',' '{print $1}' )"
p_disp="$(echo "$OUT_JSON" | awk -F'"pending_dispute":' '{print $2}' | awk -F',' '{print $1}' )"

SUMMARY="📊 Accuracy 24h — checked: ${checked} | HIT: ${hit} | MISS: ${miss} | ⚪ NEU: ${neu}
✅ Hit%%: ${rate} | avg |pips|: ${avgp}
🧭 Truth src -> local:${src_local} / yahoo:${src_yahoo} / stooq:${src_stooq} / finnhub:${src_finnhub}
⏳ Pending: STALE=${p_stale} / DISPUTE=${p_disp}
"

echo "[$(ts)] SUMMARY
$SUMMARY" | tee -a "$LOGDIR/daily_summary.log"

# Telegram send (plain)
if [ -n "${TG_TOKEN}" ] && [ -n "${TG_CHAT}" ]; then
  curl -sS -X POST "https://api.telegram.org/bot${TG_TOKEN}/sendMessage" \
    -d "chat_id=${TG_CHAT}" \
    --data-urlencode "text=$SUMMARY" >/dev/null || true
fi
