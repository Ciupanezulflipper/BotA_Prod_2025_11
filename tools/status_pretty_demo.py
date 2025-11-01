# tools/status_pretty_demo.py
# FULL FILE — Preview what /status and /status advanced will send.

from __future__ import annotations

import asyncio
from tools.pretty_bridge import render_status


async def main() -> None:
    print("=== BASIC (bridge) ===")
    print(await render_status("basic"))
    print("\n=== ADVANCED (bridge) ===")
    print(await render_status("advanced"))


if __name__ == "__main__":
    asyncio.run(main())
