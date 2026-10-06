# PROJECT HISTORY — Trend + Pullback MT5

Repository: aalzaa/trading-bot-v2
Branch: trend-pullback-mt5
Instrument: XAUUSD
Master dataset: Dukascopy XAUUSD M1

> Append-only history. Never overwrite previous entries. Add every future modification, test, result, rejection, and accepted version.

## 2026-10-04 — Project creation

Created a separate Trend + Pullback trading-bot project.

Initial strategy:
- EMA20 and EMA50
- EMA20 > EMA50: bullish trend, search LONG
- EMA20 < EMA50: bearish trend, search SHORT
- Pullback toward the EMA20–EMA50 zone
- Bullish/bearish candlestick confirmation
- Entry concept: confirmation candle close
- Initial schedule: 24/5
- Instrument: XAUUSD
- Strategy timeframe: M5

Initial baseline exits:
- ATR14
- SL = 1.0 × ATR
- TP = 1.5 × ATR
- No break-even
- No trailing stop
- No news filter
- No session filter
- No spread filter
- No daily-loss filter
- Fixed lot 0.10 in the MT5 EA baseline
- One open position at a time

Goal: establish a clean baseline before adding or rejecting filters.

## 2026-10-04 — Data source

Dukascopy was selected as the XAUUSD historical data source.
The research architecture was changed to use XAUUSD M1 as the single master dataset. M5 and higher timeframes are derived internally from M1 when required.

Dataset: data/raw/XAUUSD_m1_20211001_20261001.csv
Coverage requested: 2021-10-01 → 2026-10-01
Raw market data is excluded from Git with /data/raw/.

## 2026-10-04 — Dataset quality check

Added research/dataset_quality_check.py.

Result: PASS.

Dataset:
- 1,772,270 rows
- Invalid dates: 0
- Duplicate rows: 0
- Duplicate timestamps: 0
- Non-monotonic timestamps: 0
- Missing OHLC values: 0
- Invalid numeric cells: 0
- Negative volume rows: 0
- Zero-volume rows: 0
- OHLC integrity errors: 0
- Backward time jumps: 0
- Median M1 gap: 1 minute
- Maximum gap: 4,382 minutes

Large gaps were not treated as automatic data errors because XAUUSD has market-session closures.

## 2026-10-05 — Extreme-range investigation

Added research/extreme_range_check.py.

Target: 2026-01-29 15:27:00
Target range: 134.120
Target body: 125.087

The target candle was investigated with surrounding M1 candles and the top 50 largest ranges.
The surrounding candles showed sustained extreme volatility rather than an isolated corrupted row. Other large ranges also occurred elsewhere in the dataset.

Decision: DO NOT modify or delete the raw dataset. Extreme volatility remains part of the historical sample unless a future investigation proves an observation is corrupted.

## 2026-10-05 — Initial MT5 EA

Created src/TrendPullbackEA.mq5.

Configuration:
- XAUUSD M5
- EMA20 / EMA50
- Pullback lookback: 3
- ATR14
- SL = 1.0 ATR
- TP = 1.5 ATR
- Fixed lot = 0.10
- One open strategy position
- 24/5
- No news/session/spread filters

Research note: the strategy defines entry at confirmation-candle close. In live MT5 execution, the candle must first close and the market order is sent on a following tick, so live fill can differ from the theoretical backtest.

## 2026-10-05 — First M1-based backtester

Created research/backtest_trend_pullback.py.
Commit: de7a10a4cf09ce092562e568f05649fa6992ae68

The backtester reads the M1 master dataset and aggregates it internally to M5.

Baseline rules:
- EMA20 > EMA50: LONG bias
- EMA20 < EMA50: SHORT bias
- Previous 3 closed M5 candles checked for pullback
- Price must touch the EMA20–EMA50 zone
- Engulfing or rejection confirmation
- Entry at confirmation candle close
- ATR14
- SL = 1.0 ATR
- TP = 1.5 ATR
- One position at a time
- No BE/trailing/partial exits
- If SL and TP are both touched in the same M5 bar, SL is assigned first conservatively

Outputs:
- results/trend_pullback_trades.csv
- results/trend_pullback_summary.json
- results/trend_pullback_equity.csv

STATUS: Backtester created and committed. The first numerical strategy test has NOT yet been completed. The next history entry must contain the actual baseline results after executing the backtest.

## Test protocol

Every test must record:
1. Exact strategy/code version
2. Dataset and period
3. Parameters
4. Number of trades
5. Win rate
6. Total R
7. Average R
8. Profit Factor
9. Maximum drawdown
10. TP/SL counts
11. Average duration
12. Relevant additional metrics
13. ACCEPTED / REJECTED / NEEDS FURTHER TESTING

Do not add filters simply because they sound useful. Each change must be tested against the baseline and retained only when supported by results without obvious overfitting.

## Future research queue

- SL sweep
- TP/RR sweep
- Fixed-distance vs ATR exits
- Structure-based exits
- Pullback lookback sweep
- EMA parameter sweep
- Confirmation-pattern comparison
- Session/hour analysis
- Spread sensitivity
- News/event analysis
- Risk-based position sizing
- Out-of-sample validation
- Walk-forward testing
- Robustness across market regimes
- MT5/demo execution validation

Never overwrite previous results or history.

## Current reference version

TREND + PULLBACK — BASELINE

Status: Research baseline / pending first numerical backtest.

XAUUSD | M1 master | M5 strategy | EMA20/50 | 3-bar pullback | engulfing/rejection | ATR14 | SL 1.0 ATR | TP 1.5 ATR | 24/5 | one position | no additional filters
## 2026-10-05 — Research protocol: fixed-entry exit/MFE-MAE/time/regime studies

After the baseline result, the next research sequence was defined:
1. Exit optimization using the exact same baseline entry timestamps.
2. MFE/MAE analysis from the M1 master dataset, including time to MFE and time to MAE.
3. Hour/time filters, with particular attention to the 12:00 hour.
4. Regime analysis by year and month.

research/backtest_trend_pullback.py was updated to export trend_pullback_entries.csv, a fixed baseline entry ledger.
research/strategy_research.py was added. It evaluates exit variants from the fixed entry ledger and does not regenerate strategy signals. It also produces MFE/MAE and time/regime reports.

The exit sweep is deliberately performed before selecting a time filter. Research outputs remain separate from the final MT5 LIVE code.

Status: TESTS PREPARED — numerical results pending local execution against the master M1 dataset.


## 2026-10-06 — Final research setup: EMA20/EMA50 distance + 3-year combined backtest
- EMA50 reaction study updated to retain both EMA20 and EMA50 distance for every eligible entry.
- Distances are recorded in price units and ATR-normalized units, signed and absolute.
- Added distance buckets for EMA20 and EMA50 to study how entry quality changes with distance from both averages.
- The EMA50 reaction study now uses the combined 3-year window 2023-09-30 through 2026-09-30.
- Baseline trend-pullback backtest now uses the same combined 3-year window rather than a single rolling year.
- Trade CSV output remains split into 5,000-trade parts for manageable upload/analysis, with a manifest.
- Research-only changes do not modify the MT5 LIVE EA.
