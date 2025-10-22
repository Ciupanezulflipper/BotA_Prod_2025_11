# -------- providers.py --------
# Robust OHLCV + price fetchers with graceful fallbacks.
# Order: TwelveData -> AlphaVantage -> Yahoo Finance.

from __future__ import annotations

import os
import logging
import requests
from datetime import datetime, timezone
from typing import Optional, Tuple

import pandas as pd
import yfinance as yf

log = logging.getLogger("providers")

# ------------ config ------------
SESSION = requests.Session()
DEFAULT_TIMEOUT = float(os.getenv("HTTP_TIMEOUT", "10"))

TD_KEY = os.getenv("TWELVEDATA_KEY", "").strip()
AV_KEY = os.getenv("ALPHAVANTAGE_KEY", os.getenv("AV_KEY", "")).strip()

_TF_MAP_TD = {"1min": "1min","5min": "5min","15min": "15min","30min": "30min","1h": "1h"}
_TF_MAP_YF = {"1min": "1m","5min": "5m","15min": "15m","30min": "30m","1h": "1h"}
_AV_TF = {"1min": "1min","5min": "5min","15min": "15min","30min": "30min"}

# ------------ helpers ------------
def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")

def _safe_float(x) -> Optional[float]:
    try: return float(x)
    except: return None

def _pair(sym: str) -> Tuple[str,str]:
    s = sym.upper().strip()
    if len(s) >= 6: return s[:3], s[3:]
    raise ValueError(f"bad symbol {sym}")

def _ensure_ohlcv(df: pd.DataFrame) -> Optional[pd.DataFrame]:
    if df is None or df.empty: return None
    rename = {}
    cols = [c.lower() for c in df.columns]
    for k in ["open","high","low","close","volume"]:
        if k in cols: rename[df.columns[cols.index(k)]] = k.capitalize()
    df = df.rename(columns=rename)
    keep = [c for c in ["Open","High","Low","Close","Volume"] if c in df.columns]
    df = df[keep].dropna().sort_index()
    return df if not df.empty else None

# ------------ TwelveData ------------
def _td_candles(symbol, tf, limit=200):
    if not TD_KEY: return None
    tf_td = _TF_MAP_TD.get(tf); 
    if not tf_td: return None
    base, quote = _pair(symbol)
    try:
        r = SESSION.get("https://api.twelvedata.com/time_series",
                        params={"symbol":f"{base}/{quote}","interval":tf_td,
                                "outputsize":str(limit),"timezone":"UTC","apikey":TD_KEY},
                        timeout=DEFAULT_TIMEOUT)
        j = r.json()
        if "values" in j:
            rows=[]
            for v in j["values"]:
                ts=pd.to_datetime(v.get("datetime"),utc=True)
                rows.append({"Date":ts,"Open":_safe_float(v.get("open")),
                             "High":_safe_float(v.get("high")),"Low":_safe_float(v.get("low")),
                             "Close":_safe_float(v.get("close")),"Volume":_safe_float(v.get("volume"))})
            return _ensure_ohlcv(pd.DataFrame(rows).set_index("Date"))
    except Exception as e: log.debug("twelvedata err %s %s: %s",symbol,tf,e)
    return None

def _td_price(symbol):
    if not TD_KEY: return None
    base, quote = _pair(symbol)
    try:
        r=SESSION.get("https://api.twelvedata.com/price",
                      params={"symbol":f"{base}/{quote}","apikey":TD_KEY},
                      timeout=DEFAULT_TIMEOUT)
        j=r.json()
        return _safe_float(j.get("price")) if "price" in j else None
    except: return None

