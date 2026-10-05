# Trend Pullback MT5 — XAUUSD

Standalone MetaTrader 5 Expert Advisor research project.

## Strategy
- Asset: XAUUSD
- Initial timeframe: M5
- EMA 20 / EMA 50
- EMA20 > EMA50 → long bias
- EMA20 < EMA50 → short bias
- Recent pullback into the EMA20–EMA50 zone
- Bullish/bearish price-action confirmation
- Entry at confirmation-candle close

## Initial exits
Baseline uses ATR(14):
- SL = 1.0 × ATR
- TP = 1.5 × ATR
- no break-even
- no trailing stop

These are research parameters, not final values. Fixed and structure-based exits will be tested later.

## Schedule
24/5 baseline. Session filters and news handling will be studied separately.

See `docs/STRATEGY.md` for the full initial specification.
