#!/usr/bin/env python3
"""
XAUUSD M1 dataset quality checker.

Default input:
    data/raw/XAUUSD_m1_20211001_20261001.csv

Usage:
    python research/dataset_quality_check.py
    python research/dataset_quality_check.py --input path/to/file.csv
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


REQUIRED = ["Date", "Open", "High", "Low", "Close", "Volume"]


def pct(x: float) -> str:
    return f"{x:.4f}%"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        default="data/raw/XAUUSD_m1_20211001_20261001.csv",
        help="CSV path",
    )
    parser.add_argument(
        "--output",
        default="results/dataset_quality_report.txt",
        help="Human-readable report path",
    )
    parser.add_argument(
        "--json-output",
        default="results/dataset_quality_report.json",
        help="Machine-readable report path",
    )
    args = parser.parse_args()

    path = Path(args.input)
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")

    out_txt = Path(args.output)
    out_json = Path(args.json_output)
    out_txt.parent.mkdir(parents=True, exist_ok=True)
    out_json.parent.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(path)

    report: dict = {
        "file": str(path),
        "status": "PASS",
        "errors": [],
        "warnings": [],
    }

    # ---------- schema ----------
    missing_cols = [c for c in REQUIRED if c not in df.columns]
    extra_cols = [c for c in df.columns if c not in REQUIRED]
    report["schema"] = {
        "columns": list(df.columns),
        "missing_required": missing_cols,
        "extra_columns": extra_cols,
    }

    if missing_cols:
        report["errors"].append(f"Missing required columns: {missing_cols}")
        report["status"] = "FAIL"
        write_reports(report, out_txt, out_json)
        raise SystemExit(1)

    # ---------- parsing ----------
    dt = pd.to_datetime(df["Date"], errors="coerce")
    report["rows"] = int(len(df))
    report["parse"] = {
        "invalid_dates": int(dt.isna().sum()),
        "duplicate_rows": int(df.duplicated().sum()),
        "duplicate_timestamps": int(dt.duplicated().sum()),
        "non_monotonic_timestamps": int((dt.diff().dropna() < pd.Timedelta(0)).sum()),
    }

    numeric = df[["Open", "High", "Low", "Close", "Volume"]].apply(
        pd.to_numeric, errors="coerce"
    )
    numeric_bad = int(numeric.isna().sum().sum())
    report["numeric"] = {
        "invalid_numeric_cells": numeric_bad,
        "missing_values_by_column": {
            c: int(numeric[c].isna().sum()) for c in numeric.columns
        },
    }

    if report["parse"]["invalid_dates"]:
        report["errors"].append("Invalid Date values found.")
    if report["parse"]["duplicate_rows"]:
        report["errors"].append("Duplicate rows found.")
    if report["parse"]["duplicate_timestamps"]:
        report["warnings"].append("Duplicate timestamps found.")
    if report["parse"]["non_monotonic_timestamps"]:
        report["errors"].append("Timestamps are not strictly chronological.")
    if numeric_bad:
        report["errors"].append("Invalid/missing numeric OHLCV values found.")

    # ---------- OHLC integrity ----------
    o, h, l, c, v = [numeric[x] for x in ["Open", "High", "Low", "Close", "Volume"]]

    bad_high = ((h < o) | (h < c) | (h < l))
    bad_low = ((l > o) | (l > c) | (l > h))
    non_positive_price = ((o <= 0) | (h <= 0) | (l <= 0) | (c <= 0))
    negative_volume = v < 0
    zero_volume = v == 0

    report["ohlc_integrity"] = {
        "high_below_required_value_count": int(bad_high.fillna(False).sum()),
        "low_above_required_value_count": int(bad_low.fillna(False).sum()),
        "non_positive_price_rows": int(non_positive_price.fillna(False).sum()),
        "negative_volume_rows": int(negative_volume.fillna(False).sum()),
        "zero_volume_rows": int(zero_volume.fillna(False).sum()),
    }

    if bad_high.any() or bad_low.any() or non_positive_price.any():
        report["errors"].append("OHLC integrity violations found.")
    if negative_volume.any():
        report["errors"].append("Negative volume values found.")

    # ---------- time coverage ----------
    clean = pd.DataFrame(
        {
            "Date": dt,
            "Open": o,
            "High": h,
            "Low": l,
            "Close": c,
            "Volume": v,
        }
    ).dropna(subset=["Date"])

    clean = clean.sort_values("Date").reset_index(drop=True)

    if len(clean):
        diffs = clean["Date"].diff().dropna()
        one_minute = pd.Timedelta(minutes=1)
        gaps = diffs[diffs > one_minute]
        backwards = diffs[diffs < pd.Timedelta(0)]

        report["coverage"] = {
            "first_timestamp": str(clean["Date"].iloc[0]),
            "last_timestamp": str(clean["Date"].iloc[-1]),
            "calendar_days": int(
                (clean["Date"].dt.normalize().iloc[-1]
                 - clean["Date"].dt.normalize().iloc[0]).days + 1
            ),
            "unique_dates": int(clean["Date"].dt.date.nunique()),
            "unique_months": int(clean["Date"].dt.to_period("M").nunique()),
            "unique_years": int(clean["Date"].dt.year.nunique()),
            "min_bar_gap_minutes": float(diffs.min().total_seconds() / 60) if len(diffs) else 0,
            "median_bar_gap_minutes": float(diffs.median().total_seconds() / 60) if len(diffs) else 0,
            "max_bar_gap_minutes": float(diffs.max().total_seconds() / 60) if len(diffs) else 0,
            "gaps_gt_1m": int(len(gaps)),
            "largest_gap_minutes": float(gaps.max().total_seconds() / 60) if len(gaps) else 0,
            "backward_time_jumps": int(len(backwards)),
        }

        # Gaps are not automatically errors because XAUUSD has market closures/weekends.
        if len(backwards):
            report["errors"].append("Backward timestamp jumps found.")

        daily = clean.assign(day=clean["Date"].dt.date).groupby("day").size()
        report["daily_bar_stats"] = {
            "days": int(len(daily)),
            "min_bars_per_day": int(daily.min()) if len(daily) else 0,
            "median_bars_per_day": float(daily.median()) if len(daily) else 0,
            "mean_bars_per_day": float(daily.mean()) if len(daily) else 0,
            "max_bars_per_day": int(daily.max()) if len(daily) else 0,
        }

        # Month/year coverage summary.
        month_counts = clean.assign(
            month=clean["Date"].dt.to_period("M").astype(str)
        ).groupby("month").size()
        report["monthly_bar_stats"] = {
            "min_bars": int(month_counts.min()),
            "median_bars": float(month_counts.median()),
            "max_bars": int(month_counts.max()),
            "months_below_1000_bars": int((month_counts < 1000).sum()),
        }

    # ---------- market statistics ----------
    ret = clean["Close"].pct_change()
    candle_range = clean["High"] - clean["Low"]
    body = (clean["Close"] - clean["Open"]).abs()

    report["market_stats"] = {
        "price_min": float(clean["Low"].min()),
        "price_max": float(clean["High"].max()),
        "median_close": float(clean["Close"].median()),
        "median_m1_range": float(candle_range.median()),
        "mean_m1_range": float(candle_range.mean()),
        "median_body": float(body.median()),
        "mean_body": float(body.mean()),
        "median_volume": float(clean["Volume"].median()),
        "mean_volume": float(clean["Volume"].mean()),
        "return_mean_pct": float(ret.mean() * 100),
        "return_std_pct": float(ret.std() * 100),
    }

    # ---------- outlier checks ----------
    # Robust range outliers using MAD.
    med_range = candle_range.median()
    mad = (candle_range - med_range).abs().median()
    if mad > 0:
        robust_z = 0.6745 * (candle_range - med_range) / mad
        range_outliers = robust_z.abs() > 10
    else:
        range_outliers = pd.Series(False, index=clean.index)

    vol_med = clean["Volume"].median()
    volume_spikes = clean["Volume"] > vol_med * 20 if vol_med > 0 else pd.Series(False, index=clean.index)

    report["outliers"] = {
        "extreme_range_count_robust_z_gt_10": int(range_outliers.sum()),
        "volume_gt_20x_median_count": int(volume_spikes.sum()),
        "largest_range": float(candle_range.max()),
        "largest_range_timestamp": str(clean.loc[candle_range.idxmax(), "Date"]),
        "largest_volume": float(clean["Volume"].max()),
        "largest_volume_timestamp": str(clean.loc[clean["Volume"].idxmax(), "Date"]),
    }

    # ---------- weekend / hour profile ----------
    dow = clean["Date"].dt.day_name().value_counts().to_dict()
    hours = clean["Date"].dt.hour.value_counts().sort_index().to_dict()
    report["time_profile"] = {
        "bars_by_weekday": {str(k): int(v) for k, v in dow.items()},
        "bars_by_hour": {str(int(k)): int(v) for k, v in hours.items()},
    }

    # ---------- final status ----------
    if report["errors"]:
        report["status"] = "FAIL"
    elif report["warnings"]:
        report["status"] = "PASS_WITH_WARNINGS"

    write_reports(report, out_txt, out_json)

    print_report(report)
    print()
    print(f"TEXT REPORT : {out_txt}")
    print(f"JSON REPORT : {out_json}")


def write_reports(report: dict, out_txt: Path, out_json: Path) -> None:
    out_json.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        "XAUUSD M1 DATASET QUALITY REPORT",
        "=" * 34,
        f"STATUS: {report['status']}",
        f"FILE: {report['file']}",
        f"ROWS: {report.get('rows', 0):,}",
        "",
        "ERRORS",
        "------",
    ]
    lines += [f"- {x}" for x in report["errors"]] or ["- None"]
    lines += ["", "WARNINGS", "--------"]
    lines += [f"- {x}" for x in report["warnings"]] or ["- None"]

    for section in [
        "schema",
        "parse",
        "numeric",
        "ohlc_integrity",
        "coverage",
        "daily_bar_stats",
        "monthly_bar_stats",
        "market_stats",
        "outliers",
    ]:
        if section in report:
            lines += ["", section.upper(), "-" * len(section)]
            for k, v in report[section].items():
                lines.append(f"{k}: {v}")

    out_txt.write_text("\n".join(lines) + "\n", encoding="utf-8")


def print_report(report: dict) -> None:
    print("\n" + "=" * 60)
    print("XAUUSD M1 DATASET QUALITY REPORT")
    print("=" * 60)
    print(f"STATUS: {report['status']}")
    print(f"ROWS:   {report.get('rows', 0):,}")

    print("\n[ERRORS]")
    for x in report["errors"] or ["None"]:
        print(f"  - {x}")

    print("\n[WARNINGS]")
    for x in report["warnings"] or ["None"]:
        print(f"  - {x}")

    for section in ["coverage", "ohlc_integrity", "market_stats", "outliers"]:
        if section in report:
            print(f"\n[{section.upper()}]")
            for k, v in report[section].items():
                print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
