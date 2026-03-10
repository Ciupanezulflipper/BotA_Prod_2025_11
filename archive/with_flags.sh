#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
. "$DIR/env_loader.sh"
exec "$@"
