# tools/pretty_bridge.py
# FULL FILE — Shell out to tools/status_pretty.py and extract sections for Telegram.

from __future__ import annotations

import asyncio
import os
import shlex
import sys
from typing import Tuple

SCRIPT_PATH = os.path.join(os.getcwd(), "tools", "status_pretty.py")


def _extract_sections(full_text: str) -> Tuple[str, str]:
    """
    Return (basic, advanced) text extracted between markers:
      === BASIC ===
      === ADVANCED ===
    Missing sections return "".
    """
    t = full_text.replace("\r\n", "\n")
    basic = ""
    adv = ""

    basic_marker = "=== BASIC ==="
    adv_marker = "=== ADVANCED ==="

    bidx = t.find(basic_marker)
    aidx = t.find(adv_marker)

    if bidx != -1:
        if aidx != -1 and aidx > bidx:
            basic = t[bidx + len(basic_marker) : aidx].strip()
        else:
            basic = t[bidx + len(basic_marker) :].strip()

    if aidx != -1:
        adv = t[aidx + len(adv_marker) :].strip()

    return basic, adv


async def _shell_capture() -> str:
    """
    Run 'python3 tools/status_pretty.py' and capture stdout/stderr.
    """
    if not os.path.isfile(SCRIPT_PATH):
        return f"⚠️ Missing script: {SCRIPT_PATH}"

    cmd = f"{shlex.quote(sys.executable)} {shlex.quote(SCRIPT_PATH)}"
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out_b, err_b = await proc.communicate()
    out = out_b.decode("utf-8", errors="replace")
    err = err_b.decode("utf-8", errors="replace")
    if proc.returncode != 0:
        return f"⚠️ status_pretty.py exited with {proc.returncode}\n{err or out}"
    if err.strip():
        out = out + ("\n\n[stderr]\n" + err.strip())
    return out


def _telegram_trim(s: str, hard_limit: int = 4000) -> str:
    """
    Trim for Telegram safety (prefer pair boundary).
    """
    if len(s) <= hard_limit:
        return s
    cut = s.rfind("\n\n📊", 0, hard_limit)
    if cut == -1:
        cut = hard_limit
    return s[:cut] + "\n\n⚠️ Output trimmed."


async def render_status(mode: str = "basic") -> str:
    """
    Public API used by tg_bot.py
    """
    raw = await _shell_capture()
    basic, adv = _extract_sections(raw)

    if mode == "advanced":
        text = adv or (basic if basic else raw)
    else:
        text = basic or (adv if adv else raw)

    # Tidy blank lines
    lines = [ln.rstrip() for ln in text.splitlines()]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    final = "\n".join(lines)

    return _telegram_trim(final, 4000)
