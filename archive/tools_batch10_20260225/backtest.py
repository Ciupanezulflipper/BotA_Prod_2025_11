import datetime as dt
from .providers import get_ohlc
from .indicators_ext import compute_confluence
from .scoring_v2 import score_16_6

def backtest(pair: str, tf: str, days:int=3):
    # Simple walk-forward sampling: every Nth candle
    data, src = get_ohlc(pair, tf, bars=days*24*4)  # rough
    if not data:
        print("Backtest: no data available from providers; try later.")
        return
    wins=0; total=0
    step=max(5, len(data)//50)
    for i in range(50, len(data)-2, step):
        window=data[:i]
        md=compute_confluence(window)
        t,r,rs,ks,act=score_16_6(md)
        if act in ("BUY","SELL"):
            total+=1
            c0=window[-1]["close"]; c1=data[i+1]["close"]
            if act=="BUY" and c1>c0: wins+=1
            if act=="SELL" and c1<c0: wins+=1
    print(f"Backtest {pair} {tf}: signals={total} wins={wins} win_rate={(wins/total*100 if total else 0):.1f}%")

def main():
    import argparse
    ap=argparse.ArgumentParser()
    ap.add_argument("--pair", required=True)
    ap.add_argument("--tf", required=True)
    ap.add_argument("--days", type=int, default=3)
    a=ap.parse_args()
    backtest(a.pair,a.tf,a.days)

if __name__=="__main__":
    main()
