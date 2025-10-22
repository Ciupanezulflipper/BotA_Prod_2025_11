"""
BotA/tools/net_mode.py

Quick helper to toggle network settings for different environments.

Usage:
    python -m BotA.tools.net_mode normal   # land mode, SSL on
    python -m BotA.tools.net_mode ship     # ship mode, SSL off
    python -m BotA.tools.net_mode cache    # cache-only
    python -m BotA.tools.net_mode status   # show current settings
"""

import os
from pathlib import Path

RUNTIME_ENV = Path.home() / ".env.runtime"

MODES = {
    "normal": {
        "VERIFY_SSL": "true",
        "PROVIDER_ORDER": "yahoo,alphavantage,twelvedata",
    },
    "ship": {
        "VERIFY_SSL": "false",
        "PROVIDER_ORDER": "yahoo,alphavantage,twelvedata",
    },
    "cache": {
        "VERIFY_SSL": "true",
        "PROVIDER_ORDER": "yahoo",  # will fall back to cache if throttled
    },
}

def load_runtime_env():
    if not RUNTIME_ENV.exists():
        return {}
    env = {}
    with open(RUNTIME_ENV, "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k] = v
    return env

def save_runtime_env(env):
    RUNTIME_ENV.parent.mkdir(parents=True, exist_ok=True)
    with open(RUNTIME_ENV, "w") as f:
        f.write("# BotA runtime environment\n")
        for k, v in sorted(env.items()):
            f.write(f"{k}={v}\n")
    print(f"✓ Updated {RUNTIME_ENV}")

def set_mode(mode_name: str):
    if mode_name not in MODES:
        print(f"Error: Unknown mode '{mode_name}'")
        print(f"Available: {', '.join(MODES.keys())}")
        return
    env = load_runtime_env()
    env.update(MODES[mode_name])
    save_runtime_env(env)
    print(f"✓ Network mode set to {mode_name}")
    show_status(env)

def show_status(env=None):
    if env is None:
        env = load_runtime_env()
    print("\nCurrent Settings:")
    print(f"  VERIFY_SSL:     {env.get('VERIFY_SSL', 'not set')}")
    print(f"  PROVIDER_ORDER: {env.get('PROVIDER_ORDER', 'not set')}")
    for mode_name, config in MODES.items():
        if all(env.get(k) == v for k, v in config.items()):
            print(f"  Active mode:    {mode_name}")
            break
    else:
        print("  Active mode:    custom")

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    cmd = sys.argv[1].lower()
    if cmd == "status":
        show_status()
    elif cmd in MODES:
        set_mode(cmd)
    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
        sys.exit(1)
