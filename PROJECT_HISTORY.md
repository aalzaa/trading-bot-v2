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


## 2026-10-08 — Consolidated research record and results2 upload

Branch: `results2`.

This entry consolidates the numerical research performed during the Trend + Pullback / Engulfing research cycle so the project history does not lose tests performed before the results2 branch was created.

### Historical baseline: original Trend + Pullback strategy

Initial strategy:
- XAUUSD M1 master data aggregated to M5.
- EMA20/EMA50 trend bias.
- 3 closed M5 candle pullback lookback.
- Pullback into EMA20–EMA50 zone.
- Confirmation initially allowed Engulfing OR Rejection.
- ATR14.
- Baseline exit: SL 1 ATR, TP 1.5 ATR.
- Entry at confirmation candle close.
- No BE, trailing, news, session, spread or additional filters.

Five-year baseline result:
- 18,352 trades.
- Win rate: 39.46%.
- Total: -247R.
- Profit Factor: 0.978.
- Max drawdown: 303.5R.
- Average duration: 5.04 M5 bars.
- LONG: 9,570 trades, ~39.43% WR, -137.5R, PF ~0.976.
- SHORT: 8,782 trades, ~39.50% WR, -109.5R, PF ~0.979.
- Maximum loss streak: 19.
- Maximum win streak: 9.

Five-year yearly results:
- 2021: +23R, PF 1.042.
- 2022: -179.5R, PF 0.924.
- 2023: -61R, PF 0.972.
- 2024: -7.5R, PF 0.997.
- 2025: +48.5R, PF 1.023.
- 2026: -70.5R, PF 0.958.

Duration study:
- 1 M5 bar: 3,294 trades, 26.20% WR, -1,136.5R, PF 0.533.
- 2–3 bars: 6,563 trades, 36.32% WR, -603R, PF 0.856.
- 4–5 bars: 3,395 trades, 44.83% WR, +410R, PF 1.219.
- 6–10 bars: 3,328 trades, 48.44% WR, +702R, PF 1.409.
- 11–20 bars: 1,361 trades, 47.24% WR, +246.5R, PF 1.343.
- 21–50 bars: 362 trades, 54.97% WR, +135.5R, PF 1.831.
- 51+ bars: 49 trades, 38.78% WR, -1.5R, PF 0.950.

Conclusion: immediate stops were a major weakness; trades surviving roughly 15–30 minutes performed materially better. This was a research observation, not automatically promoted to a filter.

### Three-year combined baseline

Fixed comparison window:
`2023-09-30 00:00:00` → `2026-09-30 23:59:59`.

Original Engulfing + Rejection baseline was approximately 10.9k trades, ~39.8% WR and about -57R overall, with PF around 0.98.

Three rolling-year windows:
- 2023/24: ~3,635 trades, -55R, PF ~0.975, DD 98.5R.
- 2024/25: ~3,613 trades, +104.5R, PF ~1.049, DD 50.5R.
- 2025/26: ~3,644 trades, -106.5R, PF ~0.952, DD 170R.

### Original ATR/RR exit sweep

Fixed-entry sweep:
- SL ATR: 0.50, 0.75, 1.00, 1.25, 1.50, 2.00.
- TP ATR: 0.75, 1.00, 1.25, 1.50, 2.00, 2.50, 3.00.

Key results:
- SL 2 ATR was materially better than 0.50–1.50 ATR.
- SL 2 / TP 2.5 ATR (RR 1.25): detailed run 10,885 trades, 44.52% WR, PF ~1.003, +18.77R.
- SL 2 / TP 3 ATR (RR 1.5): PF ~1.003, +17.77R.
- These were weak positive results and were not treated as a robust edge.

### Original time study

Best individual hours were approximately:
- 05 PF 1.156
- 08 PF 1.158
- 15 PF 1.156
- 01 PF 1.117
- 06 PF 1.114
- 13 PF 1.069
- 14 PF 1.057
- 23 PF 1.055

Weak hours:
- 19 PF 0.772
- 21 PF 0.750
- 09 PF 0.852
- 11 PF 0.876
- 17 PF 0.882
- 02 PF 0.890

Hour 12 was not robustly bad across years. A broad hand-selected exclusion set produced roughly +149R / PF 1.032 but was rejected as likely overfit and was not implemented.

### Original regime/month study

Weak periods included:
- September 2024: -58R, PF 0.721.
- November 2025: -32.5R, PF 0.820.
- December 2025: -28R, PF 0.859.
- May 2026: -38.5R, PF 0.797.
- July 2026: -45R, PF 0.789.

