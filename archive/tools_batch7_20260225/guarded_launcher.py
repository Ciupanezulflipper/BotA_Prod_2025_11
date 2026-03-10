#!/usr/bin/env python3
"""
Launch Bot-A runner with a strong-only send gate and EURUSD-only filter,
without modifying runner_confluence.py.
"""
import argparse, os, sys, importlib

TOOLS = os.path.expanduser('~/bot-a/tools')
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)

# Pin EURUSD at process level (runner still reads WATCHLIST)
os.environ.setdefault("WATCHLIST", "EURUSD")

from tight_gate import guarded_sender  # noqa

def try_import(name):
    try:
        return importlib.import_module(name)
    except Exception:
        return None

def get_send_fn(runner_mod):
    for name in ("send_telegram", "send_signal", "send"):
        fn = getattr(runner_mod, name, None)
        if callable(fn):
            return name, fn
    return None, None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--pair", default="EURUSD")
    ap.add_argument("--tf", default=None)
    args, extra = ap.parse_known_args()

    os.environ["WATCHLIST"] = "EURUSD"

    journal = try_import("signal_journal")
    jr = getattr(journal, "append_row", None)

    runner = try_import("runner_confluence")
    if not runner:
        print("[GUARD] ERROR: could not import runner_confluence.py")
        sys.exit(2)

    name, send = get_send_fn(runner)
    if not send:
        print("[GUARD] WARNING: runner has no send_* function; nothing to gate.")
    else:
        wrapped = guarded_sender(send, journal_append_fn=jr)
        setattr(runner, name, wrapped)
        print(f"[GUARD] Patched sender '{name}' with strong-only gate")

    entry = getattr(runner, "main", None) or getattr(runner, "run", None)
    if entry:
        sys.argv = ["runner_confluence.py"] \
            + (["--dry-run"] if args.dry_run else []) \
            + (["--force"]   if args.force   else []) \
            + (["--pair", args.pair] if args.pair else []) \
            + (["--tf", args.tf] if args.tf else []) \
            + extra
        return entry()
    else:
        print("[GUARD] NOTE: runner has no entrypoint main()/run(). Nothing executed.")
        return 0

if __name__ == "__main__":
    sys.exit(main())
