"""
EMA50 reaction + breathing-room SL research.

Uses the exact baseline entry timestamps. The EMA50-specific setup is:
- LONG: signal candle touches EMA50 and both Open and Close stay >= EMA50.
- SHORT: signal candle touches EMA50 and both Open and Close stay <= EMA50.
A wick may cross EMA50; a candle BODY may not.

SL is placed beyond EMA50 by a configurable ATR buffer.
RR is tested independently. Every output retains exact entry timestamp,
hour, session, side, pattern, EMA50 distance and news context.

Research only. Does not modify the MT5 LIVE EA.
Historical news is read from data/news/xauusd_news.csv when supplied.
No historical news event is invented.
"""

from pathlib import Path
import json
import math
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "data" / "raw" / "XAUUSD_m1_20211001_20261001.csv"
RESULTS = ROOT / "results"
ENTRIES = RESULTS / "trend_pullback_entries.csv"
NEWS = ROOT / "data" / "news" / "xauusd_news.csv"
OUT = RESULTS / "research"
OUT.mkdir(parents=True, exist_ok=True)

BUFFER_ATR_GRID = [0.10, 0.20, 0.30, 0.50]
RR_GRID = [0.75, 1.00, 1.25, 1.50, 2.00, 2.50, 3.00]
NEWS_WINDOWS = [15, 30, 60, 120]

SESSIONS = {
    "ASIA": range(0, 8),
    "LONDON": range(8, 13),
    "NEW_YORK": range(13, 18),
    "NY_LATE": range(18, 22),
    "OFF": range(22, 24),
}


