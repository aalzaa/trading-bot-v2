"""
XAUUSD Trend + Pullback research backtester.

Master data: M1 Dukascopy CSV.
Internally resamples M1 -> M5 and runs:
- EMA20 / EMA50 trend
- pullback into EMA20-EMA50 zone within prior 3 closed M5 bars
- bullish/bearish engulfing OR rejection confirmation
- entry at confirmation candle close
- ATR14
- SL = 1.0 ATR
- TP = 1.5 ATR
- one position at a time
- latest available 1-year window (dataset itself defines trading availability)

Outputs:
results/trend_pullback_trades.csv (complete local copy)
results/trend_pullback_trades_part_001.csv, ... (5,000 trades per file for upload/analysis)
results/trend_pullback_trades_manifest.json
results/trend_pullback_summary.json
results/trend_pullback_equity.csv
"""

from pathlib import Path
import json
import math
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "data" / "raw" / "XAUUSD_m1_20211001_20261001.csv"
RESULTS = ROOT / "results"
TRADES_OUT = RESULTS / "trend_pullback_trades.csv"
TRADES_PART_PREFIX = "trend_pullback_trades_part_"
TRADES_PART_ROWS = 5000
TRADES_MANIFEST_OUT = RESULTS / "trend_pullback_trades_manifest.json"
SUMMARY_OUT = RESULTS / "trend_pullback_summary.json"
EQUITY_OUT = RESULTS / "trend_pullback_equity.csv"

ENTRIES_OUT = RESULTS / "trend_pullback_entries.csv"

FAST = 20
SLOW = 50
PULLBACK_LOOKBACK = 3
ATR_PERIOD = 14
SL_ATR = 1.0
TP_ATR = 1.5