No regime/month filter was promoted.

### EMA distance study

Original three-year baseline showed strong deterioration as entries moved farther from the EMAs.

EMA20 absolute distance:
- 0–0.25 ATR: PF 0.819, -102.5R.
- 0.25–0.50: PF 0.930, -40R.
- 0.50–0.75: PF 0.828, -116.5R.
- 0.75–1.00: PF 0.736, -143.5R.
- 1.00–1.50: PF 0.602, -270R.
- 1.50–2.00: PF 0.353, -165R.
- 2.00–3.00: PF 0.248, -109R.
- 3.00–5.00: PF 0.075, -18.5R.
- 5+ ATR: PF 0, -2R.

EMA50 absolute distance:
- 0–0.25 ATR: PF 1.167, +4.5R, only 48 trades.
- 0.25–0.50: PF 0.724, -23.5R.
- 0.50–0.75: PF 0.914, -15R.
- 0.75–1.00: PF 0.978, -7R.
- 1.00–1.50: PF 0.924, -67R.
- 1.50–2.00: PF 0.668, -267.5R.
- 2.00–3.00: PF 0.518, -430R.
- 3.00–5.00: PF 0.426, -151.5R.
- 5+ ATR: PF 0.231, -10R.

This motivated a dedicated EMA-proximity test but the tiny closest EMA50 bucket was not treated as proof by itself.

### EMA50 reaction / EMA50-stop test — REJECTED

Focused reaction study:
- ~1,853 setups.
- Best tested result remained negative, approximately PF 0.774 at 0.5 ATR buffer / RR 3.
- Engulfing at 0.5 ATR / RR 1: approximately PF 0.958, -11R.
- Rejection at 0.5 ATR / RR 1: approximately PF 0.621, about -312R.
- LONG/SHORT had no decisive advantage.
- NY/NY-LATE were relatively better but still negative.

A later result file for the EMA50 reaction variant contained 5,122 trades, 32.45% WR, -967R, PF 0.721.

Decision: **PERMANENTLY REJECTED.** EMA50 is not used as the stop level. Later research excludes signal candles touching EMA50 completely.

### Engulfing-only ATR/RR/RSI research

Branch: `engulfing-atr-rsi-research`.

Rules:
- Engulfing only.
- Rejection excluded.
- EMA20/EMA50 trend bias.
- 3-bar pullback.
- RSI14 recorded but no threshold.
- Exact entry time/hour/minute/session/side recorded.
- EMA distances recorded signed/absolute and ATR-normalized.
- ATR/RR variants use identical entry timestamps.
- MFE/MAE bounded by baseline exit.
- Historical news only when actual historical news data exists.

Earlier pre-proximity run:
- ~7,364 entries.
- Baseline 1 ATR / RR 1.5: -1,674R, 30.91% WR, PF 0.671.
- Best tested region was SL 2 ATR / RR 3: approximately +137R, PF 1.025.
- SL 2 ATR was negative for RR 0.5 through 2.5 and positive only at RR 3.
- LONG and SHORT were both negative.
- NY was least negative but remained negative.

### RSI study before proximity tightening

Baseline-exit RSI bins:
- <30: PF ~0.132, -29.5R.
- 30–35: PF ~0.361, -53R.
- 35–40: PF ~0.563, -128R.
- 40–45: PF ~0.709, -191.5R.
- 45–50: PF ~0.859, -73.5R.
- 50–55: PF ~0.914, -49.5R.
- 55–60: PF ~0.769, -183R.
- 60–65: PF ~0.504, -189R.
- 65–70: PF ~0.506, -42.5R.
- 70–75: PF ~0.339, -20.5R.
- 75+: PF 0, -7R.

Decision: no RSI filter was accepted because these bins were tied to a specific exit configuration and did not prove a robust universal entry threshold.

### Optimization work

Branch: `engulfing-atr-rsi-research-optimized`.

Implemented:
- faster M1 loading;
- vectorized entry generation;
- vectorized news tagging;
- batch/JIT MFE/MAE;
- Numba ATR/RR exit-grid engine;
- exact Python fallback;
- deterministic exit-grid cache;
- reuse of the same exit grid for all downstream analyses;
- corrected granular EMA distance bins;
- fixed grid-results scope/runtime bugs.

Goal: reduce the previous 3–4 hour research runtime without changing strategy logic or research metrics.

### EMA proximity test

Branch: `engulfing-ema-close-rsi-research`.

