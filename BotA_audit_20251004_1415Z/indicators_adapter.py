import os
import pandas as pd

def _lower_cols(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).lower() for c in df.columns]
    rename_map = {
        'o':'open','h':'high','l':'low','c':'close',
        'Open':'open','High':'high','Low':'low','Close':'close'
    }
    df = df.rename(columns=rename_map)
    return df

def _ensure_time_index(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    # If there's a 'time' column, parse it and set as index.
    if 'time' in df.columns:
        df['time'] = pd.to_datetime(df['time'], utc=True, errors='coerce')
        df = df.dropna(subset=['time']).sort_values('time')
        df = df.set_index('time')
    # If index is named 'time', make sure it's datetime and unique
    if df.index.name == 'time':
        if not pd.api.types.is_datetime64_any_dtype(df.index):
            df = df.reset_index().rename(columns={'index':'time'})
            df['time'] = pd.to_datetime(df['time'], utc=True, errors='coerce')
            df = df.dropna(subset=['time']).set_index('time')
        df = df[~df.index.duplicated(keep='last')]
    # Drop any accidental 'time' column left behind
    if 'time' in df.columns:
        df = df.drop(columns=['time'])
    return df.sort_index()

def _ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False, min_periods=n).mean()

def analyze_indicators(df_in: pd.DataFrame, pair: str) -> dict:
    """
    Returns dict: action ('BUY'/'SELL'/'WAIT'), score16, score6, reason.
    Heuristic: EMA and MACD alignment + slope.
    """
    try:
        df = _lower_cols(df_in)
        df = _ensure_time_index(df)
        for col in ['open','high','low','close']:
            if col not in df.columns:
                raise ValueError(f"missing OHLC column: {col}")
        df = df.dropna(subset=['close']).copy()

        short_bars = int(os.getenv('IND_SHORT_BARS', '120'))
        long_bars  = int(os.getenv('IND_LONG_BARS',  '360'))
        need = max(200, long_bars + 10)  # ensure enough for EMAs/MACD

        if len(df) < need:
            return {
                "action":"WAIT","score16":0,"score6":0,
                "reason": f"short[need>={short_bars}] long[need>={long_bars}] rows[{len(df)}<{need}]"
            }

        close = df['close']
        ema12  = _ema(close, 12)
        ema26  = _ema(close, 26)
        macd   = ema12 - ema26
        macds  = _ema(macd, 9)
        ema50  = _ema(close, 50)
        ema200 = _ema(close, 200)

        # Recent values
        c  = float(close.iloc[-1])
        e50 = float(ema50.iloc[-1]) if not pd.isna(ema50.iloc[-1]) else None
        e200= float(ema200.iloc[-1]) if not pd.isna(ema200.iloc[-1]) else None
        m   = float(macd.iloc[-1]) if not pd.isna(macd.iloc[-1]) else None
        ms  = float(macds.iloc[-1]) if not pd.isna(macds.iloc[-1]) else None

        # Slopes (last 5 bars)
        def slope(s: pd.Series, k=5):
            s = s.dropna()
            if len(s) < k+1: return 0.0
            return float(s.iloc[-1] - s.iloc[-1-k])

        slope50  = slope(ema50, 5)
        slope200 = slope(ema200,5)
        slopeMacd= slope(macd,  5)

        # Votes
        votes_buy = 0
        votes_sell= 0

        if e50 is not None and e200 is not None:
            if e50 > e200: votes_buy += 1
            if e50 < e200: votes_sell += 1
        if slope50 > 0:  votes_buy += 1
        if slope50 < 0:  votes_sell += 1
        if m is not None and ms is not None:
            if m > ms: votes_buy += 1
            if m < ms: votes_sell += 1
        if c > (e50 or c): votes_buy += 1
        if c < (e50 or c): votes_sell += 1

        # Scores (crude mapping: up to 4 buy votes ~ 16, 6-score mirrors momentum bits)
        score16 = int((votes_buy / 4.0) * 16) if votes_buy >= votes_sell else int((votes_sell / 4.0) * 16)
        # Momentum-focused (macd cross + ema50 slope + price vs ema50)
        mom_buy = 0
        if slopeMacd > 0: mom_buy += 1
        if slope50   > 0: mom_buy += 1
        if c > (e50 or c): mom_buy += 1
        score6 = mom_buy * 2  # 0..6

        if votes_buy > votes_sell and score16 >= 8:
            action = "BUY"
            why = "EMA50>EMA200 + EMA50 slope up + MACD>signal + price>EMA50"
        elif votes_sell > votes_buy and score16 >= 8:
            action = "SELL"
            why = "EMA50<EMA200 + EMA50 slope down + MACD<signal + price<EMA50"
        else:
            action = "WAIT"
            why = "insufficient confluence"

        return {
            "action": action,
            "score16": score16,
            "score6": score6,
            "reason": why
        }
    except Exception as e:
        return {"action":"WAIT","score16":0,"score6":0,"reason":f"indicators_ext error: {e}"}
