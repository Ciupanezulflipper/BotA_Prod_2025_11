#!/usr/bin/env python3
"""
Publish a BotA signal to Supabase ProfitLab dashboard.
Uses only stdlib urllib — no extra packages needed.
"""
import os, sys, json, urllib.request, urllib.error

SUPABASE_URL = "https://ozgkeslgjqbqfewojnmr.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

def score_to_strength(score: int) -> int:
    if score >= 85: return 5
    if score >= 70: return 4
    if score >= 55: return 3
    if score >= 40: return 2
    return 1

def publish(pair, direction, entry, sl, tp, score, tf, tier):
    if not SUPABASE_KEY:
        print("[supabase_publish] ❌ SUPABASE_SERVICE_KEY not set", file=sys.stderr)
        return False

    min_tier = "free" if tier == "YELLOW" else "pro"

    payload = {
        "pair":            pair.upper(),
        "direction":       direction.upper(),
        "entry_price":     float(entry),
        "stop_loss":       float(sl),
        "take_profit":     float(tp),
        "signal_strength": score_to_strength(int(score)),
        "status":          "ACTIVE",
        "timeframe":       tf.upper(),
        "min_tier":        min_tier,
        "rationale":       f"BotA score={score} tier={tier}",
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/signals",
        data=data,
        headers={
            "Content-Type":  "application/json",
            "apikey":        SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Prefer":        "return=minimal",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            print(f"[supabase_publish] ✅ published {pair} {direction} entry={entry}", file=sys.stderr)
            return True
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        print(f"[supabase_publish] ❌ HTTP {e.code}: {body[:200]}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"[supabase_publish] ❌ {e}", file=sys.stderr)
        return False

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--pair",      required=True)
    ap.add_argument("--direction", required=True)
    ap.add_argument("--entry",     required=True)
    ap.add_argument("--sl",        required=True)
    ap.add_argument("--tp",        required=True)
    ap.add_argument("--score",     required=True)
    ap.add_argument("--tf",        required=True)
    ap.add_argument("--tier",      default="GREEN")
    args = ap.parse_args()
    ok = publish(args.pair, args.direction, args.entry, args.sl, args.tp, args.score, args.tf, args.tier)
    sys.exit(0 if ok else 1)
