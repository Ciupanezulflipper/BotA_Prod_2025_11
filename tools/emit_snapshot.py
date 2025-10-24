#!/usr/bin/env python3
# Bot A — Phase 2 (v3): resilient snapshot emitter (dual-symbol TwelveData, Yahoo 429 mitigation, flex RSI)

from __future__ import annotations
import os, sys, json, math, datetime, time
from typing import Dict, List, Optional, Tuple

# ---------------- HTTP ----------------
def _http_get(url: str, params: Dict[str, str], timeout: int = 15) -> Tuple[int, Dict]:
    try:
        import requests  # type: ignore
        r = requests.get(url, params=params, timeout=timeout, headers={"User-Agent":"BotA/emit_snapshot"})
        code = r.status_code
        try: return code, r.json()
        except Exception: return code, {"_json_error": True, "_raw": r.text[:2000]}
    except Exception:
        try:
            import urllib.parse, urllib.request
            full = url + "?" + urllib.parse.urlencode(params)
            with urllib.request.urlopen(full, timeout=timeout) as resp:
                code = getattr(resp, "status", 200); raw = resp.read()
            try: return code, json.loads(raw.decode("utf-8","replace"))
            except Exception:
                try: txt = raw[:2000].decode("utf-8","replace")
                except Exception: txt = str(raw)[:2000]
                return code, {"_json_error": True, "_raw": txt}
        except Exception as e:
            return 0, {"_transport_error": str(e)}

# --------------- Indicators ---------------
def ema(values: List[float], n: int) -> List[Optional[float]]:
    if n <= 0: return [None]*len(values)
    k = 2.0/(n+1.0); e=None; out=[]
    for v in values:
        e = v if e is None else (v-e)*k+e
        out.append(e)
    return out

def rsi_flex(values: List[float], preferred_n: int = 14) -> List[Optional[float]]:
    L = len(values)
    if L < 3: return [None]*L
    n = min(preferred_n, L-1)
    gains=[max(values[i]-values[i-1],0.0) for i in range(1,L)]
    losses=[max(values[i-1]-values[i],0.0) for i in range(1,L)]
    avg_g=sum(gains[:n])/n; avg_l=sum(losses[:n])/n
    out: List[Optional[float]] = [None]*n
    rs=(avg_g/avg_l) if avg_l!=0 else math.inf
    out.append(100.0-100.0/(1.0+rs))
    for idx in range(n+1, L):
        g=gains[idx-1]; l=losses[idx-1]
        avg_g=(avg_g*(n-1)+g)/n; avg_l=(avg_l*(n-1)+l)/n
        rs=(avg_g/avg_l) if avg_l!=0 else math.inf
        out.append(100.0-100.0/(1.0+rs))
    return out

def macd_hist(vals: List[float], f:int=12, s:int=26, sig:int=9)->List[Optional[float]]:
    e1=ema(vals,f); e2=ema(vals,s)
    macd=[(a-b) if (a is not None and b is not None) else None for a,b in zip(e1,e2)]
    sigl=ema([m if m is not None else 0.0 for m in macd],sig)
    out=[]
    for m,sg in zip(macd,sigl):
        out.append(None if (m is None or sg is None) else (m-sg))
    return out

# --------------- Time utils ---------------
def _parse_dt_to_utc(dt_str:str)->datetime.datetime:
    try:
        dt=datetime.datetime.fromisoformat(dt_str.replace("Z","+00:00"))
        if dt.tzinfo: dt=dt.astimezone(datetime.timezone.utc).replace(tzinfo=None)
        return dt
    except Exception: pass
    try: return datetime.datetime.strptime(dt_str,"%Y-%m-%d %H:%M:%S")
    except Exception: return datetime.datetime.utcnow()

def _from_ts_utc(ts:int)->datetime.datetime:
    return datetime.datetime.fromtimestamp(int(ts), datetime.timezone.utc).replace(tzinfo=None)

def _fmt_utc(dt:datetime.datetime)->str:
    return dt.strftime("%Y-%m-%d %H:%M:%SZ")

