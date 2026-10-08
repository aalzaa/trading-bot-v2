"""Engulfing-only ATR/RR/RSI research for Trend + Pullback.

Research branch only. Not MT5 LIVE code.

Rules:
- EMA20 > EMA50: long bias; EMA20 < EMA50: short bias.
- Pullback into EMA20-EMA50 zone over prior closed M5 bars.
- ENTRY ONLY on bullish/bearish engulfing confirmation.
- Rejection patterns are excluded.
- Engulfings reacting on EMA50 are excluded.
- Directional RSI entry filter: LONG RSI 47-58 inclusive; SHORT RSI 42-51 inclusive.
- Entry price is confirmation-candle close.
- Entry timestamp/hour/session, LONG/SHORT, EMA distances and RSI are recorded.
- Optional historical news CSV is tagged when present.
- Only the 10 explicitly selected ATR/RR combinations are evaluated.
"""

from pathlib import Path
import json
import math
import hashlib
import numpy as np
import pandas as pd

try:
    from numba import njit
    NUMBA_AVAILABLE = True
except ImportError:
    NUMBA_AVAILABLE = False
    njit = None

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "data" / "raw" / "XAUUSD_m1_20211001_20261001.csv"
NEWS = ROOT / "data" / "news" / "xauusd_news.csv"
RESULTS = ROOT / "results" / "engulfing_atr_rsi"
GRID_CACHE = RESULTS / "engulfing_exit_grid_cache.npz"
CACHE_VERSION = "exit-grid-v5-rsi-filter-top10"
RESULTS.mkdir(parents=True, exist_ok=True)

START = pd.Timestamp("2023-09-30 00:00:00")
END = pd.Timestamp("2026-09-30 23:59:59")

# ONLY the 10 combinations selected for the RSI-filter study.
SELECTED_ATR_RR = [
    (4.00, 3.00),
    (3.50, 2.50),
    (4.00, 2.50),
    (4.00, 2.00),
    (5.00, 1.50),
    (5.00, 1.25),
    (3.50, 3.00),
    (5.00, 2.50),
    (5.00, 2.00),
    (3.50, 2.00),
]
SL_GRID = sorted({sl for sl, _ in SELECTED_ATR_RR})
RR_GRID = sorted({rr for _, rr in SELECTED_ATR_RR})
SELECTED_COMBOS = set(SELECTED_ATR_RR)
SELECTED_SL = np.asarray([sl for sl, _ in SELECTED_ATR_RR], dtype=np.float64)
SELECTED_RR = np.asarray([rr for _, rr in SELECTED_ATR_RR], dtype=np.float64)

RSI_PERIOD = 14
PULLBACK_LOOKBACK = 3

SESSION_MAP = {
    "ASIA": range(0, 8),
    "LONDON": range(8, 13),
    "NEW_YORK": range(13, 18),
    "NY_LATE": range(18, 22),
    "OFF": range(22, 24),
}

def session_for_hour(hour):
    for name, hours in SESSION_MAP.items():
        if hour in hours:
            return name
    return "UNKNOWN"

def load_m1():
    df = pd.read_csv(INPUT, usecols=["Date","Open","High","Low","Close","Volume"],
        dtype={"Open":"float64","High":"float64","Low":"float64","Close":"float64","Volume":"float64"},
        parse_dates=["Date"]).set_index("Date")
    if not df.index.is_monotonic_increasing:
        df = df.sort_index(kind="stable")
    if df.index.has_duplicates:
        df = df[~df.index.duplicated(keep="first")]
    return df.loc[START:END].dropna(subset=["Open","High","Low","Close"])

def make_m5(m1):
    m5 = m1.resample("5min", label="left", closed="left").agg(
        Open=("Open","first"), High=("High","max"), Low=("Low","min"),
        Close=("Close","last"), Volume=("Volume","sum"), M1Count=("Close","count"))
    m5 = m5.dropna(subset=["Open","High","Low","Close"])
    tr = pd.concat([m5["High"]-m5["Low"],
                    (m5["High"]-m5["Close"].shift()).abs(),
                    (m5["Low"]-m5["Close"].shift()).abs()], axis=1).max(axis=1)
    m5["ATR"] = tr.rolling(14).mean()
    return m5

def rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, float("nan"))
    out = 100 - (100 / (1 + rs))
    out[(avg_loss == 0) & (avg_gain > 0)] = 100.0
    out[(avg_gain == 0) & (avg_loss > 0)] = 0.0
    return out

def build_entries(m5):
    m5 = m5.copy()
    close = m5["Close"]
    m5["EMA20"] = close.ewm(span=20, adjust=False).mean()
    m5["EMA50"] = close.ewm(span=50, adjust=False).mean()
    m5["RSI14"] = rsi(close, RSI_PERIOD)

    ema20 = m5["EMA20"].to_numpy(dtype=np.float64)
    ema50 = m5["EMA50"].to_numpy(dtype=np.float64)
    high = m5["High"].to_numpy(dtype=np.float64)
    low = m5["Low"].to_numpy(dtype=np.float64)
    op = m5["Open"].to_numpy(dtype=np.float64)
    cl = close.to_numpy(dtype=np.float64)
    atr = m5["ATR"].to_numpy(dtype=np.float64)

    long_bias, short_bias = ema20 > ema50, ema20 < ema50
    zone_lo, zone_hi = np.minimum(ema20,ema50), np.maximum(ema20,ema50)
    touches = (high >= zone_lo) & (low <= zone_hi)
    pull_long_bar = touches & (cl >= zone_lo)
    pull_short_bar = touches & (cl <= zone_hi)
    prev_long = pd.Series(pull_long_bar,index=m5.index).shift(1).rolling(PULLBACK_LOOKBACK,min_periods=1).max().to_numpy(dtype=bool)
    prev_short = pd.Series(pull_short_bar,index=m5.index).shift(1).rolling(PULLBACK_LOOKBACK,min_periods=1).max().to_numpy(dtype=bool)

    prev_op, prev_cl = np.roll(op,1), np.roll(cl,1)
    prev_op[0], prev_cl[0] = np.nan, np.nan
    bullish = (cl>op)&(prev_cl<prev_op)&(op<=prev_cl)&(cl>=prev_op)
    bearish = (cl<op)&(prev_cl>prev_op)&(op>=prev_cl)&(cl<=prev_op)

    valid = (np.arange(len(m5)) >= max(50,PULLBACK_LOOKBACK+3)) & np.isfinite(atr) & (atr>0)
    long_signal = valid & long_bias & prev_long & bullish
    short_signal = valid & short_bias & prev_short & bearish

    touches_ema50 = (low <= ema50) & (high >= ema50)
    long_signal &= ~touches_ema50
    short_signal &= ~touches_ema50

    abs_d20_atr = np.abs(cl-ema20)/atr
    abs_d50_atr = np.abs(cl-ema50)/atr
    proximity = (abs_d20_atr <= 0.75) & (abs_d50_atr <= 1.20)
    long_signal &= proximity
    short_signal &= proximity

    rsi_values_all = m5["RSI14"].to_numpy(dtype=np.float64)
    long_signal &= (rsi_values_all >= 47.0) & (rsi_values_all <= 58.0)
    short_signal &= (rsi_values_all >= 42.0) & (rsi_values_all <= 51.0)

    idx = np.flatnonzero(long_signal | short_signal)
    columns = ["entry_time","side","entry","atr","ema20","ema50","distance_ema20","distance_ema50",
               "abs_distance_ema20","abs_distance_ema50","distance_ema20_atr","distance_ema50_atr",
               "abs_distance_ema20_atr","abs_distance_ema50_atr","rsi14","hour","minute","session",
               "pattern","ema50_reaction"]
    if len(idx)==0:
        return pd.DataFrame(columns=columns)

    is_long = long_signal[idx]
    times = m5.index.to_numpy()[idx]
    entries, atrs = cl[idx], atr[idx]
    e20,e50 = ema20[idx],ema50[idx]
    rsi_values = rsi_values_all[idx]
    dt = pd.DatetimeIndex(times)
    hours,minutes = dt.hour.to_numpy(dtype=np.int16),dt.minute.to_numpy(dtype=np.int16)

    return pd.DataFrame({
        "entry_time":times,"side":np.where(is_long,"LONG","SHORT"),"entry":entries,"atr":atrs,
        "ema20":e20,"ema50":e50,"distance_ema20":entries-e20,"distance_ema50":entries-e50,
        "abs_distance_ema20":np.abs(entries-e20),"abs_distance_ema50":np.abs(entries-e50),
        "distance_ema20_atr":(entries-e20)/atrs,"distance_ema50_atr":(entries-e50)/atrs,
        "abs_distance_ema20_atr":np.abs(entries-e20)/atrs,"abs_distance_ema50_atr":np.abs(entries-e50)/atrs,
        "rsi14":rsi_values,"hour":hours,"minute":minutes,
        "session":np.array([session_for_hour(int(h)) for h in hours],dtype=object),
        "pattern":np.where(is_long,"BULLISH_ENGULFING","BEARISH_ENGULFING"),
        "ema50_reaction":np.zeros(len(idx),dtype=bool)})

