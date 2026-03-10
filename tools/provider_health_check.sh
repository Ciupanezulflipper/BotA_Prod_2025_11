#!/data/data/com.termux/files/usr/bin/bash
# provider_health_check.sh — Alert via Telegram if provider fetch/build fails
# Runs after each updater cycle (called from cron or standalone)

ROOT="${BOTA_ROOT:-$HOME/BotA}"
LOG="${ROOT}/logs/cron.updater_m15.log"

source "${ROOT}/config/strategy.env" 2>/dev/null || true

# Read last fail counts from log
last_line="$(grep "fetch_fail_count" "${LOG}" 2>/dev/null | tail -1)"
fetch_fails="$(echo "${last_line}" | grep -o 'fetch_fail_count=[0-9]*' | cut -d= -f2)"
build_fails="$(echo "${last_line}" | grep -o 'build_fail_count=[0-9]*' | cut -d= -f2)"

fetch_fails="${fetch_fails:-0}"
build_fails="${build_fails:-0}"

if [[ "${fetch_fails}" -gt 0 || "${build_fails}" -gt 0 ]]; then
    msg="⚠️ BotA Provider Alert%0Afetch_fail_count=${fetch_fails}%0Abuild_fail_count=${build_fails}%0ATime: $(date -u +%Y-%m-%dT%H:%MZ)"
    curl -s "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
        -d chat_id="${TELEGRAM_CHAT_ID}" \
        -d text="${msg}" \
        -d parse_mode="HTML" >/dev/null 2>&1
    echo "[HEALTH] ALERT sent: fetch=${fetch_fails} build=${build_fails}"
else
    echo "[HEALTH] OK fetch=${fetch_fails} build=${build_fails}"
fi
