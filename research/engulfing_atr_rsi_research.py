"""
Engulfing-only ATR/RR/RSI research for Trend + Pullback.

Research branch only. Not MT5 LIVE code.

Rules:
- EMA20 > EMA50: long bias; EMA20 < EMA50: short bias.
- Pullback into EMA20-EMA50 zone over prior closed M5 bars.
- ENTRY ONLY on bullish/bearish engulfing confirmation.
- Rejection patterns are excluded.
- An engulfing candle touching EMA50 is valid if its BODY does not cross EMA50.
- No RSI threshold/filter is applied: RSI is recorded only.
- Entry price is confirmation-candle close.
- Entry timestamp/hour/session, LONG/SHORT, EMA distances and RSI are recorded.
- Optional historical news CSV is tagged when present.
- RR/ATR exit variants are evaluated from the exact same entries.
- MFE/MAE are bounded by each trade's baseline exit, never the end of the dataset.
"""

from pathlib import Path
import json
import math
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "data" / "raw" / "XAUUSD_m1_20211001_20261001.csv"
NEWS = ROOT / "data" / "news" / "xauusd_news.csv"
RESULTS = ROOT / "results" / "engulfing_atr_rsi"
RESULTS.mkdir(parents=True, exist_ok=True)

START = pd.Timestamp("2023-09-30 00:00:00")
END = pd.Timestamp("2026-09-30 23:59:59")

# Keep a broad ATR grid and compare RR explicitly.
SL_GRID = [0.50, 0.75, 1.00, 1.25, 1.50, 2.00]
RR_GRID = [0.50, 0.75, 1.00, 1.25, 1.50, 2.00, 2.50, 3.00]

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
    df = pd.read_csv(INPUT)
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.set_index("Date").sort_index()
    df = df[~df.index.duplicated(keep="first")]
    df = df.loc[START:END]
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
        M1Count=("Close", "count"),
    )
    m5 = m5.dropna(subset=["Open", "High", "Low", "Close"])
    tr = pd.concat([
        m5["High"] - m5["Low"],
        (m5["High"] - m5["Close"].shift()).abs(),
        (m5["Low"] - m5["Close"].shift()).abs(),
    ], axis=1).max(axis=1)
    m5["ATR"] = tr.rolling(14).mean()
    return m5


def rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, float("nan"))
    out = 100 - (100 / (1 + rs))
    out[(avg_loss == 0) & (avg_gain > 0)] = 100.0
    out[(avg_gain == 0) & (avg_loss > 0)] = 0.0
    return out


def bullish_engulfing(bar, prev):
    return (
        bar.Close > bar.Open
        and prev.Close < prev.Open
        and bar.Open <= prev.Close
        and bar.Close >= prev.Open
    )


def bearish_engulfing(bar, prev):
    return (
        bar.Close < bar.Open
        and prev.Close > prev.Open
        and bar.Open >= prev.Close
        and bar.Close <= prev.Open
    )


def touches_zone(bar, ema20, ema50):
    hi = max(ema20, ema50)
    lo = min(ema20, ema50)
    return bar.High >= lo and bar.Low <= hi


def build_entries(m5):
    m5 = m5.copy()
    m5["EMA20"] = m5.Close.ewm(span=20, adjust=False).mean()
    m5["EMA50"] = m5.Close.ewm(span=50, adjust=False).mean()
    m5["RSI14"] = rsi(m5.Close, RSI_PERIOD)

    rows = []
    for i in range(max(50, PULLBACK_LOOKBACK + 3), len(m5)):
        bar = m5.iloc[i]
        prev = m5.iloc[i - 1]
        if not math.isfinite(float(bar.ATR)) or bar.ATR <= 0:
            continue

        ema20 = float(bar.EMA20)
        ema50 = float(bar.EMA50)
        atr = float(bar.ATR)

        long_side = ema20 > ema50
        short_side = ema20 < ema50
        if not (long_side or short_side):
            continue

        # Pullback is required in the preceding closed candles, excluding signal candle.
        recent = m5.iloc[max(0, i - PULLBACK_LOOKBACK):i]
        had_pullback = False
        for _, p in recent.iterrows():
            p20 = float(p.EMA20)
            p50 = float(p.EMA50)
            if touches_zone(p, p20, p50):
                if long_side and p.Close >= min(p20, p50):
                    had_pullback = True
                    break
                if short_side and p.Close <= max(p20, p50):
                    had_pullback = True
                    break
        if not had_pullback:
            continue

        engulf = bullish_engulfing(bar, prev) if long_side else bearish_engulfing(bar, prev)
        if not engulf:
            continue

        # EMA50 reaction is valid too, provided the candle body does not cross EMA50.
        ema50_reaction = (
            bar.Low <= ema50 <= bar.High
            and (
                (long_side and bar.Open >= ema50 and bar.Close >= ema50)
                or (short_side and bar.Open <= ema50 and bar.Close <= ema50)
            )
        )

        side = "LONG" if long_side else "SHORT"
        entry = float(bar.Close)
        hour = int(bar.name.hour)

        rows.append({
            "entry_time": bar.name,
            "side": side,
            "entry": entry,
            "atr": atr,
            "ema20": ema20,
            "ema50": ema50,
            "distance_ema20": entry - ema20,
            "distance_ema50": entry - ema50,
            "abs_distance_ema20": abs(entry - ema20),
            "abs_distance_ema50": abs(entry - ema50),
            "distance_ema20_atr": (entry - ema20) / atr,
            "distance_ema50_atr": (entry - ema50) / atr,
            "abs_distance_ema20_atr": abs(entry - ema20) / atr,
            "abs_distance_ema50_atr": abs(entry - ema50) / atr,
            "rsi14": float(bar.RSI14) if pd.notna(bar.RSI14) else float("nan"),
            "hour": hour,
            "minute": int(bar.name.minute),
            "session": session_for_hour(hour),
            "pattern": "BULLISH_ENGULFING" if long_side else "BEARISH_ENGULFING",
            "ema50_reaction": bool(ema50_reaction),
        })

    return pd.DataFrame(rows)