def load_m1():
    df = pd.read_csv(INPUT)
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.set_index("Date").sort_index()
    df = df[~df.index.duplicated(keep="first")]
    # Use only the latest one-year window available in the master dataset.
    # The end is derived from the actual last timestamp so the test stays current
    # if the dataset is extended later.
    end = df.index.max()
    start = end - pd.DateOffset(years=1)
    df = df.loc[start:end]
    for c in ["Open", "High", "Low", "Close", "Volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["Open", "High", "Low", "Close"])
    return df


def make_m5(m1):
    # M1 timestamps are session-local/source timestamps; aggregation preserves
    # the source clock and creates a bar whenever at least one M1 exists.
    m5 = m1.resample("5min", label="left", closed="left").agg(
        Open=("Open", "first"),
        High=("High", "max"),
        Low=("Low", "min"),
        Close=("Close", "last"),
        Volume=("Volume", "sum"),
        M1Count=("Close", "count"),
    )
    m5 = m5.dropna(subset=["Open", "High", "Low", "Close"])
    # Do not invent missing market bars. A valid M5 bar must contain at least
    # one source M1 observation.
    return m5


def add_indicators(df):
    df = df.copy()
    df["EMA20"] = df["Close"].ewm(span=FAST, adjust=False).mean()
    df["EMA50"] = df["Close"].ewm(span=SLOW, adjust=False).mean()
    prev_close = df["Close"].shift(1)
    tr = pd.concat(
        [
            df["High"] - df["Low"],
            (df["High"] - prev_close).abs(),
            (df["Low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    df["ATR14"] = tr.rolling(ATR_PERIOD).mean()
    return df


def touches_zone(row):
    hi = max(row.EMA20, row.EMA50)
    lo = min(row.EMA20, row.EMA50)
    return row.Low <= hi and row.High >= lo


def bullish_pattern(bar, prev):
    rng = bar.High - bar.Low
    body = abs(bar.Close - bar.Open)
    lower = min(bar.Open, bar.Close) - bar.Low
    if rng <= 0 or body <= 0:
        return False
    engulf = (
        bar.Close > bar.Open
        and prev.Close < prev.Open
        and bar.Open <= prev.Close
        and bar.Close >= prev.Open
    )
    rejection = (
        bar.Close > bar.Open
        and lower >= body
        and (bar.Close - bar.Low) / rng >= 0.70
    )
    return bool(engulf or rejection)


def bearish_pattern(bar, prev):
    rng = bar.High - bar.Low
    body = abs(bar.Close - bar.Open)
    upper = bar.High - max(bar.Open, bar.Close)
    if rng <= 0 or body <= 0:
        return False
    engulf = (
        bar.Close < bar.Open
        and prev.Close > prev.Open
        and bar.Open >= prev.Close
        and bar.Close <= prev.Open
    )
    rejection = (
        bar.Close < bar.Open
        and upper >= body
        and (bar.High - bar.Close) / rng >= 0.70
    )
    return bool(engulf or rejection)


def backtest(df):
    trades = []
    entries = []
    equity = 0.0
    equity_curve = []
    position = None

    # Signal on closed bar i. Entry is modeled at that bar's close.
    # Exit is evaluated from subsequent M5 bars using OHLC.
    for i in range(SLOW + ATR_PERIOD + PULLBACK_LOOKBACK + 5, len(df)):
        row = df.iloc[i]
        ts = df.index[i]

        # Manage an existing trade before looking for a new one.
        if position is not None:
            hit_sl = row.Low <= position["sl"] if position["side"] == "LONG" else row.High >= position["sl"]
            hit_tp = row.High >= position["tp"] if position["side"] == "LONG" else row.Low <= position["tp"]

            if hit_sl or hit_tp:
                # Conservative same-bar ambiguity: if both are hit, count SL first.
                exit_price = position["sl"] if hit_sl else position["tp"]
                result_r = -1.0 if hit_sl else TP_ATR / SL_ATR
                exit_reason = "SL" if hit_sl else "TP"
                pnl_price = exit_price - position["entry"] if position["side"] == "LONG" else position["entry"] - exit_price
                position.update(
                    exit_time=ts,
                    exit=exit_price,
                    exit_reason=exit_reason,
                    result_r=result_r,
                    pnl_price=pnl_price,
                    duration_bars=i - position["entry_i"],
                )
                trades.append(position)
                equity += result_r
                position = None

        equity_curve.append({"Date": ts, "EquityR": equity})

        if position is not None:
            continue

        # Need enough prior closed bars for pullback.
        if i < PULLBACK_LOOKBACK + 1:
            continue

        long_side = row.EMA20 > row.EMA50
        short_side = row.EMA20 < row.EMA50
        if not (long_side or short_side) or not math.isfinite(row.ATR14) or row.ATR14 <= 0:
            continue

        pullback = False
        for j in range(i - PULLBACK_LOOKBACK, i):
            p = df.iloc[j]
            if not touches_zone(p):
                continue
            if long_side and p.Close >= min(p.EMA20, p.EMA50):
                pullback = True
                break
            if short_side and p.Close <= max(p.EMA20, p.EMA50):
                pullback = True
                break

        if not pullback:
            continue

        prev = df.iloc[i - 1]
        if long_side and bullish_pattern(row, prev):
            entry = row.Close
            sl = entry - row.ATR14 * SL_ATR
            tp = entry + row.ATR14 * TP_ATR
            position = {
                "entry_time": ts,
                "entry": entry,
                "side": "LONG",
                "sl": sl,
                "tp": tp,
                "atr": row.ATR14,
                "entry_i": i,
            }
            entries.append({**position})
        elif short_side and bearish_pattern(row, prev):
            entry = row.Close
            sl = entry + row.ATR14 * SL_ATR
            tp = entry - row.ATR14 * TP_ATR
            position = {
                "entry_time": ts,
                "entry": entry,
                "side": "SHORT",
                "sl": sl,
                "tp": tp,
                "atr": row.ATR14,
                "entry_i": i,
            }
            entries.append({**position})

    # Close an unfinished position at final available close, flagged separately.
    if position is not None:
        final_i = len(df) - 1
        final = df.iloc[final_i]
        pnl_price = final.Close - position["entry"] if position["side"] == "LONG" else position["entry"] - final.Close
        risk = position["atr"] * SL_ATR
        result_r = pnl_price / risk if risk > 0 else 0.0
        position.update(
            exit_time=df.index[final_i],
            exit=final.Close,
            exit_reason="END_OF_DATA",
            result_r=result_r,
            pnl_price=pnl_price,
            duration_bars=final_i - position["entry_i"],
        )
        trades.append(position)
        equity += result_r
        equity_curve.append({"Date": df.index[final_i], "EquityR": equity})

    return pd.DataFrame(trades), pd.DataFrame(equity_curve), pd.DataFrame(entries)


def main():
    RESULTS.mkdir(exist_ok=True)
    m1 = load_m1()
    m5 = add_indicators(make_m5(m1))
    trades, equity, entries = backtest(m5)

    if not trades.empty:
        trades["entry_time"] = pd.to_datetime(trades["entry_time"])
        trades["exit_time"] = pd.to_datetime(trades["exit_time"])
        wins = trades[trades.result_r > 0]
        losses = trades[trades.result_r < 0]
        gross_profit = wins.result_r.sum()
        gross_loss = abs(losses.result_r.sum())
        pf = gross_profit / gross_loss if gross_loss else float("inf")
        peak = equity.EquityR.cummax()
        dd = equity.EquityR - peak
        max_dd_r = abs(dd.min())
        summary = {
            "status": "PASS",
            "data": str(INPUT.relative_to(ROOT)),
            "m1_rows": int(len(m1)),
            "m5_bars": int(len(m5)),
            "period_start": str(m5.index.min()),
            "period_end": str(m5.index.max()),
            "parameters": {
                "ema_fast": FAST,
                "ema_slow": SLOW,
                "pullback_lookback_m5": PULLBACK_LOOKBACK,
                "atr_period": ATR_PERIOD,
                "sl_atr": SL_ATR,
                "tp_atr": TP_ATR,
                "entry": "confirmation_candle_close",
            },
            "trades": int(len(trades)),
            "wins": int((trades.result_r > 0).sum()),
            "losses": int((trades.result_r < 0).sum()),
            "win_rate_pct": float((trades.result_r > 0).mean() * 100),
            "total_r": float(trades.result_r.sum()),
            "avg_r": float(trades.result_r.mean()),
            "profit_factor": float(pf),
            "max_drawdown_r": float(max_dd_r),
            "avg_duration_m5": float(trades.duration_bars.mean()),
            "tp_count": int((trades.exit_reason == "TP").sum()),
            "sl_count": int((trades.exit_reason == "SL").sum()),
            "end_of_data_count": int((trades.exit_reason == "END_OF_DATA").sum()),
        }
        # Keep the complete CSV locally, but also split trades into small CSV parts.
        # The parts are the files intended for upload/analysis through GitHub.
        trades.to_csv(TRADES_OUT, index=False)
        part_files = []
        for part_no, start in enumerate(range(0, len(trades), TRADES_PART_ROWS), start=1):
            part = trades.iloc[start:start + TRADES_PART_ROWS]
            part_name = f"{TRADES_PART_PREFIX}{part_no:03d}.csv"
            part_path = RESULTS / part_name
            part.to_csv(part_path, index=False)
            part_files.append({
                "file": part_name,
                "rows": int(len(part)),
                "first_trade_index": int(start),
                "last_trade_index": int(start + len(part) - 1),
            })

        TRADES_MANIFEST_OUT.write_text(
            json.dumps({
                "source": "trend_pullback_trades.csv",
                "part_rows_limit": TRADES_PART_ROWS,
                "parts": part_files,
                "total_rows": int(len(trades)),
            }, indent=2),
            encoding="utf-8",
        )
        equity.to_csv(EQUITY_OUT, index=False)
        entries.to_csv(ENTRIES_OUT, index=False)
    else:
        summary = {
            "status": "PASS_NO_TRADES",
            "data": str(INPUT.relative_to(ROOT)),
            "m1_rows": int(len(m1)),
            "m5_bars": int(len(m5)),
            "period_start": str(m5.index.min()),
            "period_end": str(m5.index.max()),
            "parameters": {
                "ema_fast": FAST,
                "ema_slow": SLOW,
                "pullback_lookback_m5": PULLBACK_LOOKBACK,
                "atr_period": ATR_PERIOD,
                "sl_atr": SL_ATR,
                "tp_atr": TP_ATR,
                "entry": "confirmation_candle_close",
            },
            "trades": 0,
        }

    SUMMARY_OUT.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
