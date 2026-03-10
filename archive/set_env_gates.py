#!/usr/bin/env python3
import argparse
import pathlib
import re
import sys
from typing import Dict, List, Tuple

ASSIGN_RX = re.compile(r'^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$')

SECRET_KEYS = {"TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "TELEGRAM_TOKEN"}

def parse_env_lines(lines: List[str]) -> Dict[str, str]:
    kv: Dict[str, str] = {}
    for line in lines:
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        m = ASSIGN_RX.match(s)
        if not m:
            continue
        k, v = m.group(1), m.group(2)
        v = v.strip()
        if (len(v) >= 2) and ((v[0] == v[-1]) and v[0] in ("'", '"')):
            v = v[1:-1]
        kv[k] = v
    return kv

def update_env_file(path: pathlib.Path, updates: Dict[str, str]) -> Tuple[bool, List[str]]:
    if not path.exists():
        raise FileNotFoundError(str(path))

    orig = path.read_text(encoding="utf-8", errors="replace").splitlines(True)  # keep newlines
    out = []
    seen = set()

    for line in orig:
        m = ASSIGN_RX.match(line.strip())
        if not m:
            out.append(line)
            continue
        key = m.group(1)
        if key in updates:
            # Preserve "export " prefix if present, but normalize spacing.
            prefix = "export " if line.lstrip().startswith("export ") else ""
            out.append(f"{prefix}{key}={updates[key]}\n")
            seen.add(key)
        else:
            out.append(line)

    # Append missing keys
    appended = False
    for k, v in updates.items():
        if k not in seen:
            out.append(f"{k}={v}\n")
            appended = True

    changed = (orig != out)
    if changed:
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text("".join(out), encoding="utf-8")
        tmp.replace(path)

    return changed, out

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True, help="Path to .env")
    ap.add_argument("--set", action="append", default=[], help="KEY=VALUE (repeatable)")
    ap.add_argument("--show", nargs="*", default=None, help="Show selected keys (no secrets)")
    args = ap.parse_args()

    path = pathlib.Path(args.file)
    if not path.is_absolute():
        path = (pathlib.Path("/data/data/com.termux/files/home/BotA") / path).resolve()

    if args.show is not None:
        if not path.exists():
            print(f"env_file={path} MISSING")
            return 0
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        kv = parse_env_lines(lines)
        keys = args.show if args.show else sorted(kv.keys())
        for k in keys:
            if k in SECRET_KEYS:
                continue
            print(f"{k}={kv.get(k,'(unset)')}")
        return 0

    updates: Dict[str, str] = {}
    for item in args.set:
        if "=" not in item:
            print(f"ERROR: bad --set (need KEY=VALUE): {item}", file=sys.stderr)
            return 2
        k, v = item.split("=", 1)
        k = k.strip()
        v = v.strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", k or ""):
            print(f"ERROR: bad key: {k}", file=sys.stderr)
            return 2
        # Keep values raw; caller decides quoting.
        updates[k] = v

    if not updates:
        print("ERROR: no updates provided", file=sys.stderr)
        return 2

    changed, _ = update_env_file(path, updates)
    print("updated=" + ("YES" if changed else "NO (already set)"))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