def first_exit(m1, entry, sl_atr, rr):
    side = entry.side
    price = float(entry.entry)
    atr = float(entry.atr)
    risk = atr * sl_atr
    if risk <= 0 or not math.isfinite(risk):
        return None

    if side == "LONG":
        sl = price - risk
        tp = price + risk * rr
    else:
        sl = price + risk
        tp = price - risk * rr

    pos = m1.index.searchsorted(entry.entry_time, side="right")
    after = m1.iloc[pos:]
    for ts, bar in after.iterrows():
        hit_sl = bar.Low <= sl if side == "LONG" else bar.High >= sl
        hit_tp = bar.High >= tp if side == "LONG" else bar.Low <= tp
        if hit_sl or hit_tp:
            if hit_sl:
                return ts, -1.0, "SL", sl, ts - entry.entry_time
            return ts, rr, "TP", tp, ts - entry.entry_time

    return None


def baseline_trades(m1, entries):
    rows = []
    for _, e in entries.iterrows():
        x = first_exit(m1, e, 1.0, 1.5)
        if x is None:
            continue
        ts, result_r, reason, exit_price, duration = x
        row = e.to_dict()
        row.update({
            "exit_time": ts,
            "result_r": result_r,
            "exit_reason": reason,
            "exit_price": exit_price,
            "duration_m1": int(duration.total_seconds() / 60),
        })
        rows.append(row)
    return pd.DataFrame(rows)


def mfe_mae_bounded(m1, trade):
    pos0 = m1.index.searchsorted(trade.entry_time, side="right")
    pos1 = m1.index.searchsorted(trade.exit_time, side="right")
    after = m1.iloc[pos0:pos1]
    if after.empty:
        return None

    price = float(trade.entry)
    atr = float(trade.atr)
    if trade.side == "LONG":
        favorable = after.High - price
        adverse = price - after.Low
    else:
        favorable = price - after.Low
        adverse = after.High - price

    mfe_idx = favorable.idxmax()
    mae_idx = adverse.idxmax()
    mfe = max(0.0, float(favorable.max()))
    mae = max(0.0, float(adverse.max()))

    return {
        "entry_time": trade.entry_time,
        "exit_time": trade.exit_time,
        "side": trade.side,
        "entry": price,
        "atr": atr,
        "mfe_price": mfe,
        "mae_price": mae,
        "mfe_r_at_1atr": mfe / atr if atr else float("nan"),
        "mae_r_at_1atr": mae / atr if atr else float("nan"),
        "time_to_mfe_m1": int((mfe_idx - trade.entry_time).total_seconds() / 60),
        "time_to_mae_m1": int((mae_idx - trade.entry_time).total_seconds() / 60),
        "result_r": trade.result_r,
    }


def load_news():
    if not NEWS.exists():
        return None
    n = pd.read_csv(NEWS)
    time_col = next((c for c in ["datetime", "DateTime", "timestamp", "time", "Date"] if c in n.columns), None)
    if time_col is None:
        return None
    n["news_time"] = pd.to_datetime(n[time_col], errors="coerce")
    n = n.dropna(subset=["news_time"]).sort_values("news_time")
    return n


