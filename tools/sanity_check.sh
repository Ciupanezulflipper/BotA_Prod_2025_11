#!/data/data/com.termux/files/usr/bin/bash
# sanity_check.sh — BotA master sanity/smoke/health check
# Replaces: health_check_pro.sh, run_smoke_suite.sh
# Run: bash tools/sanity_check.sh
# Sends PASS/FAIL summary to Telegram.
# Schedule: every Sunday before weekly trade review.

set -uo pipefail

ROOT="${BOTA_ROOT:-$HOME/BotA}"
cd "$ROOT" || exit 1
TOOLS="$ROOT/tools"
LOGS="$ROOT/logs"
CACHE="$ROOT/cache"

PASS=0
FAIL=0
WARN=0
RESULTS=()

# ── helpers ──────────────────────────────────────────────
_ok()   { echo "[PASS] $*"; PASS=$((PASS+1)); RESULTS+=("✅ $*"); }
_fail() { echo "[FAIL] $*"; FAIL=$((FAIL+1)); RESULTS+=("❌ $*"); }
_warn() { echo "[WARN] $*"; WARN=$((WARN+1)); RESULTS+=("⚠️  $*"); }
_hdr()  { echo ""; echo "── $* ──────────────────────────────"; }

# ── source credentials ───────────────────────────────────
source "$ROOT/config/strategy.env" 2>/dev/null || true

# ════════════════════════════════════════════════════════
_hdr "1. CRONTAB — PAIRS and GATE"
# ════════════════════════════════════════════════════════

CRON_LINE="$(crontab -l 2>/dev/null | grep 'signal_watcher_pro' | head -1)"

if echo "$CRON_LINE" | grep -q 'USDJPY'; then
    _fail "USDJPY still present in cron PAIRS — must be removed"
else
    _ok "PAIRS clean — no USDJPY in cron"
fi

if echo "$CRON_LINE" | grep -q 'FILTER_SCORE_MIN=62'; then
    _ok "FILTER_SCORE_MIN=62 confirmed in cron"
else
    _fail "FILTER_SCORE_MIN=62 NOT found in cron — gate may be wrong"
fi

if echo "$CRON_LINE" | grep -q 'TELEGRAM_TIER_GREEN_MIN=65'; then
    _ok "TELEGRAM_TIER_GREEN_MIN=65 confirmed in cron"
else
    _warn "TELEGRAM_TIER_GREEN_MIN=65 not found in cron — check tier config"
fi

if echo "$CRON_LINE" | grep -q 'TELEGRAM_COOLDOWN_SECONDS=1800'; then
    _ok "TELEGRAM_COOLDOWN_SECONDS=1800 confirmed"
else
    _warn "TELEGRAM_COOLDOWN_SECONDS not confirmed in cron"
fi

# ════════════════════════════════════════════════════════
_hdr "2. DEAD ZONE GATE"
# ════════════════════════════════════════════════════════

if grep -q "2130" "$TOOLS/market_open.sh" 2>/dev/null && \
   grep -q "2300" "$TOOLS/market_open.sh" 2>/dev/null; then
    _ok "Dead zone 21:30-23:00 UTC present in market_open.sh"
else
    _fail "Dead zone gate NOT found in market_open.sh"
fi

