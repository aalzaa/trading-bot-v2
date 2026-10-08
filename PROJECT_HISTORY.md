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


## 2026-10-06 — Research branch: engulfing-only + ATR/RR + RSI capture

Created branch: engulfing-atr-rsi-research.

The EMA50-stop version is REJECTED and is not carried forward.

New research rules:
- Entry confirmation is Engulfing only: bullish engulfing for LONG, bearish engulfing for SHORT.
- Rejection patterns are excluded.
- An engulfing candle reacting at EMA50 remains valid when its candle BODY does not cross EMA50; EMA50 is not used as the stop level.
- Exits return to ATR-based stop/target research.
- Multiple SL-ATR values and RR values are tested from the exact same entry set.
- LONG/SHORT is recorded for every trade.
- Exact entry timestamp, hour, minute and session are recorded for later session analysis.
- EMA20 and EMA50 distances are recorded in price and ATR-normalized form, signed and absolute.
- RSI14 is recorded for every trade; no RSI threshold/filter is applied yet.
- Historical news context is recorded when a real data/news/xauusd_news.csv dataset is available; no news event is invented when unavailable.
- MFE/MAE are corrected to use a finite window ending at each trade's baseline exit, instead of scanning to the end of the M1 dataset.

Research output is separate from the MT5 LIVE bot.
Status: NEW RESEARCH VERSION — pending local execution and analysis.


## 2026-10-07 — Research optimization branch: full backtest/research acceleration

Branch: engulfing-atr-rsi-research-optimized.

The optimization branch was expanded beyond the ATR/RR exit engine so the full research pipeline is faster while preserving the same strategy rules and conservative execution conventions.

Optimizations implemented:
- Faster M1 loading using only required columns and avoiding unnecessary sorting/copies when the source is already ordered.
- Vectorized M5 entry generation for EMA20/EMA50 bias, 3-bar pullback detection, Engulfing confirmation, ATR and RSI calculations.
- EMA50-touch exclusion remains exactly active.
- Vectorized historical-news tagging using sorted timestamp search rather than scanning the full news table for every trade.
- Batch/JIT MFE/MAE calculation bounded by each trade's baseline exit, preserving the previous finite-window definition.
- ATR/RR exit grid remains the authoritative backtest engine and is reused by all downstream analyses.
- Added deterministic on-disk caching of the numerical ATR/RR exit grid. The cache is invalidated when the dataset signature, period, entry ledger or grid parameters change.
- No strategy filter, entry condition, SL/TP rule, same-candle convention, or research metric was intentionally changed by the optimization.

Numba remains the preferred acceleration path, with the existing exact-rule Python fallback retained for environments where Numba is unavailable. Current Numba documentation confirms Python 3.14 support in modern releases.

Status: OPTIMIZED RESEARCH PIPELINE — pending local runtime/equivalence verification.


## 2026-10-08 — EMA proximity + full ATR/RR RSI research
- New research branch: `engulfing-ema-close-rsi-research`, based on the optimized research pipeline.
- Entry rule tightened: confirmation candle close must be within **0.75 ATR of EMA20** AND **1.20 ATR of EMA50**.
- Existing rules preserved: EMA20/EMA50 trend bias, 3-candle pullback, Engulfing only, rejection excluded, EMA50-touching signal candles excluded.
- Full ATR/RR grid remains unchanged: SL 0.50–5.00 ATR and RR 0.50–3.00.
- Every resolved ATR/RR trade now retains exact RSI14, hour, minute, session, side, EMA20/EMA50 distances and entry metadata in `engulfing_all_atr_rr_trades.csv`.
- Added `engulfing_rsi_by_atr_rr.csv` and `engulfing_hour_by_atr_rr.csv` for aggregate analysis without discarding raw trade-level information.
- Optimization preserved: existing Numba exit grid/cache and vectorized/batched research pipeline are reused; no strategy rule outside the requested EMA-proximity filter was removed or simplified.
- Research-only; not the final MT5 LIVE bot.


## 2026-10-08 — Split full ATR/RR trade-level output for GitHub compatibility

The research script no longer writes the monolithic `engulfing_all_atr_rr_trades.csv`.

Instead:
- Full trade-level data is written to `results/engulfing_atr_rsi/engulfing_all_atr_rr_trades/`.
- Data is grouped by every SL/RR combination.
- Each combination is automatically split into additional numbered parts if needed.
- Each part is capped below 20 MB, leaving headroom under GitHub's 25 MB web-upload limit.
- No columns or trade rows are intentionally discarded by the split.
- The aggregate files `engulfing_rsi_by_atr_rr.csv` and `engulfing_hour_by_atr_rr.csv` remain unchanged.
- The large numerical exit-grid cache remains a local-only acceleration artifact and is not required for final analysis.

This change affects only result-file storage, not entry logic, ATR/RR calculations, RSI values, timestamps, sessions, exits, or any research metric.

Status: RESEARCH OUTPUT STORAGE UPDATED — pending local runtime verification.


## 2026-10-08 — Directional RSI entry filter research
- New research branch: `engulfing-rsi-filter-research`, based on `engulfing-ema-close-rsi-research`.
- Added the requested RSI entry filter only; all other strategy rules remain unchanged.
- LONG entries require RSI14 **47.0–58.0 inclusive**.
- SHORT entries require RSI14 **42.0–51.0 inclusive**.
- EMA20/EMA50 bias, 3-candle pullback, Engulfing-only confirmation, EMA50-touch exclusion, and EMA20/EMA50 proximity limits remain active.
- Full SL 0.50–5.00 ATR × RR 0.50–3.00 grid remains unchanged.
- Exit-grid cache version was incremented so the new filtered entry set cannot reuse the previous unfiltered cache.
- The next analysis target is the **hour-of-day performance of the filtered strategy**, with LONG/SHORT and ATR/RR breakdowns where useful.
- Research-only; this is not the final MT5 LIVE bot.

Status: RSI FILTER TEST READY — pending local execution and hourly analysis.


## 2026-10-08 — Hour-filter research branch
- New research branch: `engulfing-hour-filter-research`, based on the RSI-filter research version.
- Removed the RSI entry filter. RSI14 remains recorded only as a diagnostic value; it no longer determines whether an entry is allowed.
- Added an entry hour filter excluding **02:00, 07:00, 11:00, 19:00 and 20:00**.
- These five hours were selected because they were negative across all 10 tested ATR/RR configurations in the previous hourly cross-check.
- The same 10 selected ATR/RR combinations remain unchanged.
- EMA20/EMA50 bias, 3-candle pullback, Engulfing-only confirmation, EMA50-touch exclusion and EMA20/EMA50 proximity limits remain unchanged.
- Research-only; not the final MT5 LIVE bot.

Status: HOUR FILTER TEST READY — pending local execution and robustness analysis.
