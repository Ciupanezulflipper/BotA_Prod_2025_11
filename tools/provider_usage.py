#!/usr/bin/env python3
"""R5 compatibility shim that keeps provider accounting in mutable runtime state.

The historical R5 release separates immutable code at BOTA_CODE_ROOT from
mutable state at BOTA_MUTABLE_ROOT. The legacy provider-accounting module only
consults BOTA_ROOT. In R5, prefer BOTA_MUTABLE_ROOT for its state/log files,
while preserving the original module/API verbatim in provider_usage_r5_legacy.py.
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path


def _load_legacy():
    mutable = os.environ.get("BOTA_MUTABLE_ROOT", "").strip()
    if mutable:
        os.environ["BOTA_ROOT"] = mutable

    path = Path(__file__).with_name("provider_usage_r5_legacy.py")
    spec = importlib.util.spec_from_file_location("_bota_provider_usage_r5_legacy", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load legacy provider usage module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_legacy = _load_legacy()

for _name in dir(_legacy):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_legacy, _name)


if __name__ == "__main__":
    raise SystemExit(_legacy.main())
