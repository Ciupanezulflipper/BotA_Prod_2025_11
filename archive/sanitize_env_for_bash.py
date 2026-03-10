#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
import sys
import time
from pathlib import Path
from typing import List, Tuple

LINE_RE = re.compile(r'^\s*(export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)$')

def _is_wrapped_quote(s: str) -> bool:
    s = s.strip()
    return len(s) >= 2 and ((s[0] == s[-1] == '"') or (s[0] == s[-1] == "'"))

def _split_value_comment(rest: str) -> Tuple[str, str]:
    """
    Split VALUE and trailing comment using a conservative rule:
      - if we find ' #' (space then #), treat that as comment start.
    This avoids breaking URLs/fragments that contain '#'.
    """
    idx = rest.find(" #")
    if idx == -1:
        return rest, ""
    return rest[:idx], rest[idx:]

def _needs_quoting(val: str) -> bool:
    """
    Quote ONLY when necessary to prevent bash syntax errors from unquoted special chars.
    We deliberately avoid touching command substitution values like $(...) or `...`.
    """
    v = val.strip()
    if v == "":
        return False
    if _is_wrapped_quote(v):
        return False
    # If user intentionally uses command substitution, don't alter semantics.
    if "$(" in v or "`" in v:
        return False

    # These characters commonly break bash when unquoted in assignment lines.
    breakers = ["(", ")", " ", "\t", ";", "&", "|", "<", ">", "#"]
    return any(ch in v for ch in breakers)

def _sh_single_quote(s: str) -> str:
    # Safe single-quote for bash: abc'def -> 'abc'"'"'def'
    return "'" + s.replace("'", "'\"'\"'") + "'"

def sanitize_env_file(path: Path, show_keys: bool = True) -> Tuple[Path, List[str], int]:
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(str(path))

    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    out_lines: List[str] = []
    changed_keys: List[str] = []
    changed_count = 0

    for raw in lines:
        s = raw.rstrip("\n")

        # keep blank lines + full-line comments untouched
        if s.strip() == "" or s.lstrip().startswith("#"):
            out_lines.append(s)
            continue

        m = LINE_RE.match(s)
        if not m:
            out_lines.append(s)
            continue

        export_prefix = "export " if m.group(1) else ""
        key = m.group(2)
        rest = m.group(3)

        val_part, comment = _split_value_comment(rest)

        # preserve exact empty value: KEY=
        if val_part.strip() == "":
            out_lines.append(f"{export_prefix}{key}={val_part.strip()}{comment}")
            continue

        if _needs_quoting(val_part):
            new_val = _sh_single_quote(val_part.strip())
            out_lines.append(f"{export_prefix}{key}={new_val}{comment}")
            changed_keys.append(key)
            changed_count += 1
        else:
            out_lines.append(s)

    # backup + atomic replace
    backup = path.with_name(path.name + f".bak.{time.strftime('%Y%m%d_%H%M%S')}")
    backup.write_bytes(path.read_bytes())

    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text("\n".join(out_lines).rstrip() + "\n", encoding="utf-8")
    os.replace(str(tmp), str(path))

    try:
        os.chmod(str(path), 0o600)
    except Exception:
        pass

    return backup, changed_keys, changed_count

def main() -> int:
    ap = argparse.ArgumentParser(description="Sanitize a .env file so bash can source it safely (no secrets printed).")
    ap.add_argument("env_file", nargs="?", default=str(Path.home() / "BotA" / ".env.botA"))
    ap.add_argument("--no-keys", action="store_true", help="Do not print changed key names")
    args = ap.parse_args()

    p = Path(args.env_file).expanduser().resolve()
    try:
        backup, keys, n = sanitize_env_file(p, show_keys=not args.no_keys)
    except FileNotFoundError:
        print(f"FAIL: file not found: {p}", file=sys.stderr)
        return 2
    except Exception as e:
        print(f"FAIL: sanitize error: {e}", file=sys.stderr)
        return 2

    print("=== sanitize_env_for_bash: DONE (no secrets) ===")
    print(f"file  : {p}")
    print(f"backup: {backup}")
    print(f"changed_lines: {n}")
    if not args.no_keys and keys:
        # keys only (safe), never values
        print("changed_keys:")
        for k in keys:
            print(f" - {k}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
