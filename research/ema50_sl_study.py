"""
EMA50-anchored stop-loss research.

Uses the exact baseline entry timestamps from trend_pullback_entries.csv.
For LONG: SL = EMA50 at entry.
For SHORT: SL = EMA50 at entry.
TP is defined as a multiple of the actual entry-to-EMA50 stop distance.

This is research-only code. It does not modify the live MT5 EA.
"""

from pathlib import Path
import json
import math
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "data" / "raw" / "XAUUSD_m1_20211001_20261001.csv"
RESULTS = ROOT / "results"
ENTRIES = RESULTS / "trend_pullback_entries.csv"
OUT = RESULTS / "research"
OUT.mkdir(parents=True, exist_ok=True)

TP_RR_GRID = [0.75, 1.00, 1.25, 1.50, 2.00, 2.50, 3.00]


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


def add_ema50(m5):
    m5 = m5.copy()
    m5["EMA50"] = m5["Close"].ewm(span=50, adjust=False).mean()
    return m5


def load_entries():
    e = pd.read_csv(ENTRIES)
    e["entry_time"] = pd.to_datetime(e["entry_time"])
    return e.sort_values("entry_time").reset_index(drop=True)


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


def first_exit(m1, entry, ema50, rr):
    side = str(entry.side)
    price = float(entry.entry)
    ema50 = float(ema50)

    if side == "LONG":
        stop_distance = price - ema50
        sl = ema50
        tp = price + stop_distance * rr
    else:
        stop_distance = ema50 - price
        sl = ema50
        tp = price - stop_distance * rr

    # Invalid if EMA50 is on the wrong side of the entry.
    if stop_distance <= 0 or not math.isfinite(stop_distance):
        return None

    start_pos = m1.index.searchsorted(entry.entry_time, side="right")
    after = m1.iloc[start_pos:]

    for ts, bar in after.iterrows():
        hit_sl = bar.Low <= sl if side == "LONG" else bar.High >= sl
        hit_tp = bar.High >= tp if side == "LONG" else bar.Low <= tp

        if hit_sl or hit_tp:
            # Conservative same-bar ambiguity: SL first.
            if hit_sl:
                return {
                    "result_r": -1.0,
                    "exit_reason": "SL",
                    "exit_time": ts,
                    "duration_m1": int((ts - entry.entry_time).total_seconds() / 60),
                }
            return {
                "result_r": float(rr),
                "exit_reason": "TP",
                "exit_time": ts,
                "duration_m1": int((ts - entry.entry_time).total_seconds() / 60),
            }

    final_ts = m1.index[-1]
    final_close = float(m1.iloc[-1].Close)
    pnl = final_close - price if side == "LONG" else price - final_close
    return {
        "result_r": pnl / stop_distance,
        "exit_reason": "END_OF_DATA",
        "exit_time": final_ts,
        "duration_m1": int((final_ts - entry.entry_time).total_seconds() / 60),
    }


def main():
    m1 = load_m1()
    m5 = add_ema50(make_m5(m1))
    entries = load_entries()

    rows = []
    detail_rows = []

    for _, entry in entries.iterrows():
        ts = entry.entry_time
        if ts not in m5.index:
            continue

        ema50 = float(m5.loc[ts, "EMA50"])
        price = float(entry.entry)
        side = str(entry.side)

        if side == "LONG":
            distance = price - ema50
        else:
            distance = ema50 - price

        if distance <= 0 or not math.isfinite(distance):
            continue

        for rr in TP_RR_GRID:
            result = first_exit(m1, entry, ema50, rr)
            if result is None:
                continue
            detail_rows.append({
                "entry_time": ts,
                "side": side,
                "entry": price,
                "ema50": ema50,
                "sl_distance": distance,
                "sl_distance_atr": distance / float(entry.atr),
                "rr": rr,
                **result,
            })

    detail = pd.DataFrame(detail_rows)
    detail.to_csv(OUT / "ema50_sl_trades.csv", index=False)

    for rr, group in detail.groupby("rr", sort=True):
        results = group[["result_r"]].rename(columns={"result_r": "x"}).to_dict("records")
        summary = summarize([{"result_r": float(x["x"])} for x in results])
        summary["rr"] = float(rr)
        summary["avg_sl_distance_atr"] = float(group.sl_distance_atr.mean())
        summary["median_sl_distance_atr"] = float(group.sl_distance_atr.median())
        rows.append(summary)

    sweep = pd.DataFrame(rows).sort_values(["profit_factor", "total_r"], ascending=False)
    sweep.to_csv(OUT / "ema50_sl_rr_sweep.csv", index=False)

    by_side = []
    for (side, rr), group in detail.groupby(["side", "rr"], sort=True):
        summary = summarize([{"result_r": float(x)} for x in group.result_r])
        summary.update({"side": side, "rr": float(rr)})
        by_side.append(summary)
    pd.DataFrame(by_side).to_csv(OUT / "ema50_sl_rr_by_side.csv", index=False)

    report = {
        "status": "PASS",
        "entries_used": int(len(entries)),
        "valid_entries": int(detail.entry_time.nunique()),
        "rr_grid": TP_RR_GRID,
        "stop_rule": "LONG SL at EMA50 below entry; SHORT SL at EMA50 above entry",
        "tp_rule": "TP = entry +/- RR * actual entry-to-EMA50 stop distance",
        "notes": [
            "Exact baseline entry timestamps are reused; entry logic is not regenerated.",
            "EMA50 is the same M5 EMA50 used by the strategy.",
            "Same-bar SL/TP ambiguity is resolved conservatively in favor of SL.",
            "Each RR variant is evaluated independently, so long-running variants can overlap later baseline entries.",
            "This is research-only and must not be copied into the final MT5 LIVE package."
        ],
        "best_by_profit_factor": sweep.iloc[0].to_dict() if not sweep.empty else None,
        "best_by_total_r": sweep.sort_values("total_r", ascending=False).iloc[0].to_dict() if not sweep.empty else None,
    }
    (OUT / "ema50_sl_summary.json").write_text(
        json.dumps(report, indent=2, default=str),
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
