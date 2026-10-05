# Trend + Pullback — Initial Specification

## Objective
Test whether an EMA trend filter plus a pullback into the EMA20/EMA50 zone and a price-action confirmation candle produces a robust edge on XAUUSD.

## Trend
- Long bias: EMA20 > EMA50.
- Short bias: EMA20 < EMA50.
- No trade when EMA20 equals EMA50.

## Pullback
A pullback is present when one of the previous N closed candles intersects the zone between EMA20 and EMA50.

## Initial confirmation
Long:
- bullish engulfing, OR
- bullish rejection candle: bullish close, lower wick >= body, close in the upper 30% of the range.

Short:
- bearish engulfing, OR
- bearish rejection candle: bearish close, upper wick >= body, close in the lower 30% of the range.

Entry is evaluated on the closed confirmation candle.

## Initial risk management
First baseline uses dynamic ATR exits:
- ATR(14)
- SL = 1.0 x ATR
- TP = 1.5 x ATR
- no break-even
- no trailing stop
- one position per symbol/magic number

These are deliberately baseline values and will be optimized/studied later against fixed and market-structure exits.

## Schedule
Initial test: 24/5. No session filter.

## News
No news filter in version 1. News handling will be studied after the baseline.

## Research order
1. Baseline backtest.
2. Fixed vs ATR vs structure-based SL/TP.
3. RR and risk-management sweep.
4. Session/time-of-day study.
5. News-window study.
6. Out-of-sample validation.
7. Forward/demo testing.
