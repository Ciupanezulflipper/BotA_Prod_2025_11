#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
ROOT="$HOME/BotA"
TOOL="$ROOT/tools/telecontroller.py"

echo "== 1) Syntax =="
python3 -m py_compile "$TOOL" && echo "OK"

echo "== 2) Non-ASCII scan (should be empty) =="
# Show any byte outside printable ASCII range 0x20..0x7E and newlines/tabs
if LC_ALL=C grep -n -P '[^\x09\x0a\x0d\x20-\x7e]' "$TOOL" >/dev/null 2>&1; then
  LC_ALL=C grep -n -P '[^\x09\x0a\x0d\x20-\x7e]' "$TOOL" || true
  echo "FAIL: Non-ASCII found"
  exit 1
else
  echo "OK: ASCII-only"
fi

echo "== 3) Dry import =="
python3 - <<'PY'
import importlib.util, sys, os
p = os.path.expanduser("~/BotA/tools/telecontroller.py")
spec = importlib.util.spec_from_file_location("telecontroller", p)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
print("Imported OK; TOKEN set? {}".format(bool(m.TOKEN)))
PY

echo "== Smoke complete =="