# --------------- Providers ----------------
def _td_symbols(sym:str)->List[str]:
    s=sym.strip().upper()
    cand=[s]
    if len(s)==6 and s.isalpha(): cand.append(s[:3]+"/"+s[3:])
    if "/" in s: cand.append(s.replace("/",""))
    if s in ("XAUUSD","XAGUSD"): cand.append(s[:3]+"/"+s[3:])
    # dedup
    out=[]; seen=set()
    for x in cand:
        if x not in seen: out.append(x); seen.add(x)
    return out

def _fetch_twelvedata_once(symbol:str, interval:str, apikey:str)->Tuple[Optional[List[Tuple[datetime.datetime,float]]], Optional[str], Optional[Dict]]:
    url="https://api.twelvedata.com/time_series"
    params={"symbol":symbol,"interval":interval,"outputsize":"160","timezone":"UTC","format":"JSON","apikey":apikey}
    code,j=_http_get(url,params,timeout=15); raw=j
    if code!=200: return None,f"TwelveData HTTP {code}",raw
    if not isinstance(j,dict): return None,"TwelveData non-dict JSON",raw
    if j.get("status")=="error": return None,f"TwelveData error: {j.get('message','unknown')}",raw
    values=j.get("values")
    if not isinstance(values,list): return None,"TwelveData missing 'values'",raw
    out=[]
    for item in reversed(values):
        try:
            dt=_parse_dt_to_utc(item["datetime"]); close=float(item["close"])
            out.append((dt,close))
        except Exception: continue
    if not out: return None,"TwelveData no usable datapoints",raw
    return out,None,raw

def fetch_twelvedata_multi(raw_sym:str, interval:str, apikey:str)->Tuple[Optional[List[Tuple[datetime.datetime,float]]], Optional[str]]:
    errs=[]
    for s in _td_symbols(raw_sym):
        series, err, _raw = _fetch_twelvedata_once(s, interval, apikey)
        if series is not None:
            return series, None
        errs.append(err or "unknown"); time.sleep(0.6)
    return None, "; ".join([e for e in errs if e])

def _yahoo_symbol(pair:str)->Optional[str]:
    m={"EURUSD":"EURUSD=X","GBPUSD":"GBPUSD=X","USDJPY":"USDJPY=X","USDCAD":"USDCAD=X","AUDUSD":"AUDUSD=X","NZDUSD":"NZDUSD=X","XAUUSD":"XAUUSD=X"}
    return m.get(pair.upper())

def _fetch_yahoo(pair:str, rng:str, interval:str)->Tuple[Optional[List[Tuple[datetime.datetime,float]]], Optional[str], Optional[int]]:
    ys=_yahoo_symbol(pair)
    if not ys: return None,"Yahoo mapping unavailable",None
    url=f"https://query1.finance.yahoo.com/v8/finance/chart/{ys}"
    params={"range":rng,"interval":interval}
    code,j=_http_get(url,params,timeout=15)
    if code!=200: return None,f"Yahoo HTTP {code}",code
    try:
        res=j["chart"]["result"][0]; ts=res["timestamp"]; closes=res["indicators"]["quote"][0]["close"]
    except Exception: return None,"Yahoo malformed result",code
    out=[]
    for t,c in zip(ts,closes):
        if c is None: continue
        out.append((_from_ts_utc(t), float(c)))
    if not out: return None,"Yahoo no datapoints",code
    return out,None,code

def fetch_yahoo_1h(pair:str):
    s,err,code=_fetch_yahoo(pair,"5d","60m")
    if s: return s,None
    if code==429:
        time.sleep(1.0)
        s2,err2,code2=_fetch_yahoo(pair,"1mo","60m")
        if s2: return s2,None
        if code2==429:
            time.sleep(1.0)
            s3,err3,_=_fetch_yahoo(pair,"3mo","60m")
            if s3: return s3,None
            return None, err3 or err2 or err
    return s,err

def fetch_yahoo_1d(pair:str):
    s,err,code=_fetch_yahoo(pair,"3mo","1d")
    if s: return s,None
    if code==429:
        time.sleep(1.0)
        s2,err2,_=_fetch_yahoo(pair,"6mo","1d")
        if s2: return s2,None
        return None, err2 or err
    return s,err