if NUMBA_AVAILABLE:
    @njit(cache=True)
    def _exit_grid_kernel(entry_positions,sides,prices,atrs,highs,lows,sl_grid,rr_grid):
        n=len(entry_positions); n_combo=len(sl_grid)
        exit_indices=np.full((n,n_combo),-1,dtype=np.int64)
        result_r=np.zeros((n,n_combo),dtype=np.float64)
        reason=np.zeros((n,n_combo),dtype=np.int8)
        for i in range(n):
            pos=entry_positions[i]
            if pos>=len(highs): continue
            unresolved=np.ones(n_combo,dtype=np.uint8); remaining=n_combo
            side= sides[i]; price=prices[i]; atr=atrs[i]
            if not np.isfinite(atr) or atr<=0: continue
            for j in range(pos,len(highs)):
                if remaining==0: break
                hi,lo=highs[j],lows[j]
                for c in range(n_combo):
                    if unresolved[c]==0: continue
                    sl_value=sl_grid[c]; rr_value=rr_grid[c]; risk=atr*sl_value
                    if side==1:
                        sl=price-risk; tp=price+risk*rr_value
                        hit_sl,hit_tp=lo<=sl,hi>=tp
                    else:
                        sl=price+risk; tp=price-risk*rr_value
                        hit_sl,hit_tp=hi>=sl,lo<=tp
                    if hit_sl or hit_tp:
                        unresolved[c]=0; remaining-=1; exit_indices[i,c]=j
                        if hit_sl: result_r[i,c]=-1.0; reason[i,c]=1
                        else: result_r[i,c]=rr_value; reason[i,c]=2
        return exit_indices,result_r,reason

def _precompute_exit_grid_python(m1, entries):
    times=m1.index.to_numpy(); highs=m1["High"].to_numpy(dtype=float); lows=m1["Low"].to_numpy(dtype=float)
    combos=SELECTED_ATR_RR; results={combo:[] for combo in combos}
    for _,e in entries.iterrows():
        pos=m1.index.searchsorted(e.entry_time,side="right")
        if pos>=len(m1): continue
        side=e.side; price=float(e.entry); atr=float(e.atr)
        if not math.isfinite(atr) or atr<=0: continue
        unresolved=set(combos)
        for j in range(pos,len(m1)):
            if not unresolved: break
            hi,lo=highs[j],lows[j]; hit_now=[]
            for sl,rr in unresolved:
                risk=atr*sl
                hit_sl=(lo<=price-risk) if side=="LONG" else (hi>=price+risk)
                hit_tp=(hi>=price+risk*rr) if side=="LONG" else (lo<=price-risk*rr)
                if hit_sl or hit_tp:
                    results[(sl,rr)].append({"entry_time":e.entry_time,"side":side,"entry":price,"atr":atr,
                        "exit_time":times[j],"result_r":-1.0 if hit_sl else rr,
                        "exit_reason":"SL" if hit_sl else "TP",
                        "exit_price":(price-risk if side=="LONG" else price+risk) if hit_sl else
                                     (price+risk*rr if side=="LONG" else price-risk*rr),
                        "duration_m1":int((times[j]-e.entry_time)/pd.Timedelta(minutes=1))})
                    hit_now.append((sl,rr))
            for combo in hit_now: unresolved.discard(combo)
    return results