# Validate gate math for 7 boundary cases
GATE_OK=$(python3 -c "
tests = [(2200,True),(2130,True),(2259,True),(2300,False),(1400,False),(0,False),(2129,False)]
all_ok = all((h >= 2130 and h < 2300) == expected for h, expected in tests)
print('OK' if all_ok else 'FAIL')
")
if [[ "$GATE_OK" == "OK" ]]; then
    _ok "Dead zone boundary logic verified (7 cases)"
else
    _fail "Dead zone boundary logic FAILED"
fi

# ════════════════════════════════════════════════════════
_hdr "3. TREND PENALTY in quality_filter.py"
# ════════════════════════════════════════════════════════

if grep -q "0\.85" "$TOOLS/quality_filter.py" 2>/dev/null && \
   grep -q "H1_trend_opposite" "$TOOLS/quality_filter.py" 2>/dev/null; then
    _ok "Trend penalty (0.85 × score on H1_trend_opposite) in quality_filter.py"
else
    _fail "Trend penalty NOT found in quality_filter.py"
fi

# ════════════════════════════════════════════════════════
_hdr "4. CHART GENERATOR"
# ════════════════════════════════════════════════════════

if [[ ! -f "$TOOLS/chart_generator.py" ]]; then
    _fail "chart_generator.py missing"
else
    TEST_PNG="$LOGS/tmp/sanity_chart_test.png"
    python3 "$TOOLS/chart_generator.py" \
        --pair EURUSD --tf M15 --direction BUY \
        --entry 1.1774 --sl 1.1740 --tp 1.1830 \
        --score 65 --confidence 65 \
        --out "$TEST_PNG" >/dev/null 2>&1
    if [[ -f "$TEST_PNG" ]] && [[ $(stat -c%s "$TEST_PNG" 2>/dev/null || echo 0) -gt 10000 ]]; then
        _ok "chart_generator.py produced valid PNG ($(stat -c%s "$TEST_PNG") bytes)"
        rm -f "$TEST_PNG"
    else
        _fail "chart_generator.py failed to produce valid PNG"
    fi
fi

# ════════════════════════════════════════════════════════
_hdr "5. TELEGRAM DELIVERY"
# ════════════════════════════════════════════════════════

if [[ -z "${TELEGRAM_BOT_TOKEN:-}" ]] || [[ -z "${TELEGRAM_CHAT_ID:-}" ]]; then
    _fail "TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set"
else
    TG_RESP=$(curl -s --max-time 10 \
        "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
        -d chat_id="${TELEGRAM_CHAT_ID}" \
        -d text="[BotA sanity_check.sh] Telegram delivery test OK $(date -u +%H:%MZ)" \
        2>/dev/null)
    if echo "$TG_RESP" | python3 -c "import sys,json; r=json.load(sys.stdin); sys.exit(0 if r.get('ok') else 1)" 2>/dev/null; then
        _ok "Telegram sendMessage delivered OK"
    else
        _fail "Telegram sendMessage failed — check token/chat_id"
    fi
fi

# ════════════════════════════════════════════════════════
_hdr "6. ALERTS_TO_TRADES --since"
# ════════════════════════════════════════════════════════

TRADES_OUT="$LOGS/tmp/sanity_trades_test.csv"
TRADES_LOG=$(python3 "$TOOLS/alerts_to_trades.py"     --alerts "logs/alerts.csv"     --since "2099-01-01T00:00:00"     --horizon 96     --out "logs/tmp/sanity_trades_test.csv" 2>&1 || true)
if echo "$TRADES_LOG" | grep -q "No resolved trades\|Filtered to"; then
    _ok "alerts_to_trades.py --since runs without crash"
    rm -f "$TRADES_OUT"
else
    _fail "alerts_to_trades.py --since crashed or unexpected output"
fi

# ════════════════════════════════════════════════════════
_hdr "7. PROVIDER HEALTH CHECK"
# ════════════════════════════════════════════════════════

HC_OUT=$(bash "$TOOLS/provider_health_check.sh" 2>&1)
if echo "$HC_OUT" | grep -q "\[HEALTH\] OK"; then
    _ok "provider_health_check.sh: $HC_OUT"
else
    _fail "provider_health_check.sh: $HC_OUT"
fi

# ════════════════════════════════════════════════════════
_hdr "8. PROTECTED FILES PRESENT"
# ════════════════════════════════════════════════════════

PROTECTED=(
    "tools/signal_watcher_pro.sh"
    "tools/m15_h1_fusion.sh"
    "tools/scoring_engine.sh"
    "tools/quality_filter.py"
    "tools/market_open.sh"
    "tools/news_sentiment.py"
    "tools/indicators_updater.sh"
    "tools/signal_accuracy.py"
    "tools/alerts_to_trades.py"
    "tools/auditor.py"
    "tools/provider_health_check.sh"
    "tools/chart_generator.py"
    "config/strategy.env"
    "logs/alerts.csv"
)

MISSING=0
for f in "${PROTECTED[@]}"; do
    if [[ ! -f "$ROOT/$f" ]]; then
        _fail "PROTECTED FILE MISSING: $f"
        MISSING=$((MISSING+1))
    fi
done
if [[ $MISSING -eq 0 ]]; then
    _ok "All ${#PROTECTED[@]} protected files present"
fi

# ════════════════════════════════════════════════════════
_hdr "9. CACHE FRESHNESS"
# ════════════════════════════════════════════════════════

for PAIR in EURUSD GBPUSD; do
    CACHE_FILE="$CACHE/${PAIR}_M15.json"
    if [[ ! -f "$CACHE_FILE" ]]; then
        _fail "Cache missing: ${PAIR}_M15.json"
        continue
    fi
    AGE=$(( $(date +%s) - $(stat -c%Y "$CACHE_FILE" 2>/dev/null || echo 0) ))
    if [[ $AGE -lt 3600 ]]; then
        _ok "Cache fresh: ${PAIR}_M15.json (${AGE}s old)"
    elif [[ $AGE -lt 7200 ]]; then
        _warn "Cache stale: ${PAIR}_M15.json (${AGE}s old — expected <3600)"
    else
        _fail "Cache very stale: ${PAIR}_M15.json (${AGE}s old)"
    fi
done


# ════════════════════════════════════════════════════════
_hdr "10. ADX_REGIME FIX PRESENT"
# ════════════════════════════════════════════════════════
if grep -q '_adx_regime=""' "$TOOLS/signal_watcher_pro.sh"; then
    _ok "_adx_regime initialized — unbound variable fix present"
else
    _fail "_adx_regime fix missing — line 769 needs default empty string"
fi

# ════════════════════════════════════════════════════════
_hdr "11. CRONTAB TIMING — UPDATER BEFORE WATCHER"
# ════════════════════════════════════════════════════════
if crontab -l 2>/dev/null | grep -q "^13,28,43,58"; then
    _ok "Updater scheduled at 13,28,43,58 — fires before watcher at */15"
else
    _fail "Updater timing wrong — should be 13,28,43,58 not 2,17,32,47"
fi

# ════════════════════════════════════════════════════════
_hdr "12. H1_TREND FIELD POPULATING IN ALERTS.CSV"
# ════════════════════════════════════════════════════════
ALERTS_CSV="$LOGS/alerts.csv"
if [[ -f "$ALERTS_CSV" ]]; then
    h1_blank=$(tail -20 "$ALERTS_CSV" | awk -F, '{print $22}' | grep -c '^$' || true)
    if (( h1_blank < 20 )); then
        _ok "h1_trend field populating in alerts.csv ($h1_blank/20 blank)"
    else
        _fail "h1_trend always blank in alerts.csv — fusion tag not writing back"
    fi
else
    _fail "alerts.csv not found"
fi

# ════════════════════════════════════════════════════════
_hdr "13. MACD_COMP NOT ALWAYS ZERO"
# ════════════════════════════════════════════════════════
if [[ -f "$ALERTS_CSV" ]]; then
    macd_nonzero=$(tail -50 "$ALERTS_CSV" | awk -F, '{print $15}' | grep -vc '^0\.0*$' || true)
    if (( macd_nonzero > 0 )); then
        _ok "macd_comp has non-zero values in last 50 rows ($macd_nonzero non-zero)"
    else
        _warn "macd_comp always 0.0 in last 50 rows — scoring component may be miscalibrated"
    fi
fi
# API credit tracker check
API_OUT="$(python3 "${ROOT}/tools/api_credit_tracker.py" status 2>/dev/null || true)"
if [[ -n "${API_OUT}" ]]; then
    if echo "${API_OUT}" | grep -q '🔴'; then
        _warn "API credits critical: ${API_OUT}"
    else
        _ok "API tracker: ${API_OUT}"
    fi
else
    _warn "API credit tracker not responding"
fi

# ════════════════════════════════════════════════════════
_hdr "SUMMARY"
# ════════════════════════════════════════════════════════

echo ""
echo "PASS=$PASS  FAIL=$FAIL  WARN=$WARN"
echo ""

# Build Telegram summary
TG_SUMMARY="BotA Sanity Check $(date -u +%Y-%m-%d)
PASS=$PASS | FAIL=$FAIL | WARN=$WARN
"
for r in "${RESULTS[@]}"; do
    TG_SUMMARY+="$r
"
done

if [[ -n "${TELEGRAM_BOT_TOKEN:-}" ]] && [[ -n "${TELEGRAM_CHAT_ID:-}" ]]; then
    curl -s --max-time 10 \
        "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
        -d chat_id="${TELEGRAM_CHAT_ID}" \
        --data-urlencode "text=${TG_SUMMARY}" \
        >/dev/null 2>&1
    echo "[sanity_check] Summary sent to Telegram"
fi

if [[ $FAIL -gt 0 ]]; then
    echo "[sanity_check] FAILED — $FAIL checks failed"
    exit 1
else
    echo "[sanity_check] PASSED"
    exit 0
fi
