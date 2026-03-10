#!/data/data/com.termux/files/usr/bin/bash
###############################################################################
# FILE: tools/deploy_phase_fix.sh
# PURPOSE:
#   Fix caller-side PHASE capture bug (market_open.sh + '|| echo' inside $()).
# SCOPE:
#   Only these 3 live files:
#     - tools/scoring_engine.sh
#     - tools/smoke_market.sh
#     - tools/watch_wrap_market.sh
#   DO NOT MODIFY: tools/market_open.sh
#
# SAFETY:
#   - Forces TELEGRAM_ENABLED=0 and DRY_RUN_MODE=1
#   - Creates timestamped backups before writing (every run)
#   - Idempotent: if already patched, it will not re-patch (but will still sanity-check)
###############################################################################

set -euo pipefail

ROOT="/data/data/com.termux/files/home/BotA"
cd "${ROOT}" || exit 1

# Hard safety
export TELEGRAM_ENABLED=0
export DRY_RUN_MODE=1

ts="$(date +%Y%m%d_%H%M%S)"
log(){ printf "%s %s\n" "$(date -Iseconds)" "$*" >&2; }

need(){
  local p="$1"
  if [[ ! -e "$p" ]]; then
    log "ERROR: missing: $p"
    exit 1
  fi
}

log "=== PRECHECK (read-only) ==="
if [[ -f logs/error.log ]]; then
  log "--- logs/error.log tail 20 ---"
  tail -n 20 logs/error.log >&2 || true
fi

need tools/market_open.sh
need tools/scoring_engine.sh
need tools/smoke_market.sh
need tools/watch_wrap_market.sh

if ! command -v python3 >/dev/null 2>&1; then
  log "ERROR: python3 not found"
  exit 1
fi

log "=== BACKUP ==="
for f in tools/scoring_engine.sh tools/smoke_market.sh tools/watch_wrap_market.sh; do
  cp -a "$f" "$f.bak.${ts}"
  log "backup: $f -> $f.bak.${ts}"
done

log "=== PATCH (caller-side only) ==="
python3 - <<'PY'
import re, pathlib, sys

ROOT = pathlib.Path("/data/data/com.termux/files/home/BotA")
targets = [
    ("tools/scoring_engine.sh", "scoring"),
    ("tools/smoke_market.sh", "smoke"),
    ("tools/watch_wrap_market.sh", "wrap"),
]

BAD_RE = re.compile(r"market_open\.sh.*\|\|\s*echo")

def already_patched(text: str) -> bool:
    # Heuristic: presence of the safe pattern "|| true" on market_open capture
    return ("market_open.sh" in text) and ("|| true" in text) and (not BAD_RE.search(text))

def hardened_block(indent: str) -> str:
    # set -euo pipefail safe block (whitelist Open/Closed, else Unknown)
    return (
        f'{indent}PHASE="Unknown"\n'
        f'{indent}if [[ -x "${{TOOLS}}/market_open.sh" ]]; then\n'
        f'{indent}  _raw="$("${{TOOLS}}/market_open.sh" 2>/dev/null || true)"\n'
        f'{indent}  _raw="$(printf %s "${{_raw}}" | head -n1 | tr -d \'[:space:]\')"\n'
        f'{indent}  if [[ "${{_raw}}" == "Open" || "${{_raw}}" == "Closed" ]]; then\n'
        f'{indent}    PHASE="${{_raw}}"\n'
        f'{indent}  fi\n'
        f'{indent}  unset _raw\n'
        f'{indent}fi\n'
    )

