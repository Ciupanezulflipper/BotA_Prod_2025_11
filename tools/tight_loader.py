#!/usr/bin/env python3
import subprocess, os, sys, json, time
def run_gate():
    r = subprocess.run(
        ["python3", os.path.expanduser("~/bot-a/tools/tight_gate.py")],
        capture_output=True, text=True
    )
    return r.returncode==0, (r.stdout or r.stderr).strip()
def emit_block_to_journal(reason):
    # append minimal CSV line with reason
    path = os.path.expanduser("~/bot-a/data/signal_journal.csv")
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    line = f"{ts},BLOCK,EURUSD,M15,0,0.0,{reason},tight_loader.py,0\n"
    with open(path,"a") as f: f.write(line)
def main():
    ok, msg = run_gate()
    if not ok:
        emit_block_to_journal(msg)
        print(f"[GATE] {msg}")
        sys.exit(2)
    print("[GATE] OK")
if __name__ == "__main__":
    main()