def precompute_exit_grid(m1,entries):
    if entries.empty: return {combo:[] for combo in SELECTED_ATR_RR}
    times=m1.index.to_numpy(); highs=m1["High"].to_numpy(dtype=np.float64); lows=m1["Low"].to_numpy(dtype=np.float64)
    entry_times=entries["entry_time"].to_numpy(dtype="datetime64[ns]")
    entry_positions=np.searchsorted(times,entry_times,side="right").astype(np.int64)
    sides=np.array([1 if s=="LONG" else -1 for s in entries["side"]],dtype=np.int8)
    prices=entries["entry"].to_numpy(dtype=np.float64); atrs=entries["atr"].to_numpy(dtype=np.float64)
    sl_arr=SELECTED_SL; rr_arr=SELECTED_RR
    h=hashlib.sha256()
    for x in [CACHE_VERSION,str(INPUT.stat().st_size),str(INPUT.stat().st_mtime_ns),str(START.value),str(END.value)]:
        h.update(x.encode())
    h.update(sl_arr.tobytes()); h.update(rr_arr.tobytes())
    h.update(np.asarray(SELECTED_ATR_RR,dtype=np.float64).tobytes())
    h.update(entries["entry_time"].to_numpy(dtype="datetime64[ns]").tobytes())
    h.update(entries["side"].map({"LONG":1,"SHORT":-1}).to_numpy(dtype=np.int8).tobytes())
    h.update(entries["entry"].to_numpy(dtype=np.float64).tobytes()); h.update(entries["atr"].to_numpy(dtype=np.float64).tobytes())
    cache_key=h.hexdigest()
    exit_idx=result_values=reasons=None
    if GRID_CACHE.exists():
        try:
            cached=np.load(GRID_CACHE,allow_pickle=False)
            if str(cached["cache_key"])==cache_key:
                exit_idx,result_values,reasons=cached["exit_idx"],cached["result_values"],cached["reasons"]
        except Exception: pass
    if exit_idx is None:
        exit_idx,result_values,reasons=_exit_grid_kernel(entry_positions,sides,prices,atrs,highs,lows,sl_arr,rr_arr) if NUMBA_AVAILABLE else (None,None,None)
        if NUMBA_AVAILABLE:
            tmp=GRID_CACHE.with_name(GRID_CACHE.name+".tmp.npz")
            np.savez(tmp,cache_key=np.array(cache_key),exit_idx=exit_idx,result_values=result_values,reasons=reasons); tmp.replace(GRID_CACHE)
        else:
            return _precompute_exit_grid_python(m1,entries)
    results={combo:[] for combo in SELECTED_ATR_RR}
    entry_times=entries["entry_time"].to_numpy(); side_values=entries["side"].to_numpy()
    entry_values=entries["entry"].to_numpy(dtype=np.float64); atr_values=entries["atr"].to_numpy(dtype=np.float64)
    for sl,rr in SELECTED_ATR_RR:
        c=SELECTED_ATR_RR.index((sl,rr))
        valid=exit_idx[:,c]>=0
        if not np.any(valid): continue
        ii=np.flatnonzero(valid); jj=exit_idx[ii,c]; hit_sl=reasons[ii,c]==1
        exit_prices=np.where(hit_sl,
            np.where(side_values[ii]=="LONG",entry_values[ii]-atr_values[ii]*sl,entry_values[ii]+atr_values[ii]*sl),
            np.where(side_values[ii]=="LONG",entry_values[ii]+atr_values[ii]*sl*rr,entry_values[ii]-atr_values[ii]*sl*rr))
        for k,i in enumerate(ii):
            results[(sl,rr)].append({"entry_time":entry_times[i],"side":side_values[i],"entry":float(entry_values[i]),
                "atr":float(atr_values[i]),"exit_time":times[jj[k]],"result_r":float(result_values[i,c]),
                "exit_reason":"SL" if hit_sl[k] else "TP","exit_price":float(exit_prices[k]),
                "duration_m1":int((times[jj[k]]-entry_times[i])/np.timedelta64(1,"m"))})
    return results

def baseline_trades_from_grid(entries,grid_results):
    # The old 1 ATR / 1.5 RR baseline is not part of this 10-combination study.
    return pd.DataFrame()

