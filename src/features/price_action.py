"""Pure candle/price-action features. No volume or order-flow inputs."""
from __future__ import annotations
import pandas as pd

def add_price_action_features(df: pd.DataFrame) -> pd.DataFrame:
    required = {"open", "high", "low", "close"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing OHLC columns: {sorted(missing)}")
    out = df.copy()
    rng = out["high"] - out["low"]
    out["body"] = (out["close"] - out["open"]).abs()
    out["upper_wick"] = out["high"] - out[["open", "close"]].max(axis=1)
    out["lower_wick"] = out[["open", "close"]].min(axis=1) - out["low"]
    out["body_ratio"] = out["body"].div(rng.replace(0, pd.NA))
    out["close_location"] = (out["close"] - out["low"]).div(rng.replace(0, pd.NA))
    out["bullish"] = out["close"] > out["open"]
    out["bearish"] = out["close"] < out["open"]
    out["prev_high"] = out["high"].shift(1)
    out["prev_low"] = out["low"].shift(1)
    return out
