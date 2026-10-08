# XAUUSD Demo EA

Demo/live-forward-testing EA for the XAUUSD trend-pullback strategy.

## Reference configuration

- Instrument: XAUUSD
- Timeframe: M5
- EMA20/EMA50 trend bias
- Pullback + engulfing confirmation
- SL: 4 ATR
- RR: 3.0
- Risk: 0.25% per trade
- Sessions: Asia + London + New York
- Excluded server hours: 02, 07, 11, 19, 20
- RSI filter: disabled / not used

## MT5 inputs

The following can be changed directly from the EA Inputs panel:

- Session selection: Asia, London, New York, any supported pair, or all three
- Risk % per trade
- ATR SL multiplier
- Risk/Reward
- Excluded hours
- Strategy parameters such as EMA periods, ATR period and pullback lookback

## Important

Session and excluded-hour inputs use the MT5 broker/server time. The EA calculates position size from account equity and the configured risk percentage using the symbol tick size/tick value.

This branch is a demo/forward-testing implementation and does not modify the historical research results in results4.
