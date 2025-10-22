#!/usr/bin/env python3
# tools/health_ping.py
# Send a compact Bot-A health report to Telegram (falls back to stdout).

import os, subprocess, datetime, glob, re, sys, pathlib

APP = os.path.expanduser("~/bot-a")
RUN = os.path.expanduser("~/.bot-a/run")
LOG = os.path.expanduser("~/.bot-a/logs")

def utc_now():
    return datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

def pid_status(name, pidfile):
    pf = os.path.join(RUN, pidfile)
    if not os.path.exists(pf):
        return f"• {name}: stopped"
    try:
        with open(pf, "r") as f:
            pid = f.read().strip()
        # running?
        os.kill(int(pid), 0)
        # uptime (ps etime)
        try:
            et = subprocess.check_output(["ps", "-o", "etime=", "-p", pid], text=True).strip()
        except Exception:
            et = "?"
        return f"• {name}: RUNNING (pid {pid}, up {et})"
    except Exception:
        try:
            os.remove(pf)
        except Exception:
            pass
        return f"• {name}: STALE (pidfile removed)"

def latest(path_glob):
    files = sorted(glob.glob(path_glob), key=os.path.getmtime, reverse=True)
    return files[0] if files else ""

def last_banner(line):
    # lines like: "========== 2025-09-13 14:00:01 UTC =========="
    m = re.search(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} UTC)", line or "")
    return m.group(1) if m else ""

def today_counts(runner_log):
    if not runner_log or not os.path.exists(runner_log):
        return "   (no runner log)"
    day = datetime.datetime.utcnow().strftime("%Y%m%d")
    base = os.path.basename(runner_log)
    if day not in base:
        return f"   (latest not today: {base})"
    # counts based on our runner summary lines
    with open(runner_log, "r", errors="ignore") as f:
        data = f.read()
    sent = len(re.findall(r"✅ sent", data, flags=re.I))
    skip = len(re.findall(r"⏭️ skip", data, flags=re.I))
    prnt = len(re.findall(r"🖨️ printed", data, flags=re.I))
    err  = len(re.findall(r"❌ error", data, flags=re.I))
    return f"   today: sent {sent} | skipped {skip} | printed {prnt} | errors {err}"

def tail(path, n=6):
    if not path or not os.path.exists(path):
        return ""
    try:
        out = subprocess.check_output(["tail", "-n", str(n), path], text=True, errors="ignore")
    except Exception:
        out = ""
    return out.strip()

def send(text):
    try:
        sys.path.insert(0, APP)
        from tools.telegramalert import send_text
        ok = send_text(text)
        if not ok:
            print(text)
    except Exception:
        print(text)

def build_report():
    parts = []
    parts.append(f"🩺 *Bot-A Health* — {utc_now()}")
    # loops
    parts.append(pid_status("signal run loop", "signal_runner.pid"))
    parts.append(pid_status("digest loop",      "digest_loop.pid"))
    parts.append(pid_status("error monitor",    "error_monitor.pid"))

    # logs
    rlog = latest(os.path.join(LOG, "runner-*.log"))
    dlog = latest(os.path.join(LOG, "digest-*.log"))

    parts.append("")
    parts.append(f"• Latest runner log: {os.path.basename(rlog) if rlog else '(none)'}")
    if rlog:
        # last banner
        lb = ""
        try:
            with open(rlog, "r", errors="ignore") as f:
                for line in f:
                    if "==========" in line:
                        lb = line
            lb = last_banner(lb)
        except Exception:
            lb = ""
        if lb:
            parts.append(f"   last: {lb}")
        parts.append(today_counts(rlog))

    parts.append(f"• Latest digest log: {os.path.basename(dlog) if dlog else '(none)'}")
    if dlog:
        lb = ""
        try:
            with open(dlog, "r", errors="ignore") as f:
                for line in f:
                    if "==========" in line:
                        lb = line
            lb = last_banner(lb)
        except Exception:
            lb = ""
        if lb:
            parts.append(f"   last: {lb}")

    return "\n".join(parts)

def main():
    report = build_report()
    send(report)

if __name__ == "__main__":
    main()