def batch_mfe_mae(m1,trades):
    if trades.empty: return pd.DataFrame()
    times=m1.index.to_numpy(); highs=m1["High"].to_numpy(dtype=np.float64); lows=m1["Low"].to_numpy(dtype=np.float64)
    entry_times=trades["entry_time"].to_numpy(dtype="datetime64[ns]"); exit_times=trades["exit_time"].to_numpy(dtype="datetime64[ns]")
    entry_pos=np.searchsorted(times,entry_times,side="right").astype(np.int64)
    exit_pos=(np.searchsorted(times,exit_times,side="right")-1).astype(np.int64)
    sides=trades["side"].map({"LONG":1,"SHORT":-1}).to_numpy(dtype=np.int8); prices=trades["entry"].to_numpy(dtype=np.float64)
    atrs=trades["atr"].to_numpy(dtype=np.float64)
    if NUMBA_AVAILABLE:
        mfe,mae,mfe_idx,mae_idx=_mfe_mae_kernel(entry_pos,exit_pos,sides,prices,highs,lows)
        safe_mfe_idx=np.maximum(mfe_idx,0); safe_mae_idx=np.maximum(mae_idx,0)
        time_to_mfe=(times[safe_mfe_idx]-entry_times)/np.timedelta64(1,"m")
        time_to_mae=(times[safe_mae_idx]-entry_times)/np.timedelta64(1,"m")
        time_to_mfe[mfe_idx<0]=np.nan; time_to_mae[mae_idx<0]=np.nan
    else:
        return pd.DataFrame()
    return pd.DataFrame({"entry_time":trades["entry_time"].to_numpy(),"exit_time":trades["exit_time"].to_numpy(),
        "side":trades["side"].to_numpy(),"entry":prices,"atr":atrs,"mfe_price":np.maximum(mfe,0.0),
        "mae_price":np.maximum(mae,0.0),"mfe_r_at_1atr":np.divide(np.maximum(mfe,0.0),atrs,out=np.full_like(mfe,np.nan),where=atrs!=0),
        "mae_r_at_1atr":np.divide(np.maximum(mae,0.0),atrs,out=np.full_like(mae,np.nan),where=atrs!=0),
        "time_to_mfe_m1":time_to_mfe,"time_to_mae_m1":time_to_mae,"result_r":trades["result_r"].to_numpy(dtype=np.float64)})

if NUMBA_AVAILABLE:
    @njit(cache=True)
    def _mfe_mae_kernel(entry_pos,exit_pos,sides,prices,highs,lows):
        n=len(entry_pos); mfe=np.zeros(n); mae=np.zeros(n); mfe_idx=np.full(n,-1,dtype=np.int64); mae_idx=np.full(n,-1,dtype=np.int64)
        for i in range(n):
            start,end=entry_pos[i],exit_pos[i]
            if start>=len(highs) or end<start: continue
            p=prices[i]; side=sides[i]; best_f=0.0; best_a=0.0; bf=-1; ba=-1
            for j in range(start,end+1):
                fav=highs[j]-p if side==1 else p-lows[j]; adv=p-lows[j] if side==1 else highs[j]-p
                if fav>best_f: best_f,bf=fav,j
                if adv>best_a: best_a,ba=adv,j
            mfe[i],mae[i],mfe_idx[i],mae_idx[i]=best_f,best_a,bf,ba
        return mfe,mae,mfe_idx,mae_idx

def load_news():
    if not NEWS.exists(): return None
    n=pd.read_csv(NEWS)
    time_col=next((c for c in ["datetime","DateTime","timestamp","time","Date"] if c in n.columns),None)
    if time_col is None: return None
    n["news_time"]=pd.to_datetime(n[time_col],errors="coerce")
    return n.dropna(subset=["news_time"]).sort_values("news_time")

