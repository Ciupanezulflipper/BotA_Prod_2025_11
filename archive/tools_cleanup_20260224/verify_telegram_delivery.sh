#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

BOT_DIR="${BOT_DIR:-$HOME/BotA}"
ENV_FILE="$BOT_DIR/.env"
LOG_DIR="$BOT_DIR/logs"
LOG_FILE="$LOG_DIR/send-tg.log"
SENDER="$BOT_DIR/tools/send-tg.sh"
mkdir -p "$LOG_DIR"

ts(){ date +"%Y-%m-%d %H:%M:%S%z"; }
info(){ printf "[INFO] %s | %s\n" "$(ts)" "$*"; }
fail(){ printf "[FAIL] %s | %s\n" "$(ts)" "$*"; }
ok(){   printf "[PASS] %s | %s\n" "$(ts)" "$*"; }

die(){ fail "$*"; exit 1; }

# --- Preconditions
[[ -x "$SENDER" ]] || die "Sender not executable: $SENDER"
[[ -f "$ENV_FILE" ]] || die "Missing env file: $ENV_FILE"

TOKEN="$(grep -E '^TELEGRAM_TOKEN=' "$ENV_FILE" | head -n1 | cut -d= -f2- || true)"
[[ -n "$TOKEN" ]] || die "TELEGRAM_TOKEN missing in $ENV_FILE"
[[ "$TOKEN" =~ ^[0-9]{8,10}:[A-Za-z0-9_-]{35,}$ ]] || die "Invalid TELEGRAM_TOKEN format"

API_BASE="${BOT_API_BASE:-https://api.telegram.org}"
GETME_URL="${API_BASE%/}/bot${TOKEN}/getMe"

# --- 0) Token check
info "curl version: $(curl --version | head -n1)"
info "IPv4 connectivity test to base…"
code_base="$(curl -sS -I -4 "$API_BASE" | head -n1 | awk '{print $2}' || true)"
info "base HEAD http=${code_base:-n/a}"

info "getMe (IPv4)…"
resp="$(curl -sS -4 "$GETME_URL" || true)"
okflag="$(printf "%s" "$resp" | grep -o '"ok":true' || true)"
if [[ -n "$okflag" ]]; then
  ok "getMe http=200 ok=true"
else
  fail "getMe failed: $(printf "%s" "$resp" | sed -n 's/.*"description":"\([^"]*\)".*/\1/p')"
  exit 2
fi

# --- Helpers
send_text(){
  local label="$1" text="$2"
  info "Running: ${label} | bytes=${#text}"
  if "$SENDER" --text "$text"; then
    ok "${label}"
    return 0
  else
    fail "${label}"
    return 1
  fi
}

send_file(){
  local label="$1" data="$2"
  local tmp; tmp="$(mktemp)"
  printf "%s" "$data" >"$tmp"
  info "Running: ${label} | bytes=$(wc -c <"$tmp" | tr -d ' ')"
  if "$SENDER" --file "$tmp"; then
    rm -f "$tmp"
    ok "${label}"
    return 0
  else
    rm -f "$tmp"
    fail "${label}"
    return 1
  fi
}

# --- 1) Case: Simple HTML (should be OK as HTML)
PASS=0; FAIL=0
if send_text "Case 1: Simple HTML" "<b>BotA Verify</b> • $(date +%H:%M:%S) • Simple HTML"; then PASS=$((PASS+1)); else FAIL=$((FAIL+1)); fi

# --- 2) Case: Entities stress → should fallback to <pre>
case2_content='<b>bad & unbalanced <tag></b>
& " < >'
if send_file "Case 2: Entities Stress → <pre> fallback" "$case2_content"; then PASS=$((PASS+1)); else FAIL=$((FAIL+1)); fi

# --- 3) Case: Oversize 5k → Trim 4096
oversize="$(python3 - <<'PY'
print("X"*5000)
PY
)"
if send_file "Case 3: Oversize 5k → Trim 4096" "$oversize"; then PASS=$((PASS+1)); else FAIL=$((FAIL+1)); fi

printf "\n==============================================\n"
printf " Smoke Test Summary: PASS=%d  FAIL=%d\n" "$PASS" "$FAIL"
printf " Log file (sender): %s\n" "$LOG_FILE"
printf "==============================================\n\n"

if (( FAIL > 0 )); then
  printf "================= Sender Log (last 40) =================\n"
  tail -n 40 "$LOG_FILE" || true
  printf "========================================================\n\n"
  exit 3
fi
exit 0