# --------------- Resampling ----------------
def resample_4h_from_1h(series: List[Tuple[datetime.datetime,float]])->List[Tuple[datetime.datetime,float]]:
    if not series: return []
    buckets:Dict[int,Tuple[datetime.datetime,float]]={}
    for dt,close in series:
        bh=dt.hour-(dt.hour%4); bdt=dt.replace(hour=bh,minute=0,second=0,microsecond=0)
        key=int(bdt.timestamp()); buckets[key]=(bdt,close)
    return [buckets[k] for k in sorted(buckets.keys())]

# --------------- Formatting ----------------
def _compute_line(tf_label:str, series:List[Tuple[datetime.datetime,float]])->Optional[str]:
    if not series or len(series)<3: return None
    times=[dt for dt,_ in series]; close=[c for _,c in series]
    e9=ema(close,9); e21=ema(close,21); r=rsi_flex(close,14); mh=macd_hist(close)
    i=-1; c=close[i]; e9v=e9[i]; e21v=e21[i]; rv=r[i]; mhv=mh[i]
    if rv is None: rv=50.0
    if mhv is None: mhv=0.0
    if e9v is None: e9v=c
    if e21v is None: e21v=c
    vote=(1 if e9v>e21v else -1 if e9v<e21v else 0) + (1 if rv>55 else -1 if rv<45 else 0) + (1 if mhv>0 else -1 if mhv<0 else 0)
    tstr=_fmt_utc(times[i])
    return (f"{tf_label}: t={tstr} close={c:.5f} EMA9={e9v:.5f} EMA21={e21v:.5f} "
            f"RSI14={rv:.2f} MACD_hist={mhv:.5f} vote={'+' if vote>0 else ''}{vote}")

def _print_error(tf_label:str, msg:str):
    print(f"{tf_label}: provider_error={msg} vote=0")

# --------------- Main ----------------
def main()->None:
    if len(sys.argv)<2:
        print("usage: emit_snapshot.py EURUSD [--debug]", file=sys.stderr); sys.exit(2)
    raw_sym=sys.argv[1].upper(); debug=("--debug" in sys.argv)
    print(f"=== {raw_sym} snapshot ===")
    key=os.getenv("TWELVEDATA_API_KEY","").strip()

    # H1
    h1_series=None; h1_err=None
    if key: h1_series,h1_err=fetch_twelvedata_multi(raw_sym,"1h",key)
    if h1_series is None:
        h1_series,yh1_err=fetch_yahoo_1h(raw_sym)
        if h1_series is None:
            _print_error("H1", (h1_err or "")+("; " if h1_err else "")+(yh1_err or "unknown"))
        else:
            line=_compute_line("H1",h1_series); print(line if line else "H1: provider_error=insufficient_data vote=0")
    else:
        line=_compute_line("H1",h1_series); print(line if line else "H1: provider_error=insufficient_data vote=0")

    # H4
    h4_series=None; h4_err=None
    if key: h4_series,h4_err=fetch_twelvedata_multi(raw_sym,"4h",key)
    if h4_series is None:
        base=h1_series or fetch_yahoo_1h(raw_sym)[0]
        if base is None:
            _print_error("H4", h4_err or "no_h1_available_for_resample")
        else:
            rs=resample_4h_from_1h(base); line=_compute_line("H4",rs)
            print(line if line else "H4: provider_error=insufficient_data vote=0")
    else:
        line=_compute_line("H4",h4_series); print(line if line else "H4: provider_error=insufficient_data vote=0")

    # D1
    d1_series=None; d1_err=None
    if key: d1_series,d1_err=fetch_twelvedata_multi(raw_sym,"1day",key)
    if d1_series is None:
        d1_series,yd1_err=fetch_yahoo_1d(raw_sym)
        if d1_series is None:
            _print_error("D1", (d1_err or "")+("; " if d1_err else "")+(yd1_err or "unknown"))
        else:
            line=_compute_line("D1",d1_series); print(line if line else "D1: provider_error=insufficient_data vote=0")
    else:
        line=_compute_line("D1",d1_series); print(line if line else "D1: provider_error=insufficient_data vote=0")

if __name__=="__main__": main()