def tag_news(entries,news):
    out=entries.copy()
    cols=["nearest_news_time","nearest_news_event","nearest_news_impact","nearest_news_minutes",
          "news_within_15m","news_within_30m","news_within_60m","news_within_120m",
          "high_impact_within_15m","high_impact_within_30m","high_impact_within_60m","high_impact_within_120m"]
    for c in cols: out[c]=pd.NA
    if news is None or news.empty or out.empty: return out
    impact_col=next((c for c in ["Impact","impact"] if c in news.columns),None)
    event_col=next((c for c in ["Event","event","Title","title"] if c in news.columns),None)
    nt=news["news_time"].to_numpy(dtype="datetime64[ns]"); et=out["entry_time"].to_numpy(dtype="datetime64[ns]"); n=len(nt)
    right=np.searchsorted(nt,et,side="left"); left=np.maximum(right-1,0); rc=np.minimum(right,n-1)
    ld=np.abs(et-nt[left]).astype("timedelta64[s]").astype(np.float64); rd=np.abs(et-nt[rc]).astype("timedelta64[s]").astype(np.float64)
    cr=(right<n)&(rd<ld); ni=np.where(cr,rc,left); ns=np.where(cr,rd,ld)
    out["nearest_news_time"]=news["news_time"].iloc[ni].to_numpy(); out["nearest_news_minutes"]=ns/60.0
    if event_col: out["nearest_news_event"]=news[event_col].iloc[ni].to_numpy()
    if impact_col:
        iv=news[impact_col].astype(str).str.upper().to_numpy(); out["nearest_news_impact"]=iv[ni]
        high=np.fromiter(("HIGH" in v for v in iv),dtype=np.int8,count=n); prefix=np.concatenate(([0],np.cumsum(high,dtype=np.int64)))
    else: prefix=None
    for mins in [15,30,60,120]:
        delta=np.timedelta64(mins,"m"); lo=np.searchsorted(nt,et-delta,side="left"); hi=np.searchsorted(nt,et+delta,side="right")
        out[f"news_within_{mins}m"]=hi>lo
        if prefix is not None: out[f"high_impact_within_{mins}m"]=(prefix[hi]-prefix[lo])>0
    return out

def summarize(df):
    if df.empty: return {"trades":0}
    r=df.result_r.astype(float); gp=r[r>0].sum(); gl=abs(r[r<0].sum())
    return {"trades":int(len(r)),"wins":int((r>0).sum()),"losses":int((r<0).sum()),
            "win_rate_pct":float((r>0).mean()*100),"total_r":float(r.sum()),"avg_r":float(r.mean()),
            "profit_factor":float(gp/gl) if gl else float("inf")}

def rr_sweep_from_grid(grid_results):
    rows=[]
    for sl,rr in SELECTED_ATR_RR:
        s=summarize(pd.DataFrame(grid_results[(sl,rr)])); s.update({"sl_atr":sl,"rr":rr,"tp_atr":sl*rr}); rows.append(s)
    return pd.DataFrame(rows).sort_values(["profit_factor","total_r"],ascending=False)

def grouped_analysis(trades,column):
    rows=[]
    for value,g in trades.groupby(column,dropna=False):
        s=summarize(g); s[column]=value; rows.append(s)
    return pd.DataFrame(rows)

def all_atr_rr_trade_records(entries,grid_results):
    frames=[]; entry_df=entries.reset_index(drop=True)
    for sl,rr in SELECTED_ATR_RR:
        rows=grid_results[(sl,rr)]
        if not rows: continue
        exits=pd.DataFrame(rows)[["entry_time","side","exit_time","result_r","exit_reason","exit_price","duration_m1"]]
        merged=entry_df.merge(exits,on=["entry_time","side"],how="inner")
        if merged.empty: continue
        merged["sl_atr"],merged["rr"],merged["tp_atr"]=sl,rr,sl*rr
        frames.append(merged)
    return pd.concat(frames,ignore_index=True) if frames else pd.DataFrame()

