# Trading Bot V2 — Trend + Pullback MT5

Research and development project for an XAUUSD price-action trading bot.

## Project scope
- Instrument: XAUUSD
- Platform: MetaTrader 5 (MT5)
- Master historical dataset: Dukascopy XAUUSD M1
- Strategy timeframe: M5
- Research is performed from the M1 master dataset, with M5 candles derived internally.
- The bot is based on price action, EMA20/EMA50 trend structure, pullbacks and engulfing confirmation.
- No CME/MNQ data converter is part of this project.
- This project is separate from the previous V1 order-flow/Binance bot.

## Current research strategy
- EMA20 > EMA50: LONG bias
- EMA20 < EMA50: SHORT bias
- Pullback lookback: 3 closed M5 candles
- Engulfing confirmation only
- Rejection patterns excluded
- EMA50-touching signal candles excluded
- Confirmation close within 0.75 ATR of EMA20
- Confirmation close within 1.20 ATR of EMA50
- RSI14 is recorded for research/diagnostics only; RSI entry filter rejected
- Current hour-filter research excludes 02:00, 07:00, 11:00, 19:00 and 20:00
- The current research compares the selected 10 ATR/RR configurations

## Research protocol
Every strategy modification is tested against the relevant baseline and recorded in PROJECT_HISTORY.md.

Filters are not added merely because they sound useful. A filter is retained only when comparative results and robustness checks support it.

## Current status
RSI FILTER: REJECTED
HOUR FILTER: UNDER TEST
Final LIVE configuration: NOT YET SELECTED

The MT5 LIVE/prop version will only be selected after backtest, robustness, out-of-sample/walk-forward and demo execution validation.
