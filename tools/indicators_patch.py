from __future__ import annotations
import types
from . import providers
try:
    from . import indicators_ext as _iex
except Exception:
    _iex = None

def _wrap_load_ohlc(orig):
    def wrapped(pair: str, tf: str, bars: int = 200, *a, **kw):
        data, src = providers.get_ohlc(pair, tf, bars)
        if data:
            return data
        return orig(pair, tf, bars, *a, **kw)
    return wrapped

if _iex is not None and hasattr(_iex, "load_ohlc") and isinstance(_iex.load_ohlc, types.FunctionType):
    _iex.load_ohlc = _wrap_load_ohlc(_iex.load_ohlc)
