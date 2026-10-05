#!/usr/bin/env python3
"""Inspect suspicious XAUUSD M1 range outliers around the largest candles."""

from __future__ import annotations

import argparse
from pathlib import Path
import pandas as pd

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", default="data/raw/XAUUSD_m1_20211001_20261001.csv")
    p.add_argument("--timestamp", default="2026-01-29 15:27:00")
    p.add_argument("--window", type=int, default=10)
    p.add_argument("--top", type=int, default=50)
    args = p.parse_args()

    path = Path(args.input)
    df = pd.read_csv(path)
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    for c in ["Open","High","Low","Close","Volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["Date","Open","High","Low","Close","Volume"]).sort_values("Date").reset_index(drop=True)
    df["Range"] = df["High"] - df["Low"]
    df["Body"] = (df["Close"] - df["Open"]).abs()

    target = pd.Timestamp(args.timestamp)
    idx = (df["Date"] - target).abs().idxmin()
    lo = max(0, idx - args.window)
    hi = min(len(df), idx + args.window + 1)

    print("=" * 90)
    print("XAUUSD M1 EXTREME-RANGE INSPECTION")
    print("=" * 90)
    print(f"Target: {target}")
    print(f"Nearest row: {df.loc[idx, 'Date']}")
    print(f"Distance: {abs(df.loc[idx, 'Date'] - target)}")
    print()
    print("TARGET WINDOW")
    print(df.loc[lo:hi-1, ["Date","Open","High","Low","Close","Volume","Range","Body"]].to_string(index=False))

    print()
    print(f"TOP {args.top} LARGEST RANGES")
    cols = ["Date","Open","High","Low","Close","Volume","Range","Body"]
    print(df.nlargest(args.top, "Range")[cols].to_string(index=False))

    print()
    print("CONTEXT CHECK")
    row = df.loc[idx]
    print(f"Target range: {row['Range']:.5f}")
    print(f"Target body : {row['Body']:.5f}")
    print(f"Target OHLC : O={row['Open']:.5f} H={row['High']:.5f} L={row['Low']:.5f} C={row['Close']:.5f}")
    print(f"Target volume: {row['Volume']:.5f}")

if __name__ == "__main__":
    main()
