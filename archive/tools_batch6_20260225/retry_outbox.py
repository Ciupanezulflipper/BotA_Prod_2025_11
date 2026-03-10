#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Safe outbox retry stub.
- Uses Termux-safe lock in ~/bot-a/tmp/outbox.lock
- No-ops gracefully if there is nothing to retry
"""

import os
from lib_utils import TMP_DIR, file_lock, lock_path, ensure_dir, utcstr

LOCK = lock_path("outbox")

def main():
    ensure_dir(TMP_DIR)
    try:
        with file_lock(LOCK, timeout_sec=1):
            # Placeholder: if you add a persistent outbox later, handle it here.
            print(f"[INFO] retry_outbox @ {utcstr()} (nothing to retry)")
    except TimeoutError:
        print("[WARN] retry_outbox: another instance holds the lock, skipping")

if __name__ == "__main__":
    main()
