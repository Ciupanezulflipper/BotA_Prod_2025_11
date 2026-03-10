#!/usr/bin/env python3
"""
Chain guards (strong-only -> anti-dupe -> spread) without editing runner.
"""
import argparse, os, sys, importlib

TOOLS = os.path.expanduser('~/bot-a/tools')
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)

os.environ.setdefault("WATCHLIST", "EURUSD")

from tight_gate import guarded_sender as strong_gate      # strong-only (your file)
from anti_dupe_gate import anti_dupe_sender               # new
from spread_guard import spread_guard_sender              # new

def try_import(name):
    try: return importlib.import_module(name)
    except Exception: return None

def get_send_fn(runner_mod):
    for name in ("send_telegram", "send_signal", "send"):
        fn = getattr(runner_mod, name, None)
        if callable(fn):
            return name, fn
    return None, None

def chain(*funcs):
    def apply(fn):
        for g in funcs:
            fn = g(fn)
        return fn
    return apply

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
        print("[GUARD] ERROR: could not import runner_confluence.py"); return 2

    name, send = get_send_fn(runner)
    if not send:
        print("[GUARD] WARNING: runner has no send_* function; nothing to gate.")
    else:
        wrapped = chain(
            lambda f: strong_gate(f, journal_append_fn=jr),
            lambda f: anti_dupe_sender(f, journal_append_fn=jr),
            lambda f: spread_guard_sender(f, journal_append_fn=jr),
        )(send)
        setattr(runner, name, wrapped)
        print(f"[GUARD] Patched sender '{name}' with strong+dupe+spread gates")

    entry = getattr(runner, "main", None) or getattr(runner, "run", None)
    if entry:
        sys.argv = ["runner_confluence.py"] \
            + (["--dry-run"] if args.dry_run else []) \
            + (["--force"]   if args.force   else []) \
            + (["--pair", args.pair] if args.pair else []) \
            + (["--tf", args.tf] if args.tf else []) \
            + extra
        return entry()
    print("[GUARD] NOTE: runner has no entrypoint; nothing executed.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
