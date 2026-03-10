path = "/data/data/com.termux/files/home/BotA/tools/chart_generator.py"
with open(path) as f:
    src = f.read()

# Fix 1+2: increase Y padding from 8% to 15% (SL/TP no longer cramped)
src = src.replace(
    "y_pad = (y_max - y_min) * 0.08",
    "y_pad = (y_max - y_min) * 0.15"
)

# Fix 3: RSI fill — correct direction (fill between RSI line and threshold, not panel edge)
src = src.replace(
    "    ax2.fill_between(x, rsi.values, 70, where=(rsi.values >= 70),\n                     alpha=0.15, color=col_dn)\n    ax2.fill_between(x, rsi.values, 30, where=(rsi.values <= 30),\n                     alpha=0.15, color=col_buy)",
    "    ax2.fill_between(x, rsi.values, 70, where=(rsi.values >= 70),\n                     interpolate=True, alpha=0.25, color=col_dn)\n    ax2.fill_between(x, 30, rsi.values, where=(rsi.values <= 30),\n                     interpolate=True, alpha=0.25, color=col_buy)"
)

# Fix 4: weekend gap — add vertical dashed line where time gap > 2 candles
old = "    # --- MACD histogram panel ---"
new = """    # Fix 4: mark weekend/session gaps with vertical lines
    import numpy as np as _np
    times = df.index.astype('int64') // 10**9
    diffs = _np.diff(times.values)
    median_diff = _np.median(diffs)
    for gap_i, d in enumerate(diffs):
        if d > median_diff * 3:
            for _ax in [ax1, ax2, ax3]:
                _ax.axvline(gap_i + 0.5, color='#444466', linewidth=0.8,
                           linestyle=':', alpha=0.7)

    # --- MACD histogram panel ---"""
src = src.replace(old, new)

with open(path, 'w') as f:
    f.write(src)
print("PATCHED OK")
