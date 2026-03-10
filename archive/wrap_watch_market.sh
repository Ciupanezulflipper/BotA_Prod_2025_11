#!/data/data/com.termux/files/usr/bin/bash
# FILE: tools/wrap_watch_market.sh (compat shim)
# DESC: For any legacy calls, defer to the canonical script.
set -euo pipefail
exec "$HOME/BotA/tools/watch_wrap_market.sh" "$@"
