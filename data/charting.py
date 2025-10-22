import os, io, datetime as dt
import pandas as pd
import mplfinance as mpf
from .providers import fetch_ohlcv_safe

# Returns (png_bytes) or None
def make_chart(symbol: str, tf: str, title: str,
               entry=None, stop=None, target=None, limit=200):
    df = fetch_ohlcv_safe(symbol, tf=tf, limit=limit)
    if df is None or df.empty:
        return None

    df = df.rename(columns=str.title)
    df.index = pd.to_datetime(df.index)

    ap = []
    # Annotate entry/stop/target (horizontal lines)
    hlines = []
    colors = []

    def add_h(val, color):
        if val is not None:
            hlines.append(val); colors.append(color)

    add_h(entry, "tab:blue")
    add_h(stop, "tab:red")
    add_h(target, "tab:green")

    if hlines:
        ap.append(mpf.make_addplot(pd.Series([None]*len(df), index=df.index)))  # dummy to enable hlines
    style = mpf.make_mpf_style(base_mpf_style='yahoo', gridstyle='-', facecolor='#0f172a', edgecolor='white',
                               figcolor='#0f172a', rc={'font.size': 10, 'axes.labelcolor':'white','text.color':'white'})

    buf = io.BytesIO()
    mpf.plot(
        df,
        type='candle',
        volume=False,
        title=f"{title}\n{dt.datetime.utcnow().strftime('%Y-%m-%d %H:%MZ')}",
        style=style,
        addplot=ap,
        hlines=dict(hlines=hlines, colors=colors, linewidths=[1.0]*len(hlines), alpha=0.9),
        tight_layout=True,
        savefig=dict(fname=buf, dpi=140, bbox_inches='tight', pad_inches=0.15)
    )
    buf.seek(0)
    return buf.read()
