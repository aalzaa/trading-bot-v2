#property strict
#property version   "1.0"
#property description "XAUUSD Trend + Pullback research EA"

#include <Trade/Trade.mqh>

CTrade trade;

input string InpSymbol = "XAUUSD";
input ENUM_TIMEFRAMES InpTimeframe = PERIOD_M5;
input int InpFastEMA = 20;
input int InpSlowEMA = 50;
input int InpPullbackLookback = 3;
input int InpATRPeriod = 14;
input double InpSL_ATR = 1.0;
input double InpTP_ATR = 1.5;
input double InpLots = 0.10;
input ulong InpMagic = 20502026;
input int InpDeviationPoints = 30;

int fastHandle = INVALID_HANDLE;
int slowHandle = INVALID_HANDLE;
int atrHandle  = INVALID_HANDLE;
datetime lastBarTime = 0;

bool IsNewBar()
{
   datetime t = iTime(InpSymbol, InpTimeframe, 0);
   if(t == 0 || t == lastBarTime) return false;
   lastBarTime = t;
   return true;
}

bool GetBufferValue(int handle, int shift, double &value)
{
   double buffer[];
   ArraySetAsSeries(buffer, true);
   if(CopyBuffer(handle, 0, shift, 1, buffer) != 1) return false;
   value = buffer[0];
   return true;
}

bool GetRates(MqlRates &signalBar, MqlRates &prevBar)
{
   MqlRates rates[3];
   ArraySetAsSeries(rates, true);
   if(CopyRates(InpSymbol, InpTimeframe, 0, 3, rates) < 3) return false;
   signalBar = rates[1];
   prevBar = rates[2];
   return true;
}

bool CandleTouchesZone(MqlRates &bar, double ema20, double ema50)
{
   double zoneHigh = MathMax(ema20, ema50);
   double zoneLow = MathMin(ema20, ema50);
   return bar.high >= zoneLow && bar.low <= zoneHigh;
}

bool HasRecentPullback(bool longSide)
{
   int count = MathMax(InpPullbackLookback, 1);
   MqlRates rates[];
   double ema20[], ema50[];
   ArraySetAsSeries(rates, true);
   ArraySetAsSeries(ema20, true);
   ArraySetAsSeries(ema50, true);

   if(CopyRates(InpSymbol, InpTimeframe, 2, count, rates) < count) return false;
   if(CopyBuffer(fastHandle, 0, 2, count, ema20) != count) return false;
   if(CopyBuffer(slowHandle, 0, 2, count, ema50) != count) return false;

   for(int i = 0; i < count; i++)
   {
      if(!CandleTouchesZone(rates[i], ema20[i], ema50[i])) continue;

      if(longSide && rates[i].close >= MathMin(ema20[i], ema50[i]))
         return true;

      if(!longSide && rates[i].close <= MathMax(ema20[i], ema50[i]))
         return true;
   }
   return false;
}

bool IsBullishPattern(MqlRates &bar, MqlRates &prev)
{
   double range = bar.high - bar.low;
   double body = MathAbs(bar.close - bar.open);
   double lowerWick = MathMin(bar.open, bar.close) - bar.low;
   if(range <= 0.0 || body <= 0.0) return false;

   bool engulfing = bar.close > bar.open &&
                    prev.close < prev.open &&
                    bar.open <= prev.close &&
                    bar.close >= prev.open;

   bool rejection = bar.close > bar.open &&
                    lowerWick >= body &&
                    (bar.close - bar.low) / range >= 0.70;

   return engulfing || rejection;
}

bool IsBearishPattern(MqlRates &bar, MqlRates &prev)
{
   double range = bar.high - bar.low;
   double body = MathAbs(bar.close - bar.open);
   double upperWick = bar.high - MathMax(bar.open, bar.close);
   if(range <= 0.0 || body <= 0.0) return false;

   bool engulfing = bar.close < bar.open &&
                    prev.close > prev.open &&
                    bar.open >= prev.close &&
                    bar.close <= prev.open;

   bool rejection = bar.close < bar.open &&
                    upperWick >= body &&
                    (bar.high - bar.close) / range >= 0.70;

   return engulfing || rejection;
}

bool HasOurOpenPosition()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != InpSymbol) continue;
      if((ulong)PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      return true;
   }
   return false;
}

double NormalizePrice(double price)
{
   int digits = (int)SymbolInfoInteger(InpSymbol, SYMBOL_DIGITS);
   return NormalizeDouble(price, digits);
}

bool PlaceLong(double atr)
{
   double ask = SymbolInfoDouble(InpSymbol, SYMBOL_ASK);
   if(ask <= 0.0 || atr <= 0.0) return false;

   double sl = NormalizePrice(ask - atr * InpSL_ATR);
   double tp = NormalizePrice(ask + atr * InpTP_ATR);

   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(InpDeviationPoints);
   return trade.Buy(InpLots, InpSymbol, 0.0, sl, tp, "TrendPullback LONG");
}

bool PlaceShort(double atr)
{
   double bid = SymbolInfoDouble(InpSymbol, SYMBOL_BID);
   if(bid <= 0.0 || atr <= 0.0) return false;

   double sl = NormalizePrice(bid + atr * InpSL_ATR);
   double tp = NormalizePrice(bid - atr * InpTP_ATR);

   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(InpDeviationPoints);
   return trade.Sell(InpLots, InpSymbol, 0.0, sl, tp, "TrendPullback SHORT");
}

int OnInit()
{
   if(!SymbolSelect(InpSymbol, true)) return INIT_FAILED;

   fastHandle = iMA(InpSymbol, InpTimeframe, InpFastEMA, 0, MODE_EMA, PRICE_CLOSE);
   slowHandle = iMA(InpSymbol, InpTimeframe, InpSlowEMA, 0, MODE_EMA, PRICE_CLOSE);
   atrHandle = iATR(InpSymbol, InpTimeframe, InpATRPeriod);

   if(fastHandle == INVALID_HANDLE || slowHandle == INVALID_HANDLE || atrHandle == INVALID_HANDLE)
      return INIT_FAILED;

   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(InpDeviationPoints);
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   if(fastHandle != INVALID_HANDLE) IndicatorRelease(fastHandle);
   if(slowHandle != INVALID_HANDLE) IndicatorRelease(slowHandle);
   if(atrHandle != INVALID_HANDLE) IndicatorRelease(atrHandle);
}

void OnTick()
{
   if(!IsNewBar()) return;
   if(HasOurOpenPosition()) return;

   MqlRates signalBar, prevBar;
   if(!GetRates(signalBar, prevBar)) return;

   double ema20, ema50, atr;
   if(!GetBufferValue(fastHandle, 1, ema20)) return;
   if(!GetBufferValue(slowHandle, 1, ema50)) return;
   if(!GetBufferValue(atrHandle, 1, atr)) return;

   if(ema20 > ema50)
   {
      if(HasRecentPullback(true) && IsBullishPattern(signalBar, prevBar))
         PlaceLong(atr);
   }
   else if(ema20 < ema50)
   {
      if(HasRecentPullback(false) && IsBearishPattern(signalBar, prevBar))
         PlaceShort(atr);
   }
}
