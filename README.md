# Trading Bot V2 — Pure Price Action

Nuovo progetto separato basato esclusivamente su price action e candele.

## Regole
- Nessun volume
- Nessun Delta/CVD
- Nessun order book
- Nessuna Absorption Efficiency
- Nessun Big Trade
- Nessun VWAP/POC volumetrico
- Nessun Data Converter
- Nessuna dipendenza dalla logica del V1

## Obiettivo
Costruire e validare una strategia quantitativa usando esclusivamente OHLC.

Pipeline: OHLC → feature price action → segnali → backtest → parameter study → out-of-sample → forward test → demo → eventuale prop/live.