def tag_news(entries, news):
    out = entries.copy()
    cols = [
        "nearest_news_time", "nearest_news_event", "nearest_news_impact",
        "nearest_news_minutes", "news_within_15m", "news_within_30m",
        "news_within_60m", "news_within_120m",
        "high_impact_within_15m", "high_impact_within_30m",
        "high_impact_within_60m", "high_impact_within_120m",
    ]
    for c in cols:
        out[c] = pd.NA
    if news is None or news.empty:
        return out

    impact_col = next((c for c in ["Impact", "impact"] if c in news.columns), None)
    event_col = next((c for c in ["Event", "event", "Title", "title"] if c in news.columns), None)

    nt = news["news_time"].tolist()
    for idx, row in out.iterrows():
        t = row.entry_time
        diffs = [abs((x - t).total_seconds()) / 60 for x in nt]
        if not diffs:
            continue
        j = min(range(len(diffs)), key=diffs.__getitem__)
        d = diffs[j]
        out.at[idx, "nearest_news_time"] = nt[j]
        out.at[idx, "nearest_news_minutes"] = d
        if event_col:
            out.at[idx, "nearest_news_event"] = news.iloc[j][event_col]
        if impact_col:
            out.at[idx, "nearest_news_impact"] = news.iloc[j][impact_col]

        window = news.iloc[[k for k, x in enumerate(diffs) if x <= 120]]
        for mins in [15, 30, 60, 120]:
            out.at[idx, f"news_within_{mins}m"] = bool(any(x <= mins for x in diffs))
            if impact_col:
                impacts = window.loc[[diffs[k] <= mins for k in window.index]] if False else None
                vals = []
                for k, d2 in enumerate(diffs):
                    if d2 <= mins:
                        vals.append(str(news.iloc[k][impact_col]).upper())
                out.at[idx, f"high_impact_within_{mins}m"] = any("HIGH" in v for v in vals)
    return out


def summarize(df):
    if df.empty:
        return {"trades": 0}
    r = df.result_r.astype(float)
    gp = r[r > 0].sum()
    gl = abs(r[r < 0].sum())
    return {
        "trades": int(len(r)),
        "wins": int((r > 0).sum()),
        "losses": int((r < 0).sum()),
        "win_rate_pct": float((r > 0).mean() * 100),
        "total_r": float(r.sum()),
        "avg_r": float(r.mean()),
        "profit_factor": float(gp / gl) if gl else float("inf"),
    }


def rr_sweep(m1, entries):
    rows = []
    for sl in SL_GRID:
        for rr in RR_GRID:
            results = []
            for _, e in entries.iterrows():
                x = first_exit(m1, e, sl, rr)
                if x is None:
                    continue
                ts, result_r, reason, exit_price, duration = x
                results.append({"result_r": result_r, "exit_time": ts, "exit_reason": reason})
            s = summarize(pd.DataFrame(results))
            s.update({"sl_atr": sl, "rr": rr, "tp_atr": sl * rr})
            rows.append(s)
    return pd.DataFrame(rows).sort_values(["profit_factor", "total_r"], ascending=False)


def grouped_analysis(trades, column):
    rows = []
    for value, g in trades.groupby(column, dropna=False):
        s = summarize(g)
        s[column] = value
        rows.append(s)
    return pd.DataFrame(rows)


def main():
    m1 = load_m1()
    m5 = make_m5(m1)
    entries = build_entries(m5)
    news = load_news()
    entries = tag_news(entries, news)

    entries.to_csv(RESULTS / "engulfing_entries.csv", index=False)

    base = baseline_trades(m1, entries)
    base.to_csv(RESULTS / "engulfing_baseline_trades.csv", index=False)

    mfe_rows = []
    for _, trade in base.iterrows():
        x = mfe_mae_bounded(m1, trade)
        if x:
            mfe_rows.append(x)
    mfe = pd.DataFrame(mfe_rows)
    mfe.to_csv(RESULTS / "engulfing_mfe_mae.csv", index=False)

    rr = rr_sweep(m1, entries)
    rr.to_csv(RESULTS / "engulfing_rr_sweep.csv", index=False)

    grouped_analysis(base, "session").to_csv(RESULTS / "engulfing_by_session.csv", index=False)
    grouped_analysis(base, "hour").to_csv(RESULTS / "engulfing_by_hour.csv", index=False)
    grouped_analysis(base, "side").to_csv(RESULTS / "engulfing_by_side.csv", index=False)
    grouped_analysis(base, "ema50_reaction").to_csv(RESULTS / "engulfing_ema50_reaction.csv", index=False)

    news_cols = [c for c in entries.columns if "news" in c]
    if news_cols:
        entries[["entry_time", "side", "rsi14"] + news_cols].to_csv(
            RESULTS / "engulfing_news_context.csv", index=False
        )

    report = {
        "status": "PASS",
        "period_start": str(START),
        "period_end": str(END),
        "m1_rows": int(len(m1)),
        "m5_bars": int(len(m5)),
        "entries": int(len(entries)),
        "baseline": summarize(base),
        "rr_rows": int(len(rr)),
        "best_rr_by_pf": rr.iloc[0].to_dict() if not rr.empty else None,
        "news_data_available": news is not None,
        "rsi_threshold_applied": False,
        "entry_patterns": ["BULLISH_ENGULFING", "BEARISH_ENGULFING"],
        "rejection_used": False,
        "ema50_stop_used": False,
        "notes": [
            "Only engulfing confirmations are eligible.",
            "EMA50 reaction engulfings are retained when the candle body does not cross EMA50.",
            "RSI14 is recorded per trade but no RSI entry threshold is applied.",
            "MFE/MAE are bounded by the baseline trade exit.",
            "RR/ATR variants use the exact same engulfing entry timestamps.",
            "Research-only branch; not the final MT5 LIVE bot.",
        ],
    }
    (RESULTS / "engulfing_research_summary.json").write_text(
        json.dumps(report, indent=2, default=str), encoding="utf-8"
    )
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
