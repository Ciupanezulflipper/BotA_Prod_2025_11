#!/usr/bin/env python3
import re, os, sys, json, time, csv, pathlib

HOME = os.path.expanduser("~/bot-a")
LOG  = os.path.join(HOME, "logs", "auto_conf.log")
CSV  = os.path.join(HOME, "data", "signals_log.csv")
pathlib.Path(os.path.dirname(CSV)).mkdir(parents=True, exist_ok=True)

def grab_last_block():
    try:
        with open(LOG, "r", encoding="utf-8", errors="ignore") as f:
            txt = f.read()
    except Exception:
        return ""
    blocks = txt.split("---- card start ----")
    return blocks[-1] if blocks else ""

def parse_block(b:str):
    data = {
        "utc": "",
        "entry": "", "sl": "", "tp1": "", "tp2": "",
        "m5":"", "m15":"", "h1":"", "h5":"", "h4":"", "d1":"",
        "final_bias":"", "confidence":"", "notes":""
    }

    m = re.search(r"Time:\s*([0-9: ]+UTC)", b)
    if m: data["utc"] = m.group(1).strip()

    m = re.search(r"Entry:\s*([0-9\.]+)\s*\|\s*SL:\s*([0-9\.]+)\s*\|\s*TP1:\s*([0-9\.]+)\s*\|\s*TP2:\s*([0-9\.]+)", b)
    if m:
        data["entry"], data["sl"], data["tp1"], data["tp2"] = m.groups()

    def bias(tf):
        m = re.search(rf"\b{tf}\s*→\s*([A-Z/]+)", b)
        return m.group(1) if m else ""
    data["m5"]=bias("M5"); data["m15"]=bias("M15"); data["h1"]=bias("H1")
    data["h5"]=bias("H5"); data["h4"]=bias("H4");  data["d1"]=bias("D1")

    m = re.search(r"Final Bias:\s*([A-Z/]+)", b)
    if m: data["final_bias"]=m.group(1)

    m = re.search(r"Confidence:\s*([0-9\.]+)/10", b)
    if m: data["confidence"]=m.group(1)

    # Notes line (adj/policy etc.)
    m = re.search(r"Adj:\s*(.+)", b)
    if m: data["notes"]=m.group(1).strip()

    return data

def append_csv(row:dict):
    hdr = ["ts","utc","entry","sl","tp1","tp2","m5","m15","h1","h5","h4","d1","final_bias","confidence","notes"]
    new = {
        "ts": int(time.time()),
        **row
    }
    file_exists = os.path.exists(CSV)
    with open(CSV, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=hdr)
        if not file_exists: w.writeheader()
        w.writerow(new)

def main():
    if "--from-log" in sys.argv:
        b = grab_last_block()
        if not b.strip(): sys.exit(0)
        row = parse_block(b)
        append_csv(row)
        sys.exit(0)

if __name__ == "__main__":
    main()
