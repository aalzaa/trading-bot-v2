# Trading Bot V2 — MNQ CME

New standalone volumetric futures trading bot for CME Micro E-mini Nasdaq-100 (MNQ).

## Project rules
- Native CME data only.
- No Data Converter.
- New codebase; do not copy the V1 strategy implementation.
- Initial operational timeframe: 5 minutes.
- Entry research will use Delta, CVD, Absorption Efficiency, Volume, Big Trades, VWAP and POC-related features.
- Parameter thresholds will be derived from MNQ backtests rather than copied from BTC.
- No weekend trading.
- Demo/prop integration comes only after backtest and forward validation.

## Planned pipeline
CME MNQ data → feature calculation → entry research → backtest → parameter study → demo prop → live prop evaluation.