New rule:
- entry close must be within **0.75 ATR of EMA20**;
- AND within **1.20 ATR of EMA50**.

Preserved:
- EMA20/EMA50 bias;
- 3-bar pullback;
- Engulfing only;
- rejection excluded;
- EMA50-touching signal candles excluded;
- EMA50 not used as SL;
- RSI14 recorded only;
- exact hour/minute/session/side and EMA distances retained;
- full SL/RR grid retained.

Trade-level output was subsequently split by SL/RR and automatically kept below 20 MB per file, without dropping rows or columns.

### Latest executed test — results2

Branch: `results2`.
Period: **2023-09-30 00:00:00 → 2026-09-30 23:59:59**.
M1 rows: **1,063,252**.
M5 bars: **212,698**.
Eligible entries: **1,287**.
Historical news data: **not available**.
Numba: **enabled**.
Grid: **11 SL values × 8 RR values = 88 combinations**.

Entry rules:
- EMA20 > EMA50 for LONG / EMA20 < EMA50 for SHORT.
- Pullback into EMA20–EMA50 zone over previous 3 closed M5 candles.
- Engulfing confirmation only.
- Signal candle touching EMA50 excluded.
- Entry close ≤0.75 ATR from EMA20 and ≤1.20 ATR from EMA50.
- RSI14 recorded, no RSI filter.
- Exact hour, minute, session and side retained.

Baseline exit:
- SL 1 ATR / RR 1.5 / TP 1.5 ATR.
- 1,287 trades.
- 484 wins / 803 losses.
- WR **37.61%**.
- Total **-77R**.
- Avg **-0.0598R**.
- PF **0.9041**.

Latest best grid result by PF:
- **SL 4 ATR**
- **RR 3**
- **TP 12 ATR**
- 1,287 trades.
- 356 wins / 931 losses.
- WR **27.66%**.
- Total **+137R**.
- Avg **+0.10645R**.
- PF **1.14715**.

Other notable positive configurations:
- SL 3.5 / RR 2.5: +113R, PF 1.1274.
- SL 4 / RR 2.5: +106R, PF 1.1192.
- SL 4 / RR 2: +96R, PF 1.1162.
- SL 5 / RR 1.5: +95.5R, PF 1.1301.
- SL 5 / RR 2.5: +95.5R, PF 1.1071.
- SL 3.5 / RR 3: +101R, PF 1.1074.
- SL 5 / RR 2: +84R, PF 1.1012.
- SL 5 / RR 3: +77R, PF 1.0814.

Low-ATR configurations remained poor; SL 0.5 ATR produced approximately -382.5R to -579R across the tested RR values.

Interpretation:
- The proximity rule reduced the eligible signal set to 1,287 entries.
- 4 ATR / RR 3 is the current numerical leader.
- It is **not yet accepted as final**, because the same three-year sample was used to select it and out-of-sample/walk-forward validation is still required.
- RSI remains a recorded variable only.
- No historical-news filter can be evaluated from this run.
- No hour/session filter has been promoted.
- Research remains separate from the final MT5 LIVE bot.

### Storage/output decision

The monolithic `engulfing_all_atr_rr_trades.csv` was intentionally removed from the output workflow because it exceeded GitHub's file-size limit.

The complete trade-level dataset is now split by ATR/RR combination into many smaller CSV files. Each file retains the complete trade metadata, including:
- entry time;
- side;
- entry price;
- ATR;
- EMA20/EMA50 values;
- signed and absolute EMA distances;
- ATR-normalized EMA distances;
- RSI14;
- hour;
- minute;
- session;
- pattern;
- exit time;
- result R;
- exit reason;
- exit price;
- duration;
- SL ATR;
- RR;
- TP ATR.

The `engulfing_exit_grid_cache.npz` is a numerical acceleration cache only and is not required for analysis.

### Current research status

**Current candidate:** Engulfing-only + EMA20 proximity ≤0.75 ATR + EMA50 proximity ≤1.20 ATR + SL 4 ATR + RR 3.

**Status:** RESEARCH CANDIDATE — **NOT ACCEPTED AS FINAL**.

No RSI threshold, hour filter, session filter, news filter, EMA50 stop, rejection pattern or other additional rule has been accepted without sufficient robustness evidence.

Final-bot requirement remains unchanged: the eventual MT5 LIVE version must contain only clean live MT5 code. Historical datasets, backtest engines, research scripts, result files, caches and temporary research adjustments must remain outside the final LIVE bot.
