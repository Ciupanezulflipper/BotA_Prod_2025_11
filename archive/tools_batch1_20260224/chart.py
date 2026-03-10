#!/usr/bin/env python3
"""
chart.py — produce a PNG chart (bytes) for a symbol/timeframe.

make_chart_png(symbol, tf, limit=300, df=None) -> bytes or None
- Uses provided df if not None, otherwise fetches via providers
- EMA20/50/200 overlays + RSI(14) lower panel
- Falls back to basic matplotlib if mplfinance is missing
"""

from __future__ import annotations
import io, warnings
import numpy as np
import pandas as pd
from typing import Optional

from tools import providers

# Try mplfinance; fallback to matplotlib-only
try:
    import mplfinance as mpf
    HAVE_MPF = True
except Exception:
    HAVE_MPF = False
import matplotlib
matplotlib.use("Agg")  # headless
import matplotlib.pyplot as plt

from .scoring import _ema, _rsi14  # reuse helpers

def _ensure_dt_index(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    if not isinstance(d.index, pd.DatetimeIndex):
        if "Date" in d.columns:
            d["Date"] = pd.to_datetime(d["Date"], utc=True, errors="coerce")
            d = d.set_index("Date")
        else:
            # last resort: create a dt index
            d.index = pd.to_datetime(d.index, utc=True, errors="coerce")
    return d

def make_chart_png(symbol: str, tf: str, limit: int=300, df: Optional[pd.DataFrame]=None) -> Optional[bytes]:
    if df is None:
        df = providers.fetch_ohlcv_safe(symbol, tf=tf, limit=limit)
    if df is None or df.empty:
        return None

    df = df.copy()
    df = _ensure_dt_index(df)
    # ensure OHL C names
    for col in ["Open","High","Low","Close"]:
        if col not in df.columns:
            return None

    # Indicators
    df["ema20"]  = _ema(df["Close"], 20)
    df["ema50"]  = _ema(df["Close"], 50)
    df["ema200"] = _ema(df["Close"], 200)
    df["rsi14"]  = _rsi14(df["Close"])

    # Render
    if HAVE_MPF:
        apds = [
            mpf.make_addplot(df["ema20"], color="#1f77b4"),  # default palette colors
            mpf.make_addplot(df["ema50"], color="#ff7f0e"),
            mpf.make_addplot(df["ema200"], color="#2ca02c"),
        ]
        rsi_panel = mpf.make_addplot(df["rsi14"], panel=1)
        apds.append(rsi_panel)

        fig_bytes = io.BytesIO()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            mpf.plot(
                df,
                type="candle",
                style="yahoo",
                addplot=apds,
                volume=False,
                ylabel="Price",
                ylabel_lower="RSI",
                panel_ratios=(3,1),
                title=f"{symbol} • {tf} • {pd.Timestamp.utcnow().strftime('%Y-%m-%d %H:%MZ')}",
                savefig=dict(fname=fig_bytes, dpi=140, bbox_inches="tight"),
            )
        return fig_bytes.getvalue()

    # Fallback (no mplfinance): line chart close + EMAs + RSI subplot
    fig = plt.figure(figsize=(9, 5))
    ax1 = fig.add_subplot(2,1,1)
    ax2 = fig.add_subplot(2,1,2, sharex=ax1)

    ax1.plot(df.index, df["Close"], label="Close")
    ax1.plot(df.index, df["ema20"],  label="EMA20")
    ax1.plot(df.index, df["ema50"],  label="EMA50")
    ax1.plot(df.index, df["ema200"], label="EMA200")
    ax1.set_title(f"{symbol} • {tf} • {pd.Timestamp.utcnow().strftime('%Y-%m-%d %H:%MZ')}")
    ax1.set_ylabel("Price")
    ax1.legend(loc="upper left", ncol=4, fontsize=8)

    ax2.plot(df.index, df["rsi14"], label="RSI14")
    ax2.axhline(70, ls="--", lw=0.8)
    ax2.axhline(30, ls="--", lw=0.8)
    ax2.set_ylabel("RSI")
    ax2.set_xlabel("Time")

    buf = io.BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format="png", dpi=140, bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()

if __name__ == "__main__":
    png = make_chart_png("EURUSD", "5min", 300, df=None)
    print("png bytes:", 0 if png is None else len(png))
