#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Dict, Tuple, Optional, List


def _root() -> Path:
    return Path(__file__).resolve().parents[1]


def _strip_quotes(v: str) -> str:
    v = v.strip()
    if len(v) >= 2 and ((v[0] == v[-1] == '"') or (v[0] == v[-1] == "'")):
        return v[1:-1]
    return v


def parse_env_file(path: Path) -> Dict[str, str]:
    """
    Minimal, safe .env parser:
      - supports lines: KEY=VALUE
      - supports: export KEY=VALUE
      - ignores blank lines and comments
      - does NOT eval anything
    """
    out: Dict[str, str] = {}
    if not path.exists() or not path.is_file():
        return out

    try:
        text = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        return out

    for raw in text:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        if not k:
            continue
        # key must be shell-safe
        if not (k[0].isalpha() or k[0] == "_"):
            continue
        if any(not (ch.isalnum() or ch == "_") for ch in k):
            continue
        v = _strip_quotes(v)
        out[k] = v
    return out


def choose_value(
    env_sources: List[Tuple[Path, Dict[str, str]]],
    aliases: List[str],
    env_first: bool = True,
) -> Tuple[Optional[str], Optional[str]]:
    """
    Return (value, source_path_str) for the first alias found with a non-empty value.
    If env_first True, prefer current process env first.
    """
    if env_first:
        for k in aliases:
            v = os.getenv(k)
            if v:
                return v, "<process-env>"

    for p, d in env_sources:
        for k in aliases:
            v = d.get(k)
            if v:
                return v, str(p)
    return None, None


def upsert_env_keys(env_path: Path, token: str, chat_id: str) -> Path:
    """
    Update env_path in-place WITHOUT printing secrets.
    - makes backup: .env.botA.bak.<timestamp>
    - removes any alias keys for token/chat_id and writes canonical keys:
        TELEGRAM_BOT_TOKEN=...
        TELEGRAM_CHAT_ID=...
    """
    env_path.parent.mkdir(parents=True, exist_ok=True)
    if env_path.exists():
        backup = env_path.with_name(env_path.name + f".bak.{time.strftime('%Y%m%d_%H%M%S')}")
        backup.write_bytes(env_path.read_bytes())
    else:
        backup = env_path.with_name(env_path.name + f".bak.{time.strftime('%Y%m%d_%H%M%S')}")
        backup.write_text("", encoding="utf-8")

    # Read existing lines (preserve unknown lines)
    lines: List[str] = []
    if env_path.exists():
        try:
            lines = env_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except Exception:
            lines = []

    TOKEN_KEYS = {"TELEGRAM_BOT_TOKEN", "TELEGRAM_TOKEN", "TG_BOT_TOKEN", "BOT_TOKEN"}
    CHAT_KEYS = {"TELEGRAM_CHAT_ID", "TG_CHAT_ID", "CHAT_ID", "TELEGRAM_CHANNEL_ID"}

    kept: List[str] = []
    for raw in lines:
        s = raw.strip()
        if not s or s.startswith("#"):
            kept.append(raw)
            continue

        t = s
        if t.startswith("export "):
            t = t[len("export ") :].strip()

        if "=" in t:
            k = t.split("=", 1)[0].strip()
            if k in TOKEN_KEYS or k in CHAT_KEYS:
                # drop (we'll write canonical keys at end)
                continue

        kept.append(raw)

    # Append canonical keys at end (no quotes; safe for our env_safe_source loader)
    kept.append(f"TELEGRAM_BOT_TOKEN={token}")
    kept.append(f"TELEGRAM_CHAT_ID={chat_id}")

    tmp = env_path.with_suffix(env_path.suffix + ".tmp")
    tmp.write_text("\n".join(kept).rstrip() + "\n", encoding="utf-8")
    os.replace(str(tmp), str(env_path))

    # ensure private permissions where possible (Termux may ignore chmod in some cases)
    try:
        os.chmod(str(env_path), 0o600)
    except Exception:
        pass

    return backup


def main() -> int:
    root = _root()
    env_bota = root / ".env.botA"

    candidates = [
        root / ".env.botA",
        root / ".env",
        root / ".env.telegram",
        root / ".env.runtime",
        root / "config" / "telegram.env",
        root / "config" / "tele.env",
    ]

    env_sources = [(p, parse_env_file(p)) for p in candidates]

    token_aliases = ["TELEGRAM_BOT_TOKEN", "TELEGRAM_TOKEN", "TG_BOT_TOKEN", "BOT_TOKEN"]
    chat_aliases = ["TELEGRAM_CHAT_ID", "TG_CHAT_ID", "CHAT_ID", "TELEGRAM_CHANNEL_ID"]

    token, token_src = choose_value(env_sources, token_aliases, env_first=True)
    chat_id, chat_src = choose_value(env_sources, chat_aliases, env_first=True)

    print("=== tele_env_sync: discovery (no secrets) ===")
    print("token :", "FOUND" if token else "MISSING", (f"len={len(token)}" if token else ""), f"src={token_src or 'NONE'}")
    print("chat  :", "FOUND" if chat_id else "MISSING", (f"len={len(chat_id)}" if chat_id else ""), f"src={chat_src or 'NONE'}")

    if not token or not chat_id:
        print("FAIL: cannot persist Telegram env. Ensure token+chat_id exist in one of these files:")
        for p in candidates:
            print(f" - {p}")
        return 2

    backup = upsert_env_keys(env_bota, token=token, chat_id=chat_id)

    # verify result (no secrets)
    d = parse_env_file(env_bota)
    tok2 = d.get("TELEGRAM_BOT_TOKEN", "")
    ch2 = d.get("TELEGRAM_CHAT_ID", "")
    print("=== tele_env_sync: persisted into .env.botA (no secrets) ===")
    print("backup:", str(backup))
    print("TELEGRAM_BOT_TOKEN:", "SET" if tok2 else "MISSING", (f"len={len(tok2)}" if tok2 else ""))
    print("TELEGRAM_CHAT_ID :", "SET" if ch2 else "MISSING", (f"len={len(ch2)}" if ch2 else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
