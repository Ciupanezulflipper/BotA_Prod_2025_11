#!/data/data/com.termux/files/usr/bin/bash
# FILE: tools/hourly_dashboard.sh
# PURPOSE: Summarize last 60m alerts into logs/dashboard_hourly.txt and (optionally) push to Telegram.
# NOTES:
#  - Outputs percentages with a SINGLE '%' character (fix for '%%').
#  - Safe when there are zero alerts (no division-by-zero).
#  - Works on Termux (Android) with coreutils 'date' and 'awk'.

set -euo pipefail

# ── Pathing ─────────────────────────────────────────────────────────────────────
if [[ -n "${BASH_SOURCE[0]:-}" ]]; then
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
else
  SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
fi
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

# ── Config ─────────────────────────────────────────────────────────────────────
set -a
source config/strategy.env
set +a

[[ -z "${ALERTS_CSV:-}" ]] && { echo "ERROR: ALERTS_CSV not set in config/strategy.env" >&2; exit 1; }

OUT="logs/dashboard_hourly.txt"
mkdir -p logs

# ── Collect last 60 minutes of alerts ──────────────────────────────────────────
now=$(date -u +%s)
cutoff=$((now - 3600))
tmp="$(mktemp)"
# Expect CSV header: timestamp,pair,timeframe,verdict,score,confidence,breakdown,price,provider
# Example timestamp: 2025-10-30T15:48:22+00:00
tail -n 5000 "$ALERTS_CSV" | awk -F, -v cut="$cutoff" '
  NR==1 { next }
  {
    ts=$1
    gsub(/Z/,"",ts)
    cmd="date -u -d \"" ts "\" +%s"
    cmd | getline epoch
    close(cmd)
    if (epoch >= cut) print $0
  }
' > "$tmp" || true

# ── Basic counts ───────────────────────────────────────────────────────────────
total=$(wc -l < "$tmp" | tr -d ' ' || echo "0")
buys=$(grep -c ",BUY," "$tmp" 2>/dev/null || true)
sells=$(grep -c ",SELL," "$tmp" 2>/dev/null || true)
holds=$(grep -c ",HOLD," "$tmp" 2>/dev/null || true)

# ── Percentages (as numeric strings WITHOUT '%' sign) ──────────────────────────
if [[ "${total:-0}" -gt 0 ]]; then
  buy_pct=$(awk -v b="$buys"  -v t="$total" 'BEGIN{printf "%.1f", (b/t)*100}')
  sell_pct=$(awk -v s="$sells" -v t="$total" 'BEGIN{printf "%.1f", (s/t)*100}')
  hold_pct=$(awk -v h="$holds" -v t="$total" 'BEGIN{printf "%.1f", (h/t)*100}')
else
  buy_pct="0.0"; sell_pct="0.0"; hold_pct="0.0"
fi

# ── Top pairs by alert frequency ───────────────────────────────────────────────
# Output like: "EURUSD:33 GBPUSD:30 ..."
top="$(awk -F, '{cnt[$2]++} END{for (s in cnt) printf "%s:%d\n", s, cnt[s]}' "$tmp" \
  | sort -t: -k2,2nr | head -5 | tr '\n' ' ' 2>/dev/null)"
[[ -z "$top" ]] && top="none"

# ── Generate line & write to file ──────────────────────────────────────────────
line="[$(date -Iseconds)] last hour: total=${total} BUY=${buys} (${buy_pct}%) SELL=${sells} (${sell_pct}%) HOLD=${holds} (${hold_pct}%) | Top pairs: ${top}"
echo "$line" | tee -a "$OUT"

# ── Optional Telegram push (TEXT MODE) ─────────────────────────────────────────
if [[ "${TELEGRAM_DASHBOARD:-0}" == "1" && "${TELEGRAM_ENABLED:-0}" == "1" ]]; then
  # Require both token and chat id
  if [[ -n "${TELEGRAM_TOKEN:-}" && -n "${TELEGRAM_CHAT_ID:-}" ]]; then
    msg="📊 *BotA - Hourly Summary*%0Alast60m: *${total}* alerts%0A• BUY ${buys} (${buy_pct}%25)%0A• SELL ${sells} (${sell_pct}%25)%0A• HOLD ${holds} (${hold_pct}%25)%0ATop: ${top}"
    # Note: '%25' is the URL-encoded literal '%' so Telegram receives a SINGLE '%' in the message.
    curl -sS -X POST "https://api.telegram.org/bot${TELEGRAM_TOKEN}/sendMessage" \
      -d "chat_id=${TELEGRAM_CHAT_ID}" \
      -d "text=${msg}" \
      -d "parse_mode=Markdown" >/dev/null 2>&1 || true
  fi
fi

# ── Cleanup ────────────────────────────────────────────────────────────────────
rm -f "$tmp"
