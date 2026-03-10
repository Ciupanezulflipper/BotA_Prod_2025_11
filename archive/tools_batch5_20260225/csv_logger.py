#!/data/data/com.termux/files/usr/bin/python3
# -*- coding: utf-8 -*-

"""
csv_logger.py
- Tiny logger with a CsvLogger class so runner_confluence can import it cleanly.
- Creates the file if missing; writes header once; appends rows atomically.
"""

import os, io

class CsvLogger:
    def __init__(self, path):
        self.path = path
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self._ensure_header()

    def _ensure_header(self):
        if not os.path.exists(self.path) or os.path.getsize(self.path) == 0:
            with open(self.path, "w") as f:
                f.write("timestamp,pair,side,confidence,sentiment,uid,note\n")

    def write_row(self, row):
        # row: dict with keys timestamp,pair,side,confidence,sentiment,uid,(note optional)
        ts = row.get("timestamp", "")
        pair = row.get("pair", "")
        side = row.get("side", "")
        conf = row.get("confidence", "")
        sent = row.get("sentiment", "")
        uid = row.get("uid", "")
        note = row.get("note", "")
        line = f"{ts},{pair},{side},{conf},{sent},{uid},{note}\n"
        tmp = self.path + ".tmp"
        with open(tmp, "a") as f:
            f.write(line)
        # append atomically
        with open(tmp, "r") as src, open(self.path, "a") as dst:
            for chunk in iter(lambda: src.read(8192), ""):
                dst.write(chunk)
        try:
            os.remove(tmp)
        except Exception:
            pass
