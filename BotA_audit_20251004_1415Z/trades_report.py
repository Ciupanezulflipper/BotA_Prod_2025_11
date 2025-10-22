#!/usr/bin/env python3
import sys, math
import pandas as pd

def bucket(v, edges, labels):
    for e,lab in zip(edges, labels):
        if v <= e: return lab
    return labels[-1]

def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "trades.csv"
    df = pd.read_csv(path)

    # normalize cols
    for c in ["R_multiple","atr","duration_minutes","score16","score6"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    for c in ["action","hit_level","outcome","reason"]:
        if c in df.columns:
            df[c] = df[c].astype(str)

    total = len(df)
    none = (df["outcome"]=="NONE").sum() if "outcome" in df else 0
    completed = df[df["outcome"].isin(["WIN","LOSS"])].copy()

    print(f"\n=== OVERVIEW ===")
    print(f"Total rows: {total} | Completed: {len(completed)} | NONE: {none}")

    if len(completed)==0:
        print("No completed trades to analyze yet.")
        return

    # Core KPIs
    wr = (completed["outcome"]=="WIN").mean()*100
    avgR = completed["R_multiple"].mean()
    totalR = completed["R_multiple"].sum()
    pf = (completed.loc[completed["outcome"]=="WIN","R_multiple"].sum() /
          abs(completed.loc[completed["outcome"]=="LOSS","R_multiple"].sum() or 1))
    print(f"\nKPIs: WinRate={wr:.1f}%  AvgR={avgR:.2f}  TotalR={totalR:.2f}  PF={pf:.2f}")

    # Hit mix
    if "hit_level" in completed.columns:
        print("\nHit levels:")
        print(completed["hit_level"].value_counts(dropna=False))

    # Action split
    if "action" in completed.columns:
        print("\nBy action:")
        for side, g in completed.groupby("action"):
            wr = (g["outcome"]=="WIN").mean()*100
            print(f"  {side}: n={len(g)}  WR={wr:.1f}%  AvgR={g['R_multiple'].mean():.2f}")

    # Duration buckets
    if "duration_minutes" in completed.columns:
        bins = [60, 240, 720]  # 1h, 4h, 12h
        labels = ["<=1h","1-4h","4-12h",">12h"]
        completed["dur_bin"] = completed["duration_minutes"].apply(lambda x: bucket(x, bins, labels))
        print("\nBy duration:")
        print(completed.groupby("dur_bin")["R_multiple"].agg(['count','mean']))

    # ATR regime
    if "atr" in completed.columns:
        bins = [3, 5, 8]
        labels = ["<=3p","3-5p","5-8p",">8p"]
        completed["atr_bin"] = completed["atr"].apply(lambda x: bucket(x or 0, bins, labels))
        print("\nBy ATR regime (pips):")
        print(completed.groupby("atr_bin")["R_multiple"].agg(['count','mean']))

    # Score lift (if present)
    if "score16" in df.columns and df["score16"].notna().any():
        bins = [8, 12, 14]
        labels = ["<=8","9-12","13-14",">=15"]
        completed["s16_bin"] = completed["score16"].apply(lambda x: bucket(x or 0, bins, labels))
        print("\nBy score16 bin:")
        print(completed.groupby("s16_bin")["R_multiple"].agg(['count','mean']))

    # NONE reasons glance
    if none>0:
        ndf = df[df["outcome"]=="NONE"].copy()
        print("\nNONE rows (first 5):")
        print(ndf.head(5)[["timestamp","action","entry_price","tp1","tp2","tp3"]])

if __name__ == "__main__":
    main()
