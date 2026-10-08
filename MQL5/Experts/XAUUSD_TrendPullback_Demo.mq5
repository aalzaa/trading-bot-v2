//+------------------------------------------------------------------+
//| XAUUSD Trend Pullback Demo EA                                    |
//| Research reference: SL 4 ATR / RR 3                              |
//| Strategy: EMA20/EMA50 bias + pullback + engulfing on M5          |
//+------------------------------------------------------------------+
#property strict
#property version   "1.00"

#include <Trade/Trade.mqh>

CTrade trade;

enum ENUM_SESSION_MODE
{
   SESSION_ALL = 0,
   SESSION_ASIA = 1,
   SESSION_LONDON = 2,
   SESSION_NEW_YORK = 3,
   SESSION_ASIA_LONDON = 4,
   SESSION_ASIA_NEW_YORK = 5,
   SESSION_LONDON_NEW_YORK = 6
};

input ENUM_SESSION_MODE InpSessionMode = SESSION_ALL; // Sessions
input double            InpRiskPercent = 0.25;        // Risk % per trade
input double            InpATRSL = 4.0;                // SL = ATR x
input double            InpRR = 3.0;                   // Risk / Reward
input string            InpExcludedHours = "2,7,11,19,20"; // Server hours to exclude
input int               InpMagic = 204030;             // Magic number
input int               InpEMAFast = 20;               // Fast EMA
input int               InpEMASlow = 50;               // Slow EMA
input int               InpATRPeriod = 14;             // ATR period
input int               InpPullbackLookback = 3;       // Pullback lookback
input double            InpEMA20MaxATR = 0.75;         // Max distance from EMA20 in ATR
input double            InpEMA50MaxATR = 1.20;         // Max distance from EMA50 in ATR
input bool              InpExcludeEMA50Touch = true;   // Exclude EMA50 touch
input bool              InpOnePositionOnly = true;     // One position at a time

int hFast = INVALID_HANDLE;
int hSlow = INVALID_HANDLE;
int hATR  = INVALID_HANDLE;
datetime lastBarTime = 0;

//+------------------------------------------------------------------+
int OnInit()
{
   hFast = iMA(_Symbol, PERIOD_M5, InpEMAFast, 0, MODE_EMA, PRICE_CLOSE);
   hSlow = iMA(_Symbol, PERIOD_M5, InpEMASlow, 0, MODE_EMA, PRICE_CLOSE);
   hATR  = iATR(_Symbol, PERIOD_M5, InpATRPeriod);

   if(hFast == INVALID_HANDLE || hSlow == INVALID_HANDLE || hATR == INVALID_HANDLE)
      return(INIT_FAILED);

   trade.SetExpertMagicNumber(InpMagic);
   trade.SetTypeFillingBySymbol(_Symbol);

   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   if(hFast != INVALID_HANDLE) IndicatorRelease(hFast);
   if(hSlow != INVALID_HANDLE) IndicatorRelease(hSlow);
   if(hATR  != INVALID_HANDLE) IndicatorRelease(hATR);
}

//+------------------------------------------------------------------+
void OnTick()
{
   datetime currentBar = iTime(_Symbol, PERIOD_M5, 0);
   if(currentBar == 0 || currentBar == lastBarTime)
      return;

   lastBarTime = currentBar;
   CheckForEntry();
}

//+------------------------------------------------------------------+
bool IsNewTradeAllowed()
{
   if(InpRiskPercent <= 0.0 || InpATRSL <= 0.0 || InpRR <= 0.0)
      return false;

   if(InpOnePositionOnly && HasOurPosition())
      return false;

   return true;
}

//+------------------------------------------------------------------+
bool HasOurPosition()
{
   for(int i = PositionsTotal() - 1; i >= 0; --i)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0)
         continue;

      if(PositionGetString(POSITION_SYMBOL) == _Symbol &&
         (long)PositionGetInteger(POSITION_MAGIC) == InpMagic)
         return true;
   }
   return false;
}

//+------------------------------------------------------------------+
bool IsExcludedHour(const int hour)
{
   string parts[];
   int n = StringSplit(InpExcludedHours, ',', parts);

   for(int i = 0; i < n; ++i)
   {
      string s = parts[i];
      StringTrimLeft(s);
      StringTrimRight(s);
      if((int)StringToInteger(s) == hour)
         return true;
   }
   return false;
}

//+------------------------------------------------------------------+
// Session hours use MT5 broker/server time.
// Asia: 00:00-08:59
// London: 08:00-15:59
// New York: 13:00-21:59
// Overlaps are intentionally allowed.
//+------------------------------------------------------------------+
bool InSession(const int hour, const ENUM_SESSION_MODE mode)
{
   bool asia   = (hour >= 0 && hour <= 8);
   bool london = (hour >= 8 && hour <= 15);
   bool ny     = (hour >= 13 && hour <= 21);

   switch(mode)
   {
      case SESSION_ASIA:             return asia;
      case SESSION_LONDON:           return london;
      case SESSION_NEW_YORK:         return ny;
      case SESSION_ASIA_LONDON:      return asia || london;
      case SESSION_ASIA_NEW_YORK:    return asia || ny;
      case SESSION_LONDON_NEW_YORK:  return london || ny;
      case SESSION_ALL:              return asia || london || ny;
   }

   return false;
}

//+------------------------------------------------------------------+
bool CopyIndicators(double &ema20[], double &ema50[], double &atr[])
{
   ArraySetAsSeries(ema20, true);
   ArraySetAsSeries(ema50, true);
   ArraySetAsSeries(atr, true);

   if(CopyBuffer(hFast, 0, 0, 5, ema20) < 5) return false;
   if(CopyBuffer(hSlow, 0, 0, 5, ema50) < 5) return false;
   if(CopyBuffer(hATR,  0, 0, 5, atr)  < 5) return false;

   return true;
}