def patch_file(path: pathlib.Path, mode: str) -> str:
    text = path.read_text(encoding="utf-8")
    if already_patched(text):
        return "SKIP_ALREADY_PATCHED"

    lines = text.splitlines(True)
    bad_idxs = []
    for i, ln in enumerate(lines):
        if ("market_open.sh" in ln) and ("||" in ln) and ("echo" in ln) and ("PHASE" in ln):
            bad_idxs.append(i)

    if len(bad_idxs) != 1:
        raise SystemExit(f"{path}: expected exactly 1 bad PHASE line, found {len(bad_idxs)}")

    i = bad_idxs[0]
    bad_line = lines[i]
    indent = re.match(r"^(\s*)", bad_line).group(1)

    if mode == "scoring":
        # Replace ONLY the single bad assignment line; keep surrounding PHASE="Unknown" and if [[ -x ... ]]; then
        repl = (
            f'{indent}_raw="$("${{TOOLS}}/market_open.sh" 2>/dev/null || true)"\n'
            f'{indent}_raw="$(printf %s "${{_raw}}" | head -n1 | tr -d \'[:space:]\')"\n'
            f'{indent}if [[ "${{_raw}}" == "Open" || "${{_raw}}" == "Closed" ]]; then\n'
            f'{indent}  PHASE="${{_raw}}"\n'
            f'{indent}fi\n'
            f'{indent}unset _raw\n'
        )
        lines[i] = repl
    else:
        # smoke/watch_wrap: replace the whole bad line with full hardened block (includes PHASE="Unknown")
        lines[i] = hardened_block(indent)

    out = "".join(lines)

    if BAD_RE.search(out):
        raise SystemExit(f"{path}: post-check failed (still contains 'market_open.sh || echo')")

    path.write_text(out, encoding="utf-8")
    return "PATCHED"

for rel, mode in targets:
    p = ROOT / rel
    status = patch_file(p, mode)
    print(f"{rel}: {status}")
PY

log "=== PERMS ==="
chmod 700 tools/scoring_engine.sh tools/smoke_market.sh tools/watch_wrap_market.sh

log "=== SYNTAX CHECK ==="
for f in tools/scoring_engine.sh tools/smoke_market.sh tools/watch_wrap_market.sh; do
  bash -n "$f"
  log "syntax_ok: $f"
done

log "=== VERIFY: no bad patterns remain ==="
if grep -nE 'market_open\.sh.*\|\|[[:space:]]*echo' tools/scoring_engine.sh tools/smoke_market.sh tools/watch_wrap_market.sh >/dev/null 2>&1; then
  log "ERROR: found remaining bad patterns:"
  grep -nE 'market_open\.sh.*\|\|[[:space:]]*echo' tools/scoring_engine.sh tools/smoke_market.sh tools/watch_wrap_market.sh || true
  log "ABORT + RESTORE"
  for f in tools/scoring_engine.sh tools/smoke_market.sh tools/watch_wrap_market.sh; do
    cp -a "$f.bak.${ts}" "$f"
  done
  exit 1
fi
log "OK: no bad patterns"

log "=== MINIMAL SANITY (no sends) ==="
set +e
mo_out="$(tools/market_open.sh 2>/dev/null)"
mo_rc=$?
set -e
mo_first="$(printf '%s' "${mo_out}" | head -n1 | tr -d '[:space:]')"
log "market_open_stdout_first=${mo_first:-<empty>} exit_code=${mo_rc} (0=open,1=closed)"

# scoring_engine should emit valid JSON even if HOLD (Closed market => HOLD)
json_out="$(bash tools/scoring_engine.sh EURUSD M15 2>/dev/null || true)"
JSON_OUT="${json_out}" python3 - <<'PY'
import os, json, sys
s = os.environ.get("JSON_OUT","").strip()
try:
    j = json.loads(s)
except Exception as e:
    print("FAIL: scoring_engine JSON parse error:", e)
    print("RAW_START")
    print(s[:800])
    print("RAW_END")
    raise SystemExit(1)
print("OK: scoring_engine_json_ok=1")
print("direction=%s" % j.get("direction"))
print("score=%s" % j.get("score"))
print("confidence=%s" % j.get("confidence"))
reasons = j.get("reasons","")
print("reasons_newline_count=%d" % reasons.count("\n"))
PY

log "=== DONE ==="
log "Rollback (if needed):"
log "  for f in tools/scoring_engine.sh tools/smoke_market.sh tools/watch_wrap_market.sh; do cp -a \"\$f.bak.${ts}\" \"\$f\"; done"