# ------------ AlphaVantage ------------
def _av_candles(symbol, tf, limit=200):
    if not AV_KEY: return None
    tf_av=_AV_TF.get(tf); 
    if not tf_av: return None
    base, quote=_pair(symbol)
    try:
        r=SESSION.get("https://www.alphavantage.co/query",
                      params={"function":"FX_INTRADAY","from_symbol":base,
                              "to_symbol":quote,"interval":tf_av,
                              "outputsize":"full","apikey":AV_KEY},
                      timeout=DEFAULT_TIMEOUT)
        j=r.json(); key=next((k for k in j if k.startswith("Time Series")),None)
        if key:
            recs=[]
            for t,ohlc in j[key].items():
                ts=pd.to_datetime(t,utc=True)
                recs.append({"Date":ts,"Open":_safe_float(ohlc.get("1. open")),
                             "High":_safe_float(ohlc.get("2. high")),"Low":_safe_float(ohlc.get("3. low")),
                             "Close":_safe_float(ohlc.get("4. close"))})
            return _ensure_ohlcv(pd.DataFrame(recs).set_index("Date").tail(limit))
    except Exception as e: log.debug("av err %s %s: %s",symbol,tf,e)
    return None

def _av_price(symbol):
    if not AV_KEY: return None
    base, quote=_pair(symbol)
    try:
        r=SESSION.get("https://www.alphavantage.co/query",
                      params={"function":"CURRENCY_EXCHANGE_RATE",
                              "from_currency":base,"to_currency":quote,
                              "apikey":AV_KEY},timeout=DEFAULT_TIMEOUT)
        j=r.json(); k="Realtime Currency Exchange Rate"
        if k in j: return _safe_float(j[k].get("5. Exchange Rate"))
    except: return None
    return None

# ------------ Yahoo Finance ------------
def _yf_symbol(symbol:str)->str:
    return symbol.upper()+"=X" if not symbol.endswith("=X") else symbol

def _yf_candles(symbol, tf, limit=200):
    yf_tf=_TF_MAP_YF.get(tf); 
    if not yf_tf: return None
    try:
        data=yf.download(_yf_symbol(symbol),period="7d",interval=yf_tf,progress=False)
        return _ensure_ohlcv(data.tail(limit))
    except: return None

def _yf_price(symbol):
    try:
        data=yf.download(_yf_symbol(symbol),period="1d",interval="1m",progress=False)
        return _safe_float(data["Close"].dropna().iloc[-1]) if not data.empty else None
    except: return None

# ------------ public API ------------
def ping_any():
    if TD_KEY:
        try:
            r=SESSION.get("https://api.twelvedata.com/price",
                          params={"symbol":"EUR/USD","apikey":TD_KEY},timeout=DEFAULT_TIMEOUT)
            if r.status_code==200 and "price" in r.text: return "twelvedata",True,200,"ok"
        except Exception as e: return "twelvedata",False,500,str(e)
    if AV_KEY:
        try:
            r=SESSION.get("https://www.alphavantage.co/query",
                          params={"function":"CURRENCY_EXCHANGE_RATE","from_currency":"EUR",
                                  "to_currency":"USD","apikey":AV_KEY},timeout=DEFAULT_TIMEOUT)
            if "Realtime Currency Exchange Rate" in r.text: return "alphavantage",True,200,"ok"
        except Exception as e: return "alphavantage",False,500,str(e)
    try:
        df=yf.download("EURUSD=X",period="1d",interval="1m",progress=False)
        ok=not df.empty; return "yfinance",ok,200 if ok else 500,"ok" if ok else "empty"
    except Exception as e: return "yfinance",False,500,str(e)

def fetch_candles(symbol, tf="5min", limit=200):
    for fn in (_td_candles,_av_candles,_yf_candles):
        df=fn(symbol,tf,limit)
        if df is not None and not df.empty: return df
    log.warning("fetch_candles failed for %s %s",symbol,tf); return None

def fetch_ohlcv_safe(symbol, tf="5min", limit=200):
    return fetch_candles(symbol,tf,limit)

def fetch_price(symbol):
    for fn in (_td_price,_av_price,_yf_price):
        p=fn(symbol)
        if p is not None: return p
    log.warning("fetch_price failed for %s",symbol); return None
