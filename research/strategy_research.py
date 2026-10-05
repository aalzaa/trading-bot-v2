"""
Research suite for the Trend + Pullback baseline.

IMPORTANT:
- Baseline entry timestamps are fixed from trend_pullback_entries.csv.
- Exit sweeps NEVER regenerate or filter entries.
- MFE/MAE are calculated from the original M1 dataset after each entry.
- Time/regime studies use the fixed baseline trade/entry ledger.
- This is research-only code; it is NOT part of the final MT5 LIVE bot.
"""

from pathlib import Path
import json
import math
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "data" / "raw" / "XAUUSD_m1_20211001_20261001.csv"
RESULTS = ROOT / "results"
ENTRIES = RESULTS / "trend_pullback_entries.csv"
BASE_TRADES = RESULTS / "trend_pullback_trades.csv"

# Exit research grid. Values are multiples of the original entry ATR.
SL_GRID = [0.50, 0.75, 1.00, 1.25, 1.50, 2.00]
TP_GRID = [0.75, 1.00, 1.25, 1.50, 2.00, 2.50, 3.00]

OUT = RESULTS / "research"
OUT.mkdir(parents=True, exist_ok=True)


def load_m1():
    df = pd.read_csv(INPUT)
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.set_index("Date").sort_index()
    df = df[~df.index.duplicated(keep="first")]
    df = df.loc["2021-10-01":"2026-10-01"]
    for c in ["Open", "High", "Low", "Close", "Volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.dropna(subset=["Open", "High", "Low", "Close"])


def load_entries():
    e = pd.read_csv(ENTRIES)
    e["entry_time"] = pd.to_datetime(e["entry_time"])
    return e.sort_values("entry_time").reset_index(drop=True)


def load_baseline_trades():
    t = pd.read_csv(BASE_TRADES)
    t["entry_time"] = pd.to_datetime(t["entry_time"])
    t["exit_time"] = pd.to_datetime(t["exit_time"])
    return t.sort_values("entry_time").reset_index(drop=True)


def first_exit(m1, entry, sl_mult, tp_mult):
    side = entry.side
    price = float(entry.entry)
    atr = float(entry.atr)
    risk = atr * sl_mult
    if risk <= 0 or not math.isfinite(risk):
        return None

    if side == "LONG":
        sl = price - risk
        tp = price + atr * tp_mult
    else:
        sl = price + risk
        tp = price - atr * tp_mult

    after = m1.loc[m1.index > entry.entry_time]
    for ts, bar in after.iterrows():
        hit_sl = bar.Low <= sl if side == "LONG" else bar.High >= sl
        hit_tp = bar.High >= tp if side == "LONG" else bar.Low <= tp
        if hit_sl or hit_tp:
            # Conservative ambiguity: SL first.
            if hit_sl:
                return ts, -1.0, "SL", sl, tp, ts - entry.entry_time
            return ts, tp_mult / sl_mult, "TP", tp, tp, ts - entry.entry_time

    final_ts = m1.index[-1]
    final = m1.iloc[-1]
    pnl = final.Close - price if side == "LONG" else price - final.Close
    return final_ts, pnl / risk, "END_OF_DATA", final.Close, tp, final_ts - entry.entry_time


def mfe_mae(m1, entry):
    side = entry.side
    price = float(entry.entry)
    after = m1.loc[m1.index > entry.entry_time]
    if after.empty:
        return None

    if side == "LONG":
        favorable = after.High - price
        adverse = price - after.Low
    else:
        favorable = price - after.Low
        adverse = after.High - price

    mfe_idx = favorable.idxmax()
    mae_idx = adverse.idxmax()
    mfe = float(favorable.max())
    mae = float(adverse.max())

    return {
        "entry_time": entry.entry_time,
        "side": side,
        "entry": price,
        "atr": float(entry.atr),
        "mfe_price": mfe,
        "mae_price": mae,
        "mfe_r_at_1atr": mfe / float(entry.atr),
        "mae_r_at_1atr": mae / float(entry.atr),
        "time_to_mfe_m1": int((mfe_idx - entry.entry_time).total_seconds() / 60),
        "time_to_mae_m1": int((mae_idx - entry.entry_time).total_seconds() / 60),
    }


def summarize(results):
    r = pd.Series([x["result_r"] for x in results], dtype=float)
    wins = r[r > 0]
    losses = r[r < 0]
    gp = float(wins.sum())
    gl = float(abs(losses.sum()))
    return {
        "trades": int(len(r)),
        "wins": int((r > 0).sum()),
        "losses": int((r < 0).sum()),
        "win_rate_pct": float((r > 0).mean() * 100),
        "total_r": float(r.sum()),
        "avg_r": float(r.mean()),
        "profit_factor": float(gp / gl) if gl else float("inf"),
    }


def exit_sweep(m1, entries):
    rows = []
    for sl in SL_GRID:
        for tp in TP_GRID:
            results = []
            for _, e in entries.iterrows():
                x = first_exit(m1, e, sl, tp)
                if x is None:
                    continue
                ts, rr, reason, exit_price, target, duration = x
                results.append({
                    "result_r": rr,
                    "exit_reason": reason,
                    "exit_time": ts,
                    "duration_m1": int(duration.total_seconds() / 60),
                })
            s = summarize(results)
            s.update({"sl_atr": sl, "tp_atr": tp, "rr": tp / sl})
            rows.append(s)
    out = pd.DataFrame(rows).sort_values(["profit_factor", "total_r"], ascending=False)
    out.to_csv(OUT / "exit_sweep.csv", index=False)
    return out


def mae_mfe_study(m1, entries):
    rows = []
    for _, e in entries.iterrows():
        x = mfe_mae(m1, e)
        if x:
            rows.append(x)
    out = pd.DataFrame(rows)
    out.to_csv(OUT / "mfe_mae.csv", index=False)

    thresholds = [0.25, 0.50, 0.75, 1.00, 1.25, 1.50, 2.00, 2.50, 3.00]
    threshold_rows = []
    for t in thresholds:
        threshold_rows.append({
            "threshold_r": t,
            "mfe_reached_pct": float((out.mfe_r_at_1atr >= t).mean() * 100),
            "mae_reached_pct": float((out.mae_r_at_1atr >= t).mean() * 100),
            "mfe_count": int((out.mfe_r_at_1atr >= t).sum()),
            "mae_count": int((out.mae_r_at_1atr >= t).sum()),
        })
    pd.DataFrame(threshold_rows).to_csv(OUT / "mfe_mae_thresholds.csv", index=False)
    return out


def time_study(trades):
    t = trades.copy()
    t["hour"] = t.entry_time.dt.hour
    t["year"] = t.entry_time.dt.year
    t["month"] = t.entry_time.dt.to_period("M").astype(str)

    def agg(g):
        r = g.result_r
        gp = r[r > 0].sum()
        gl = abs(r[r < 0].sum())
        return pd.Series({
            "trades": len(g),
            "wins": int((r > 0).sum()),
            "win_rate_pct": (r > 0).mean() * 100,
            "total_r": r.sum(),
            "avg_r": r.mean(),
            "profit_factor": gp / gl if gl else float("inf"),
        })

    hour = t.groupby("hour", sort=True).apply(agg, include_groups=False)
    year = t.groupby("year", sort=True).apply(agg, include_groups=False)
    month = t.groupby("month", sort=True).apply(agg, include_groups=False)

    hour.to_csv(OUT / "time_by_hour.csv")
    year.to_csv(OUT / "regime_by_year.csv")
    month.to_csv(OUT / "regime_by_month.csv")

    # Targeted hour exclusion studies; entries remain otherwise identical.
    exclusions = [
        ("exclude_12", [12]),
        ("exclude_12_20", [12, 20]),
        ("exclude_00_02_09_12_19_20_21", [0, 2, 9, 12, 19, 20, 21]),
    ]
    rows = []
    for name, hours in exclusions:
        g = t[~t.entry_time.dt.hour.isin(hours)]
        s = agg(g)
        s["filter"] = name
        s["excluded_hours"] = ",".join(map(str, hours))
        rows.append(s)
    pd.DataFrame(rows).to_csv(OUT / "time_filter_tests.csv", index=False)


def main():
    m1 = load_m1()
    entries = load_entries()
    trades = load_baseline_trades()

    sweep = exit_sweep(m1, entries)
    mae = mae_mfe_study(m1, entries)
    time_study(trades)

    report = {
        "status": "PASS",
        "entries_used": int(len(entries)),
        "m1_rows": int(len(m1)),
        "exit_sweep_rows": int(len(sweep)),
        "best_exit_by_pf": sweep.iloc[0].to_dict(),
        "mfe_mean_r": float(mae.mfe_r_at_1atr.mean()),
        "mae_mean_r": float(mae.mae_r_at_1atr.mean()),
        "mfe_median_r": float(mae.mfe_r_at_1atr.median()),
        "mae_median_r": float(mae.mae_r_at_1atr.median()),
        "notes": [
            "Exit sweep uses the exact baseline entry timestamps from trend_pullback_entries.csv.",
            "Exit variants are evaluated independently; no new signals are generated.",
            "MFE/MAE use M1 highs/lows after entry.",
            "Hour/year/month studies use baseline trade results and UTC/source timestamps.",
            "Research outputs are not part of the final MT5 LIVE bot.",
        ],
    }
    (OUT / "research_summary.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
