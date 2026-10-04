# Project Plan — Pure Price Action

## Data
Input minimo: timestamp, open, high, low, close.
Timeframe iniziale: 5 minuti.

## Feature
- body e body/range
- upper/lower wick
- close location
- candele consecutive
- inside bar / engulfing
- swing highs/lows
- breakout di massimi/minimi recenti
- espansione/contrazione del range
- HH/HL/LH/LL

## Strategia
Nessuna soglia viene copiata dal V1. Stop, target, lookback e pattern saranno determinati tramite test.

## Validazione
Backtest → parameter sweep → out-of-sample → forward test → demo → eventuale prop.

Vincolo: il segnale deve dipendere esclusivamente da OHLC.