//+------------------------------------------------------------------+
bool PullbackIntoZone(const int shift, const double ema20, const double ema50,
                      const double atr)
{
   double zoneHigh = MathMax(ema20, ema50);
   double zoneLow  = MathMin(ema20, ema50);

   for(int s = shift; s < shift + InpPullbackLookback; ++s)
   {
      double hi = iHigh(_Symbol, PERIOD_M5, s);
      double lo = iLow(_Symbol, PERIOD_M5, s);

      if(hi >= zoneLow && lo <= zoneHigh)
         return true;

      // Allow proximity to either EMA according to the research thresholds.
      if(MathAbs(iClose(_Symbol, PERIOD_M5, s) - ema20) <= InpEMA20MaxATR * atr)
         return true;

      if(MathAbs(iClose(_Symbol, PERIOD_M5, s) - ema50) <= InpEMA50MaxATR * atr)
         return true;
   }

   return false;
}

//+------------------------------------------------------------------+
bool BullishEngulfing(const int s)
{
   double o1=iOpen(_Symbol,PERIOD_M5,s+1);
   double c1=iClose(_Symbol,PERIOD_M5,s+1);
   double o0=iOpen(_Symbol,PERIOD_M5,s);
   double c0=iClose(_Symbol,PERIOD_M5,s);

   return (c1 < o1 && c0 > o0 && o0 <= c1 && c0 >= o1);
}

//+------------------------------------------------------------------+
bool BearishEngulfing(const int s)
{
   double o1=iOpen(_Symbol,PERIOD_M5,s+1);
   double c1=iClose(_Symbol,PERIOD_M5,s+1);
   double o0=iOpen(_Symbol,PERIOD_M5,s);
   double c0=iClose(_Symbol,PERIOD_M5,s);

   return (c1 > o1 && c0 < o0 && o0 >= c1 && c0 <= o1);
}

//+------------------------------------------------------------------+
bool EMA50Touched(const int s, const double ema50)
{
   double hi=iHigh(_Symbol,PERIOD_M5,s);
   double lo=iLow(_Symbol,PERIOD_M5,s);
   return (lo <= ema50 && hi >= ema50);
}

//+------------------------------------------------------------------+
double NormalizeVolume(const double volume)
{
   double minVol = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxVol = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double step   = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);

   if(step <= 0.0) return 0.0;

   double v = MathFloor(volume / step) * step;
   v = MathMax(minVol, MathMin(maxVol, v));

   int digits = 0;
   double x = step;
   while(x < 1.0 && digits < 8)
   {
      x *= 10.0;
      digits++;
   }

   return NormalizeDouble(v, digits);
}

//+------------------------------------------------------------------+
double CalculateVolume(const double entry, const double sl)
{
   double riskMoney = AccountInfoDouble(ACCOUNT_EQUITY) * (InpRiskPercent / 100.0);
   double tickSize  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);

   if(riskMoney <= 0.0 || tickSize <= 0.0 || tickValue <= 0.0)
      return 0.0;

   double priceDistance = MathAbs(entry - sl);
   double moneyPerLot = (priceDistance / tickSize) * tickValue;

   if(moneyPerLot <= 0.0)
      return 0.0;

   return NormalizeVolume(riskMoney / moneyPerLot);
}

//+------------------------------------------------------------------+
void OpenBuy(const double atr)
{
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   if(ask <= 0.0) return;

   double sl = ask - atr * InpATRSL;
   double tp = ask + (ask - sl) * InpRR;
   double volume = CalculateVolume(ask, sl);

   if(volume <= 0.0) return;

   trade.Buy(volume, _Symbol, ask, sl, tp, "XAUUSD Demo BUY");
}

//+------------------------------------------------------------------+
void OpenSell(const double atr)
{
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   if(bid <= 0.0) return;

   double sl = bid + atr * InpATRSL;
   double tp = bid - (sl - bid) * InpRR;
   double volume = CalculateVolume(bid, sl);

   if(volume <= 0.0) return;

   trade.Sell(volume, _Symbol, bid, sl, tp, "XAUUSD Demo SELL");
}

//+------------------------------------------------------------------+
void CheckForEntry()
{
   if(_Symbol == "") return;
   if(!IsNewTradeAllowed()) return;

   datetime signalBarTime = iTime(_Symbol, PERIOD_M5, 1);
   if(signalBarTime == 0) return;

   MqlDateTime tm;
   TimeToStruct(signalBarTime, tm);

   if(IsExcludedHour(tm.hour)) return;
   if(!InSession(tm.hour, InpSessionMode)) return;

   double ema20[], ema50[], atr[];
   if(!CopyIndicators(ema20, ema50, atr)) return;

   const int s = 1;
   double close = iClose(_Symbol, PERIOD_M5, s);
   double a = atr[s];

   if(a <= 0.0) return;

   // Long bias + pullback + bullish engulfing.
   if(ema20[s] > ema50[s] &&
      PullbackIntoZone(s, ema20[s], ema50[s], a) &&
      BullishEngulfing(s))
   {
      if(InpExcludeEMA50Touch && EMA50Touched(s, ema50[s]))
         return;

      OpenBuy(a);
      return;
   }

   // Short bias + pullback + bearish engulfing.
   if(ema20[s] < ema50[s] &&
      PullbackIntoZone(s, ema20[s], ema50[s], a) &&
      BearishEngulfing(s))
   {
      if(InpExcludeEMA50Touch && EMA50Touched(s, ema50[s]))
         return;

      OpenSell(a);
      return;
   }
}
//+------------------------------------------------------------------+