def load_m1():
    df = pd.read_csv(INPUT)
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.set_index("Date").sort_index()
    df = df[~df.index.duplicated(keep="first")]
    end = df.index.max()
    start = end - pd.DateOffset(years=1)
    df = df.loc[start:end]
    for c in ["Open", "High", "Low", "Close", "Volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.dropna(subset=["Open", "High", "Low", "Close"])


def make_m5(m1):
    m5 = m1.resample("5min", label="left", closed="left").agg(
        Open=("Open", "first"),
        High=("High", "max"),
        Low=("Low", "min"),
        Close=("Close", "last"),
        Volume=("Volume", "sum"),
    )
    return m5.dropna(subset=["Open", "High", "Low", "Close"])


def add_indicators(m5):
    m5 = m5.copy()
    m5["EMA20"] = m5["Close"].ewm(span=20, adjust=False).mean()
    m5["EMA50"] = m5["Close"].ewm(span=50, adjust=False).mean()
    prev = m5["Close"].shift(1)
    tr = pd.concat(
        [
            m5["High"] - m5["Low"],
            (m5["High"] - prev).abs(),
            (m5["Low"] - prev).abs(),
        ],
        axis=1,
    ).max(axis=1)
    m5["ATR14"] = tr.rolling(14).mean()
    return m5


def load_entries():
    e = pd.read_csv(ENTRIES)
    e["entry_time"] = pd.to_datetime(e["entry_time"])
    return e.sort_values("entry_time").reset_index(drop=True)


def load_news():
    if not NEWS.exists():
        return pd.DataFrame(columns=["event_time", "event", "currency", "impact"])
    n = pd.read_csv(NEWS)
    required = {"event_time", "event", "currency", "impact"}
    missing = required - set(n.columns)
    if missing:
        raise ValueError(f"News file missing columns: {sorted(missing)}")
    n["event_time"] = pd.to_datetime(n["event_time"])
    n["impact"] = n["impact"].astype(str).str.upper()
    return n.sort_values("event_time").reset_index(drop=True)


def session_name(ts):
    h = int(ts.hour)
    for name, hours in SESSIONS.items():
        if h in hours:
            return name
    return "OFF"


def pattern_info(m5, ts, side):
    i = m5.index.searchsorted(ts)
    if i >= len(m5) or m5.index[i] != ts or i < 1:
        return {"pattern": "UNKNOWN", "ema50_setup": False, "body_breaks_ema50": None}

    bar = m5.iloc[i]
    prev = m5.iloc[i - 1]
    ema50 = float(bar.EMA50)
    rng = float(bar.High - bar.Low)
    body = abs(float(bar.Close - bar.Open))
    if rng <= 0 or body <= 0 or not math.isfinite(ema50):
        return {"pattern": "NONE", "ema50_setup": False, "body_breaks_ema50": None}

    if side == "LONG":
        engulf = bar.Close > bar.Open and prev.Close < prev.Open and bar.Open <= prev.Close and bar.Close >= prev.Open
        rejection = bar.Close > bar.Open and min(bar.Open, bar.Close) - bar.Low >= body and (bar.Close - bar.Low) / rng >= 0.70
        touches = bar.Low <= ema50 <= bar.High
        body_holds = bar.Open >= ema50 and bar.Close >= ema50
        body_breaks = min(bar.Open, bar.Close) < ema50
    else:
        engulf = bar.Close < bar.Open and prev.Close > prev.Open and bar.Open >= prev.Close and bar.Close <= prev.Open
        rejection = bar.Close < bar.Open and bar.High - max(bar.Open, bar.Close) >= body and (bar.High - bar.Close) / rng >= 0.70
        touches = bar.Low <= ema50 <= bar.High
        body_holds = bar.Open <= ema50 and bar.Close <= ema50
        body_breaks = max(bar.Open, bar.Close) > ema50

    pattern = "ENGULFING" if engulf else "REJECTION" if rejection else "NONE"
    return {
        "pattern": pattern,
        "ema50_setup": bool(pattern != "NONE" and touches and body_holds),
        "body_breaks_ema50": bool(body_breaks),
        "ema50": ema50,
        "signal_open": float(bar.Open),
        "signal_close": float(bar.Close),
        "signal_high": float(bar.High),
        "signal_low": float(bar.Low),
    }


def news_context(ts, news):
    out = {"news_data_available": not news.empty, "news_nearest_event": "", "news_nearest_impact": "", "news_nearest_minutes": None}
    for w in NEWS_WINDOWS:
        out[f"news_within_{w}m"] = False
        out[f"high_impact_within_{w}m"] = False
    if news.empty:
        return out

    delta = (news.event_time - ts).abs()
    idx = delta.idxmin()
    nearest = news.loc[idx]
    mins = int(delta.loc[idx].total_seconds() / 60)
    out["news_nearest_event"] = str(nearest.event)
    out["news_nearest_impact"] = str(nearest.impact)
    out["news_nearest_minutes"] = mins
    for w in NEWS_WINDOWS:
        out[f"news_within_{w}m"] = mins <= w
        out[f"high_impact_within_{w}m"] = mins <= w and str(nearest.impact).upper() == "HIGH"
    return out


def summarize(g):
    r = pd.Series(g.result_r, dtype=float)
    gp = r[r > 0].sum()
    gl = abs(r[r < 0].sum())
    return {
        "trades": len(r),
        "wins": int((r > 0).sum()),
        "losses": int((r < 0).sum()),
        "win_rate_pct": float((r > 0).mean() * 100),
        "total_r": float(r.sum()),
        "avg_r": float(r.mean()),
        "profit_factor": float(gp / gl) if gl else float("inf"),
    }


def simulate(m1, entry_time, side, entry, sl, tp, rr):
    start = m1.index.searchsorted(entry_time, side="right")
    for ts, bar in m1.iloc[start:].iterrows():
        hit_sl = bar.Low <= sl if side == "LONG" else bar.High >= sl
        hit_tp = bar.High >= tp if side == "LONG" else bar.Low <= tp
        if hit_sl or hit_tp:
            if hit_sl:
                return -1.0, "SL", ts
            return rr, "TP", ts

    final_ts = m1.index[-1]
    final_close = float(m1.iloc[-1].Close)
    risk = abs(entry - sl)
    pnl = final_close - entry if side == "LONG" else entry - final_close
    return pnl / risk, "END_OF_DATA", final_ts


def main():
    m1 = load_m1()
    m5 = add_indicators(make_m5(m1))
    entries = load_entries()
    news = load_news()

    contexts = []
    for _, e in entries.iterrows():
        ts = e.entry_time
        side = str(e.side)
        p = pattern_info(m5, ts, side)
        contexts.append({
            "entry_time": ts,
            "entry_hour": int(ts.hour),
            "entry_minute": int(ts.minute),
            "session": session_name(ts),
            "side": side,
            "entry": float(e.entry),
            "entry_atr": float(e.atr),
            **p,
            **news_context(ts, news),
        })

    context = pd.DataFrame(contexts)
    context.to_csv(OUT / "ema50_entry_context.csv", index=False)

    eligible = context[context["ema50_setup"] == True].copy()
    detail_rows = []

    for _, e in eligible.iterrows():
        entry = float(e.entry)
        ema50 = float(e.ema50)
        atr = float(e.entry_atr)
        side = str(e.side)

        for buffer_atr in BUFFER_ATR_GRID:
            buffer = atr * buffer_atr
            sl = ema50 - buffer if side == "LONG" else ema50 + buffer
            risk = abs(entry - sl)
            if risk <= 0:
                continue

            for rr in RR_GRID:
                tp = entry + risk * rr if side == "LONG" else entry - risk * rr
                result_r, reason, exit_time = simulate(
                    m1, e.entry_time, side, entry, sl, tp, rr
                )
                detail_rows.append({
                    **e.to_dict(),
                    "buffer_atr": buffer_atr,
                    "sl": sl,
                    "sl_distance": risk,
                    "sl_distance_atr": risk / atr,
                    "rr": rr,
                    "tp": tp,
                    "result_r": result_r,
                    "exit_reason": reason,
                    "exit_time": exit_time,
                    "duration_m1": int((exit_time - e.entry_time).total_seconds() / 60),
                })

    detail = pd.DataFrame(detail_rows)
    detail.to_csv(OUT / "ema50_reaction_trades.csv", index=False)

    def grouped(path, keys):
        rows = []
        if detail.empty:
            pd.DataFrame().to_csv(OUT / path, index=False)
            return
        for vals, g in detail.groupby(keys, sort=True):
            if not isinstance(vals, tuple):
                vals = (vals,)
            s = summarize(g)
            s.update(dict(zip(keys, vals)))
            rows.append(s)
        pd.DataFrame(rows).to_csv(OUT / path, index=False)

    grouped("ema50_reaction_rr_sweep.csv", ["buffer_atr", "rr"])
    grouped("ema50_reaction_by_session.csv", ["buffer_atr", "rr", "session"])
    grouped("ema50_reaction_by_hour.csv", ["buffer_atr", "rr", "entry_hour"])
    grouped("ema50_reaction_by_pattern.csv", ["buffer_atr", "rr", "pattern"])
    grouped("ema50_reaction_by_side.csv", ["buffer_atr", "rr", "side"])

    news_rows = []
    if not detail.empty:
        for (buffer, rr), g in detail.groupby(["buffer_atr", "rr"], sort=True):
            for col in ["high_impact_within_15m", "high_impact_within_30m", "high_impact_within_60m", "high_impact_within_120m"]:
                x = g[g[col] == True]
                if len(x):
                    s = summarize(x)
                    s.update({"buffer_atr": buffer, "rr": rr, "news_window": col})
                    news_rows.append(s)
    pd.DataFrame(news_rows).to_csv(OUT / "ema50_reaction_news_study.csv", index=False)

    sweep = pd.read_csv(OUT / "ema50_reaction_rr_sweep.csv") if (OUT / "ema50_reaction_rr_sweep.csv").exists() else pd.DataFrame()
    report = {
        "status": "PASS",
        "all_baseline_entries": len(context),
        "ema50_reaction_entries": len(eligible),
        "buffer_atr_grid": BUFFER_ATR_GRID,
        "rr_grid": RR_GRID,
        "rule": "EMA50 touch + valid candlestick reaction + body remains on trend side of EMA50; wick may cross.",
        "sl_rule": "EMA50 plus/minus ATR buffer, beyond EMA50 to give the trade breathing room.",
        "time_tracking": "Exact entry timestamp, hour, minute and session retained for every eligible trade.",
        "news_data_available": not news.empty,
        "news_file": str(NEWS),
        "notes": [
            "Original entry timestamps are preserved; this is a controlled exit/setup study.",
            "Only the requested EMA50 reaction subset is tested in the EMA50-specific results.",
            "SL/TP variants are independent and may overlap later baseline entries.",
            "Historical news is only tagged when a real news CSV is provided; no events are guessed.",
            "Research only; not part of the final MT5 LIVE bot."
        ],
        "best_by_profit_factor": sweep.sort_values(["profit_factor", "total_r"], ascending=False).iloc[0].to_dict() if not sweep.empty else None,
        "best_by_total_r": sweep.sort_values("total_r", ascending=False).iloc[0].to_dict() if not sweep.empty else None,
    }
    (OUT / "ema50_reaction_summary.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