def save_all_atr_rr_parts(all_rr,output_dir,max_mb=20):
    output_dir.mkdir(parents=True,exist_ok=True)
    for old in output_dir.glob("*.csv"): old.unlink()
    if all_rr.empty: return []
    max_bytes=int(max_mb*1024*1024); written=[]
    for (sl,rr),group in all_rr.groupby(["sl_atr","rr"],sort=True):
        group=group.reset_index(drop=True); prefix=f"sl{sl:.2f}_rr{rr:.2f}"
        csv_text=group.to_csv(index=False)
        if len(csv_text.encode("utf-8"))<=max_bytes:
            path=output_dir/f"{prefix}.csv"; path.write_text(csv_text,encoding="utf-8"); written.append(path); continue
        start=0; part=1
        while start<len(group):
            lo=start; hi=min(len(group),max(lo+1,int(len(group)*0.8)))
            while hi<len(group):
                candidate=group.iloc[lo:hi].to_csv(index=False)
                if len(candidate.encode("utf-8"))<=max_bytes:
                    next_hi=min(len(group),hi+max(1,(hi-lo)//4))
                    if next_hi==hi: break
                    hi=next_hi
                else: break
            while hi>lo:
                candidate=group.iloc[lo:hi].to_csv(index=False)
                if len(candidate.encode("utf-8"))<=max_bytes: break
                hi-=max(1,(hi-lo)//10)
            if hi<=lo: raise RuntimeError(f"Unable to split {prefix}: a single row exceeds {max_mb} MB.")
            path=output_dir/f"{prefix}_part{part:02d}.csv"; path.write_text(candidate,encoding="utf-8"); written.append(path)
            start=hi; part+=1
    return written

def main():
    m1=load_m1(); m5=make_m5(m1); entries=tag_news(build_entries(m5),load_news())
    entries.to_csv(RESULTS/"engulfing_entries.csv",index=False)

    grid_results=precompute_exit_grid(m1,entries)
    rr=rr_sweep_from_grid(grid_results)
    rr.to_csv(RESULTS/"engulfing_rr_sweep.csv",index=False)

    # Baseline is intentionally absent: this run is ONLY the 10 selected ATR/RR pairs.
    grouped_frames=[]
    for sl,rr_value in SELECTED_ATR_RR:
        df=pd.DataFrame(grid_results[(sl,rr_value)])
        if df.empty: continue
        df=df.merge(entries,on=["entry_time","side","entry","atr"],how="left")
        grouped_frames.append(df)
    selected_trades=pd.concat(grouped_frames,ignore_index=True) if grouped_frames else pd.DataFrame()
    if not selected_trades.empty:
        selected_trades.to_csv(RESULTS/"engulfing_selected_10_trades.csv",index=False)
        grouped_analysis(selected_trades,"side").to_csv(RESULTS/"selected_10_by_side.csv",index=False)
        grouped_analysis(selected_trades,"hour").to_csv(RESULTS/"selected_10_by_hour.csv",index=False)
        grouped_analysis(selected_trades,"session").to_csv(RESULTS/"selected_10_by_session.csv",index=False)
        selected_trades.groupby(["sl_atr","rr","hour"],as_index=False).agg(
            trades=("result_r","size"),total_r=("result_r","sum")
        ).to_csv(RESULTS/"selected_10_hour_by_atr_rr.csv",index=False)

    all_rr=all_atr_rr_trade_records(entries,grid_results)
    save_all_atr_rr_parts(all_rr,RESULTS/"engulfing_all_atr_rr_trades",max_mb=20)

    report={
        "status":"PASS","period_start":str(START),"period_end":str(END),
        "m1_rows":int(len(m1)),"m5_bars":int(len(m5)),"entries_after_rsi_filter":int(len(entries)),
        "tested_combinations":[{"sl_atr":sl,"rr":rr,"tp_atr":sl*rr} for sl,rr in SELECTED_ATR_RR],
        "results_rows":int(len(rr)),"news_data_available":load_news() is not None,
        "rsi_filter":{"LONG":[47.0,58.0],"SHORT":[42.0,51.0]},
        "numba_acceleration":bool(NUMBA_AVAILABLE),
        "entry_rules":{
            "ema20_ema50_bias":True,"pullback_lookback":3,"engulfing_only":True,
            "rejection_used":False,"ema50_touch_excluded":True,
            "ema20_proximity_max_atr":0.75,"ema50_proximity_max_atr":1.20
        },
        "notes":["ONLY the 10 selected ATR/RR combinations are evaluated.",
                 "RSI14 is an ENTRY filter: LONG 47-58 inclusive; SHORT 42-51 inclusive.",
                 "No 88-combination grid is computed.","Research-only branch; not MT5 LIVE code."]
    }
    (RESULTS/"engulfing_research_summary.json").write_text(json.dumps(report,indent=2,default=str),encoding="utf-8")
    print(json.dumps(report,indent=2,default=str))

if __name__=="__main__":
    main()
