//+------------------------------------------------------------------+
//|                                        GoldScalpAssistant.mq5    |
//|                                             Trade- project        |
//|                                                                  |
//| Gold scalping assistant for MetaTrader 5.                        |
//|                                                                  |
//| Implements the same setups and the same hard risk rules as the   |
//| Python package in metals/, so that what is tested there and what  |
//| runs here are the same system rather than two similar ones.       |
//|                                                                  |
//| MODES                                                             |
//|   Advisor  - draws the setup, prints the plan, alerts. Places no  |
//|              orders. This is the default and the honest starting  |
//|              point: it lets you compare its judgement against     |
//|              your own before it is allowed to spend anything.     |
//|   Auto     - places and manages the trade itself.                 |
//|                                                                  |
//| READ BEFORE ENABLING AUTO                                         |
//| The strategy behind this EA has NOT been shown to have a positive |
//| expectancy. It was evaluated across 100 simulated markets and     |
//| every configuration lost money, including one with zero spread.   |
//| That evaluation could not test its core bet (see                  |
//| docs/BACKTEST-ERGEBNISSE.md), so the result is inconclusive, not  |
//| damning -- but "inconclusive" is not "profitable". Run it in      |
//| Advisor mode on a demo account and gather your own evidence.      |
//|                                                                  |
//| What this EA does reliably is enforce discipline: position sizes  |
//| that are correct, stops that survive normal noise, a daily loss   |
//| limit that actually stops, and a refusal to trade the windows     |
//| where gold's spread eats the edge.                                |
//+------------------------------------------------------------------+
#property copyright "Trade- project"
#property link      "https://github.com/arthursideload-star/Trade-"
#property version   "1.00"
#property strict

#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>
#include <GoldScalp\Risk.mqh>
#include <GoldScalp\Sessions.mqh>

//+------------------------------------------------------------------+
//| Inputs                                                            |
//|                                                                  |
//| Note what is NOT an input: risk per trade, the daily loss limit,  |
//| the minimum reward/risk, the maximum trades per day. Those live   |
//| in Risk.mqh as compile-time constants. A risk limit you can edit  |
//| from the settings dialog mid-session is not a limit.               |
//+------------------------------------------------------------------+
enum ENUM_RUN_MODE
{
   MODE_ADVISOR = 0,   // Advisor - signals only, places no orders
   MODE_AUTO    = 1    // Auto - places and manages trades
};

input group "=== Operation ==="
input ENUM_RUN_MODE InpMode            = MODE_ADVISOR; // Run mode
input long          InpMagic           = 20260726;     // Magic number
input bool          InpPrimeOnly       = true;         // Trade prime windows only
input bool          InpAlerts          = true;         // Pop-up alert on a signal
input bool          InpDashboard       = true;         // Draw the on-chart panel

input group "=== Setups (all are M5) ==="
input bool          InpUseS2           = true;  // S2 Pullback Window Break
input bool          InpUseS4           = true;  // S4 Round Number Fade
input bool          InpUseS5           = true;  // S5 Momentum Continuation

input group "=== Exits ==="
input double        InpFirstTargetR    = 0.5;   // First target in R (measured: 0.5 beats 1.0)
input double        InpFirstTargetPct  = 60.0;  // Percent closed at the first target
input double        InpRunnerTargetR   = 2.5;   // Runner target in R
input double        InpTrailAtrMult    = 1.2;   // Trail distance in ATR
input int           InpTimeStopMinutes = 45;    // Close regardless of P/L after N minutes

input group "=== Filters ==="
input int           InpAtrPeriod       = 14;    // ATR period (M5)
input int           InpNewsBlackoutMin = 30;    // Minutes blocked around :30 data times
input bool          InpBlockNewsWindow = true;  // Apply the news blackout

//+------------------------------------------------------------------+
//| Globals                                                           |
//+------------------------------------------------------------------+
CTrade         trade;
CPositionInfo  pos;

int      hAtr   = INVALID_HANDLE;
int      hEma9  = INVALID_HANDLE;
int      hEma21 = INVALID_HANDLE;
int      hEma50 = INVALID_HANDLE;

datetime lastBarTime = 0;
DayState day;

//--- Managed-position state. One scalp at a time, so a single record.
struct ManagedPosition
{
   ulong    ticket;
   double   entry;
   double   initial_stop;
   double   risk_per_unit;
   double   first_target;
   double   runner_target;
   bool     first_target_done;
   double   initial_volume;
   datetime opened_at;
   string   setup_id;
};
ManagedPosition managed;

string   lastSignalText = "";
datetime lastSignalTime = 0;
string   lastNote       = "";

//--- Log a reason once rather than on every bar.
void Note(const string text)
{
   if(text == lastNote) return;
   lastNote = text;
   Print(text);
}

//+------------------------------------------------------------------+
int OnInit()
{
   trade.SetExpertMagicNumber(InpMagic);
   trade.SetMarginMode();
   trade.SetTypeFillingBySymbol(_Symbol);
   trade.SetDeviationInPoints(20);

   hAtr   = iATR(_Symbol, PERIOD_M5, InpAtrPeriod);
   hEma9  = iMA(_Symbol, PERIOD_M5, 9,  0, MODE_EMA, PRICE_CLOSE);
   hEma21 = iMA(_Symbol, PERIOD_M5, 21, 0, MODE_EMA, PRICE_CLOSE);
   hEma50 = iMA(_Symbol, PERIOD_M5, 50, 0, MODE_EMA, PRICE_CLOSE);

   if(hAtr == INVALID_HANDLE || hEma9 == INVALID_HANDLE ||
      hEma21 == INVALID_HANDLE || hEma50 == INVALID_HANDLE)
   {
      Print("failed to create indicator handles");
      return INIT_FAILED;
   }

   ResetDay(day, ServerToUtc(TimeTradeServer()));
   ZeroMemory(managed);

   //--- Sanity checks that are worth failing loudly on.
   if(StringFind(_Symbol, "XAU") < 0 && StringFind(_Symbol, "GOLD") < 0)
      Print("WARNING: this EA is built for gold. Symbol is ", _Symbol,
            " -- the ATR bands, round-number grid and session logic assume "
            "XAU/USD and will be wrong elsewhere.");

   if(Period() != PERIOD_M5)
      Print("NOTE: chart timeframe is ", EnumToString((ENUM_TIMEFRAMES)Period()),
            ". The EA reads M5 regardless, so this is cosmetic -- but the "
            "drawings will not line up with what it is reading.");

   PrintFormat("GoldScalpAssistant started in %s mode. "
               "Risk %.1f%%/trade, daily stop -%.1f%%, daily target +%.1f%%, "
               "max %d trades/day.",
               (InpMode == MODE_ADVISOR ? "ADVISOR (no orders)" : "AUTO"),
               RISK_PER_TRADE_PCT, DAILY_LOSS_LIMIT_PCT,
               DAILY_WIN_TARGET_PCT, MAX_TRADES_PER_DAY);

   if(InpMode == MODE_AUTO)
      Print("AUTO MODE: this strategy has not been shown to have a positive "
            "expectancy. See docs/BACKTEST-ERGEBNISSE.md. Demo only.");

   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   IndicatorRelease(hAtr);
   IndicatorRelease(hEma9);
   IndicatorRelease(hEma21);
   IndicatorRelease(hEma50);
   ObjectsDeleteAll(0, "GSA_");
}

//+------------------------------------------------------------------+
void OnTick()
{
   const datetime utc = ServerToUtc(TimeTradeServer());

   RollDayIfNeeded(utc);

   // Managing an open position happens every tick; looking for a new one
   // happens once per closed bar. Exits must not wait for a bar close.
   if(HasOpenPosition())
      ManageOpenPosition(utc);

   if(InpDashboard)
      DrawDashboard(utc);

   const datetime bar = iTime(_Symbol, PERIOD_M5, 0);
   if(bar == lastBarTime)
      return;
   lastBarTime = bar;

   if(!HasOpenPosition())
      LookForSetup(utc);
}

//+------------------------------------------------------------------+
//| Day rollover                                                      |
//+------------------------------------------------------------------+
void RollDayIfNeeded(const datetime utc)
{
   MqlDateTime now, start;
   TimeToStruct(utc, now);
   TimeToStruct(day.day_start, start);
   if(now.year != start.year || now.mon != start.mon || now.day != start.day)
   {
      PrintFormat("New session. Yesterday closed at %.2f%%.", DayPnLPercent(day));
      ResetDay(day, utc);
   }
}

//+------------------------------------------------------------------+
//| Position helpers                                                  |
//+------------------------------------------------------------------+
bool HasOpenPosition()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(!pos.SelectByIndex(i)) continue;
      if(pos.Symbol() == _Symbol && pos.Magic() == InpMagic)
         return true;
   }
   return false;
}

int CountOpenPositions()
{
   int n = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(!pos.SelectByIndex(i)) continue;
      if(pos.Symbol() == _Symbol && pos.Magic() == InpMagic) n++;
   }
   return n;
}

//+------------------------------------------------------------------+
//| Exit management: partial, break-even, trail, time stop.           |
//+------------------------------------------------------------------+
void ManageOpenPosition(const datetime utc)
{
   if(!pos.SelectByTicket(managed.ticket))
   {
      // The position closed outside our control (stop hit, manual close).
      RecordClosedTrade();
      ZeroMemory(managed);
      return;
   }

   const bool   is_long = (pos.PositionType() == POSITION_TYPE_BUY);
   const double price   = is_long ? SymbolInfoDouble(_Symbol, SYMBOL_BID)
                                  : SymbolInfoDouble(_Symbol, SYMBOL_ASK);

   //--- Time stop. A scalp that has not worked inside its own horizon is no
   //--- longer the trade that was entered.
   const int age_min = (int)((utc - managed.opened_at) / 60);
   if(age_min >= InpTimeStopMinutes)
   {
      CloseAll(StringFormat("time stop after %d minutes", age_min));
      return;
   }

   //--- Friday flat. A stop does not protect against a weekend gap.
   MqlDateTime dt;
   TimeToStruct(utc, dt);
   if(dt.day_of_week == 5 && dt.hour >= FRIDAY_FLAT_HOUR_UTC)
   {
      CloseAll("Friday flat -- a stop does not protect against a weekend gap");
      return;
   }

   //--- Partial at the first target.
   if(!managed.first_target_done)
   {
      const bool hit = is_long ? (price >= managed.first_target)
                               : (price <= managed.first_target);
      if(hit)
         TakePartialAndMoveToBreakEven();
      return;   // never trail on the same tick the partial fills
   }

   //--- Runner target.
   const bool runner_hit = is_long ? (price >= managed.runner_target)
                                   : (price <= managed.runner_target);
   if(runner_hit)
   {
      CloseAll("runner target reached");
      return;
   }

   //--- Trail the remainder.
   TrailRunner(is_long, price);
}

//+------------------------------------------------------------------+
void TakePartialAndMoveToBreakEven()
{
   const double vol_step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   const double vol_min  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double part = managed.initial_volume * InpFirstTargetPct / 100.0;
   part = MathFloor(part / vol_step) * vol_step;

   const double remaining = pos.Volume() - part;

   // If either side of the split would fall under the broker minimum, a
   // partial is impossible. Closing the whole thing at the first target is
   // the honest fallback -- better a small win than an order the server
   // rejects while the price walks away.
   if(part < vol_min || remaining < vol_min)
   {
      CloseAll(StringFormat(
         "first target reached but a partial is not possible: %.2f/%.2f lots "
         "against a %.2f minimum. Closing in full.",
         part, remaining, vol_min));
      return;
   }

   if(!trade.PositionClosePartial(managed.ticket, part))
   {
      PrintFormat("partial close failed: %d %s",
                  trade.ResultRetcode(), trade.ResultRetcodeDescription());
      return;
   }

   managed.first_target_done = true;
   PrintFormat("banked %.0f%% at %.2f (%.1fR). Remainder runs.",
               InpFirstTargetPct, managed.first_target, InpFirstTargetR);

   //--- Break-even, respecting the broker's minimum stop distance.
   const double min_dist = MinStopDistance(_Symbol);
   const bool   is_long  = (pos.PositionType() == POSITION_TYPE_BUY);
   const double price    = is_long ? SymbolInfoDouble(_Symbol, SYMBOL_BID)
                                   : SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double be = managed.entry;
   if(MathAbs(price - be) < min_dist)
   {
      Print("break-even stop is inside the broker's minimum stop distance; "
            "leaving the original stop in place until price moves further");
      return;
   }
   if(!trade.PositionModify(managed.ticket, NormalizeDouble(be, _Digits),
                            pos.TakeProfit()))
      PrintFormat("break-even modify failed: %d %s",
                  trade.ResultRetcode(), trade.ResultRetcodeDescription());
   else
      Print("stop moved to break-even -- the remainder is now a free option, "
            "which is the point of taking the partial");
}

//+------------------------------------------------------------------+
void TrailRunner(const bool is_long, const double price)
{
   double atr[];
   if(CopyBuffer(hAtr, 0, 0, 1, atr) < 1) return;
   const double distance = atr[0] * InpTrailAtrMult;
   const double min_dist = MinStopDistance(_Symbol);
   const double use_dist = MathMax(distance, min_dist);

   const double current = pos.StopLoss();
   double candidate = is_long ? (price - use_dist) : (price + use_dist);
   candidate = NormalizeDouble(candidate, _Digits);

   const bool improved = is_long ? (candidate > current + _Point)
                                 : (candidate < current - _Point);
   if(!improved) return;

   if(!trade.PositionModify(managed.ticket, candidate, pos.TakeProfit()))
   {
      // Trail failures are routine near the stop level; do not spam the log.
      if(trade.ResultRetcode() != TRADE_RETCODE_INVALID_STOPS)
         PrintFormat("trail modify failed: %d %s", trade.ResultRetcode(),
                     trade.ResultRetcodeDescription());
   }
}

//+------------------------------------------------------------------+
void CloseAll(const string why)
{
   if(!trade.PositionClose(managed.ticket))
   {
      PrintFormat("close failed: %d %s", trade.ResultRetcode(),
                  trade.ResultRetcodeDescription());
      return;
   }
   PrintFormat("closed: %s", why);
   RecordClosedTrade();
   ZeroMemory(managed);
}

//+------------------------------------------------------------------+
//| Record the outcome for the day-state rules.                       |
//+------------------------------------------------------------------+
void RecordClosedTrade()
{
   if(!HistorySelect(day.day_start, TimeTradeServer() + 60))
      return;

   double profit = 0.0;
   const int deals = HistoryDealsTotal();
   for(int i = deals - 1; i >= 0; i--)
   {
      const ulong ticket = HistoryDealGetTicket(i);
      if(ticket == 0) continue;
      if(HistoryDealGetInteger(ticket, DEAL_MAGIC) != InpMagic) continue;
      if(HistoryDealGetString(ticket, DEAL_SYMBOL) != _Symbol) continue;
      if(HistoryDealGetInteger(ticket, DEAL_ENTRY) != DEAL_ENTRY_OUT) continue;
      if(HistoryDealGetInteger(ticket, DEAL_POSITION_ID) != (long)managed.ticket)
         continue;
      profit += HistoryDealGetDouble(ticket, DEAL_PROFIT)
              + HistoryDealGetDouble(ticket, DEAL_SWAP)
              + HistoryDealGetDouble(ticket, DEAL_COMMISSION);
   }

   day.last_close_time = ServerToUtc(TimeTradeServer());
   day.last_was_loss   = (profit < 0.0);
   if(profit < 0.0)
      day.consecutive_losses++;
   else
      day.consecutive_losses = 0;

   PrintFormat("trade closed, result %.2f %s. Day %.2f%%, %d trades, %d "
               "consecutive losses.",
               profit, AccountInfoString(ACCOUNT_CURRENCY),
               DayPnLPercent(day), day.trades_taken, day.consecutive_losses);
}

//+------------------------------------------------------------------+
//| Signal search                                                     |
//+------------------------------------------------------------------+
struct Setup
{
   bool     found;
   string   id;
   string   name;
   bool     is_long;
   double   entry;
   double   structural_level;
   string   evidence;
   string   failure_mode;
};

void LookForSetup(const datetime utc)
{
   string reason;

   //--- Hard stops first.
   if(ShouldStopTrading(day, utc, reason))
   {
      Note("STOP: " + reason);
      return;
   }
   if(InCooldown(day, utc, reason))
   {
      Note(reason);
      return;
   }

   string session_label;
   if(!IsTradableSession(utc, InpPrimeOnly, session_label))
   {
      Note("not trading: " + session_label);
      return;
   }

   if(InpBlockNewsWindow && InNewsBlackout(utc, reason))
   {
      Note(reason);
      return;
   }

   double atr[];
   if(CopyBuffer(hAtr, 0, 1, 1, atr) < 1) return;
   const double atr_value = atr[0];
   if(atr_value <= 0.0) return;

   //--- M3: spread relative to volatility.
   const double spread = SymbolInfoDouble(_Symbol, SYMBOL_ASK)
                       - SymbolInfoDouble(_Symbol, SYMBOL_BID);
   if(spread > atr_value * MAX_SPREAD_ATR_FRACTION)
   {
      Note(StringFormat(
         "M3: spread %.3f is %.0f%% of ATR (%.3f), above the %.0f%% ceiling. "
         "The edge would be paid to the broker.",
         spread, spread / atr_value * 100.0, atr_value,
         MAX_SPREAD_ATR_FRACTION * 100.0));
      return;
   }

   Setup s;
   ZeroMemory(s);
   if(InpUseS2 && !s.found) s = DetectS2(atr_value);
   if(InpUseS5 && !s.found) s = DetectS5(atr_value);
   if(InpUseS4 && !s.found) s = DetectS4(atr_value);
   if(!s.found)
   {
      Note("no setup. Most bars are not an opportunity.");
      return;
   }

   ExecuteOrAdvise(s, atr_value, utc, session_label);
}

//+------------------------------------------------------------------+
//| S2 - Pullback Window Break                                        |
//| EMA stack sets direction, 1-3 counter-trend candles form the      |
//| pullback, the break of its extreme is the entry. The depth cap is |
//| the point: a pullback deeper than three bars is a reversal in     |
//| progress, not a pause.                                            |
//+------------------------------------------------------------------+
Setup DetectS2(const double atr_value)
{
   Setup s; ZeroMemory(s);

   double e9[], e21[], e50[], e21_prev[];
   if(CopyBuffer(hEma9,  0, 1, 1, e9)  < 1) return s;
   if(CopyBuffer(hEma21, 0, 1, 1, e21) < 1) return s;
   if(CopyBuffer(hEma50, 0, 1, 1, e50) < 1) return s;
   if(CopyBuffer(hEma21, 0, 6, 1, e21_prev) < 1) return s;

   const bool up   = (e9[0] > e21[0] && e21[0] > e50[0]);
   const bool down = (e9[0] < e21[0] && e21[0] < e50[0]);
   if(!up && !down) return s;

   //--- Slope filter. A flat stack is a range wearing a trend's clothes;
   //--- without this the setup fires all day in chop and loses on the spread.
   const double slope = (e21[0] - e21_prev[0]) / atr_value;
   if(MathAbs(slope) < 0.25) return s;
   if((up && slope < 0) || (down && slope > 0)) return s;

   MqlRates r[];
   ArraySetAsSeries(r, true);
   if(CopyRates(_Symbol, PERIOD_M5, 1, 6, r) < 6) return s;

   int counter = 0;
   for(int i = 0; i < 5; i++)
   {
      const bool is_counter = up ? (r[i].close < r[i].open)
                                 : (r[i].close > r[i].open);
      if(is_counter) counter++;
      else break;
   }
   if(counter == 0 || counter > 3) return s;

   double trigger = up ? r[0].high : r[0].low;
   double extreme = up ? r[0].low  : r[0].high;
   for(int i = 1; i < counter; i++)
   {
      trigger = up ? MathMax(trigger, r[i].high) : MathMin(trigger, r[i].low);
      extreme = up ? MathMin(extreme, r[i].low)  : MathMax(extreme, r[i].high);
   }

   //--- The most recent closed bar must break the pullback extreme.
   const double last_close = r[0].close;
   const bool broke = up ? (last_close > trigger) : (last_close < trigger);
   if(!broke) return s;

   s.found            = true;
   s.id               = "S2";
   s.name             = "Pullback Window Break";
   s.is_long          = up;
   s.entry            = up ? SymbolInfoDouble(_Symbol, SYMBOL_ASK)
                           : SymbolInfoDouble(_Symbol, SYMBOL_BID);
   s.structural_level = extreme;
   s.evidence         = StringFormat(
      "EMA9/21/50 stacked %s, 21-EMA slope %+.2f x ATR, %d-bar pullback broken "
      "at %.2f", (up ? "up" : "down"), slope, counter, trigger);
   s.failure_mode     = "The EMA stack is flat and the 'trend' is a range. The "
                        "slope filter exists for this.";
   return s;
}

//+------------------------------------------------------------------+
//| S5 - Momentum Continuation after an impulse bar                   |
//|                                                                  |
//| Same family as the well-known volatility-expansion scalpers: a    |
//| single bar of at least 1.5x ATR closing in the outer 20% of its   |
//| range is a repricing, not noise. The shallow retracement that     |
//| follows is the entry, with a natural invalidation at the impulse  |
//| bar's origin.                                                     |
//+------------------------------------------------------------------+
Setup DetectS5(const double atr_value)
{
   Setup s; ZeroMemory(s);

   MqlRates r[];
   ArraySetAsSeries(r, true);
   if(CopyRates(_Symbol, PERIOD_M5, 1, 8, r) < 8) return s;

   int impulse = -1;
   for(int i = 1; i < 7; i++)
   {
      const double range = r[i].high - r[i].low;
      if(range <= 0.0) continue;
      const double close_pos = (r[i].close - r[i].low) / range;
      if(range >= atr_value * 1.5 && (close_pos >= 0.8 || close_pos <= 0.2))
      {
         impulse = i;
         break;
      }
   }
   if(impulse < 0) return s;

   const double range     = r[impulse].high - r[impulse].low;
   const double close_pos = (r[impulse].close - r[impulse].low) / range;
   const bool   is_long   = (close_pos >= 0.8);
   const double origin    = is_long ? r[impulse].low : r[impulse].high;
   const double third     = is_long ? (r[impulse].low + range / 3.0)
                                    : (r[impulse].high - range / 3.0);

   //--- Invalidated if anything since closed beyond the impulse origin.
   for(int i = 0; i < impulse; i++)
   {
      if(is_long && r[i].close < origin) return s;
      if(!is_long && r[i].close > origin) return s;
   }

   //--- Price must have retraced into the impulse bar's near third.
   const bool in_zone = is_long ? (r[0].low <= third) : (r[0].high >= third);
   if(!in_zone) return s;

   s.found            = true;
   s.id               = "S5";
   s.name             = "Momentum Continuation";
   s.is_long          = is_long;
   s.entry            = is_long ? SymbolInfoDouble(_Symbol, SYMBOL_ASK)
                                : SymbolInfoDouble(_Symbol, SYMBOL_BID);
   s.structural_level = origin;
   s.evidence         = StringFormat(
      "impulse bar %.1f x ATR closing at %.0f%% of its range, retraced into "
      "its near third without breaking the origin at %.2f",
      range / atr_value, close_pos * 100.0, origin);
   s.failure_mode     = "The impulse was a news spike. Those retrace fully and "
                        "continue through far more often than session-flow "
                        "impulses. If a release landed in the last 30 minutes, "
                        "this setup does not apply.";
   return s;
}

//+------------------------------------------------------------------+
//| S4 - Round Number Fade                                            |
//| Gold respects its 10 and 50 handles because that is where resting |
//| orders actually sit. First or second touch only.                  |
//+------------------------------------------------------------------+
Setup DetectS4(const double atr_value)
{
   Setup s; ZeroMemory(s);

   MqlRates r[];
   ArraySetAsSeries(r, true);
   if(CopyRates(_Symbol, PERIOD_M5, 1, 13, r) < 13) return s;

   const double price  = r[0].close;
   const double handle = MathRound(price / 10.0) * 10.0;
   if(MathAbs(price - handle) > atr_value * 1.5) return s;

   //--- Require an extended approach: this is a first-touch setup.
   const double run = MathAbs(r[0].close - r[12].open);
   if(run < atr_value * 2.0) return s;
   const bool approaching_up = (r[0].close > r[12].open);

   //--- Rejection candle at the handle on the last closed bar.
   const double range = r[0].high - r[0].low;
   if(range <= 0.0) return s;
   const double body  = MathAbs(r[0].close - r[0].open);
   const double upper = r[0].high - MathMax(r[0].open, r[0].close);
   const double lower = MathMin(r[0].open, r[0].close) - r[0].low;

   bool rejected_down = (upper >= atr_value * 0.6 && upper > lower * 2.0
                         && body / range < 0.45 && r[0].high >= handle);
   bool rejected_up   = (lower >= atr_value * 0.6 && lower > upper * 2.0
                         && body / range < 0.45 && r[0].low <= handle);

   if(approaching_up && !rejected_down) return s;
   if(!approaching_up && !rejected_up)  return s;

   //--- Count touches. After the second the handle is being accumulated
   //--- against rather than defended, and the next attempt usually goes through.
   int touches = 0;
   for(int i = 0; i < 12; i++)
      if(r[i].low <= handle && r[i].high >= handle) touches++;
   if(touches >= 3) return s;

   s.found            = true;
   s.id               = "S4";
   s.name             = "Round Number Fade";
   s.is_long          = !approaching_up;
   s.entry            = s.is_long ? SymbolInfoDouble(_Symbol, SYMBOL_ASK)
                                  : SymbolInfoDouble(_Symbol, SYMBOL_BID);
   s.structural_level = approaching_up ? r[0].high : r[0].low;
   s.evidence         = StringFormat(
      "%.1f x ATR run into the %.0f handle, rejection candle, touch %d of a "
      "maximum 2", run / atr_value, handle, touches);
   s.failure_mode     = "The handle breaks and becomes support. After the "
                        "second test it is being accumulated against.";
   return s;
}

//+------------------------------------------------------------------+
//| News blackout                                                     |
//|                                                                  |
//| MQL5 has an economic calendar, but it is not available in the     |
//| Strategy Tester and its availability varies by broker. So this is |
//| a deliberately crude time-based guard: the 08:30 and 10:00 New    |
//| York data windows and 14:00 FOMC, blocked either side.            |
//|                                                                  |
//| It WILL miss a surprise release, a rescheduled print, and every   |
//| non-US event. It is a floor under the veto, not a substitute for  |
//| looking at a calendar before the session.                          |
//+------------------------------------------------------------------+
bool InNewsBlackout(const datetime utc, string &reason)
{
   const int ny_offset = NewYorkOffsetHours(utc);
   const datetime ny   = utc + ny_offset * 3600;
   MqlDateTime dt;
   TimeToStruct(ny, dt);

   const int minutes_now = dt.hour * 60 + dt.min;
   const int windows[3]  = { 8 * 60 + 30, 10 * 60, 14 * 60 };
   const string names[3] = { "08:30 NY data window (NFP/CPI/PPI/claims)",
                             "10:00 NY data window (ISM/sentiment)",
                             "14:00 NY FOMC window" };

   for(int i = 0; i < 3; i++)
   {
      if(MathAbs(minutes_now - windows[i]) <= InpNewsBlackoutMin)
      {
         reason = StringFormat(
            "R4: inside the %s (+/- %d min). Gold routinely moves several ATR "
            "on these prints and the first direction is wrong often enough "
            "that it is not a coin flip worth taking.",
            names[i], InpNewsBlackoutMin);
         return true;
      }
   }
   return false;
}

//+------------------------------------------------------------------+
//| Turn a setup into a plan, then either advise or execute.          |
//+------------------------------------------------------------------+
void ExecuteOrAdvise(const Setup &s, const double atr_value,
                     const datetime utc, const string session_label)
{
   //--- M2: the stop sits beyond the structural level, never on it. Gold
   //--- reaches through obvious levels to collect the stops resting there.
   double stop = s.is_long ? (s.structural_level - atr_value * STOP_BUFFER_ATR)
                           : (s.structural_level + atr_value * STOP_BUFFER_ATR);

   //--- M1: never tighter than MIN_STOP_ATR_MULTIPLE. A stop inside one ATR
   //--- is noise, not risk -- a normal wick takes it out before the idea
   //--- resolves. Widening shrinks the position, which is the correct trade.
   const double floor_dist = atr_value * MIN_STOP_ATR_MULTIPLE;
   if(MathAbs(s.entry - stop) < floor_dist)
      stop = s.is_long ? (s.entry - floor_dist) : (s.entry + floor_dist);

   //--- Broker minimum stop distance. This is the constraint that does not
   //--- exist in a backtest and rejects the order live.
   const double min_dist = MinStopDistance(_Symbol);
   if(MathAbs(s.entry - stop) < min_dist)
   {
      stop = s.is_long ? (s.entry - min_dist) : (s.entry + min_dist);
      PrintFormat("stop widened to the broker minimum distance (%.3f)", min_dist);
   }

   stop = NormalizeDouble(stop, _Digits);
   const double risk_per_unit = MathAbs(s.entry - stop);

   //--- S6 spread gate: on a tight stop the spread dominates the edge.
   const double spread = SymbolInfoDouble(_Symbol, SYMBOL_ASK)
                       - SymbolInfoDouble(_Symbol, SYMBOL_BID);
   const double spread_pct = spread / risk_per_unit * 100.0;
   if(spread_pct > MAX_SPREAD_PCT_OF_STOP)
   {
      Note(StringFormat(
         "S6: spread %.3f is %.0f%% of the %.2f stop, over the %.0f%% ceiling. "
         "Refused -- the cost would dominate the edge.",
         spread, spread_pct, risk_per_unit, MAX_SPREAD_PCT_OF_STOP));
      return;
   }

   const double first_target  = s.is_long
      ? s.entry + risk_per_unit * InpFirstTargetR
      : s.entry - risk_per_unit * InpFirstTargetR;
   const double runner_target = s.is_long
      ? s.entry + risk_per_unit * InpRunnerTargetR
      : s.entry - risk_per_unit * InpRunnerTargetR;

   //--- The blended reward/risk is the honest headline. A plan taking 60% at
   //--- 0.5R and 40% at 2.5R is 1.3R, not 2.5R.
   const double frac = InpFirstTargetPct / 100.0;
   const double blended = frac * InpFirstTargetR + (1.0 - frac) * InpRunnerTargetR;

   const double balance    = AccountInfoDouble(ACCOUNT_BALANCE);
   const double risk_money = balance * RISK_PER_TRADE_PCT / 100.0;
   string size_problem;
   const double lots = LotsForRisk(_Symbol, risk_per_unit, risk_money, size_problem);

   if(lots <= 0.0)
   {
      Note("cannot size: " + size_problem);
      return;
   }

   const string plan = StringFormat(
      "%s %s  %s\n"
      "  Entry  %.2f\n"
      "  Stop   %.2f   (%.2f = 1R, %.2f x ATR)\n"
      "  T1     %.2f   -> close %.0f%%  (%.1fR)\n"
      "  T2     %.2f   -> runner, stop to break-even after T1  (%.1fR)\n"
      "  Size   %.2f lots  (%.2f %s at risk = %.2f%%)\n"
      "  Blended R:R 1:%.2f\n"
      "  Why:   %s\n"
      "  Fails: %s\n"
      "  Session: %s",
      s.id, s.name, (s.is_long ? "LONG" : "SHORT"),
      s.entry, stop, risk_per_unit, risk_per_unit / atr_value,
      first_target, InpFirstTargetPct, InpFirstTargetR,
      runner_target, InpRunnerTargetR,
      lots, risk_money, AccountInfoString(ACCOUNT_CURRENCY), RISK_PER_TRADE_PCT,
      blended, s.evidence, s.failure_mode, session_label);

   lastSignalText = plan;
   lastSignalTime = utc;
   Print(plan);

   if(InpAlerts && !MQLInfoInteger(MQL_TESTER))
      Alert(StringFormat("%s %s %s @ %.2f  SL %.2f  %.2f lots",
                         s.id, (s.is_long ? "LONG" : "SHORT"), _Symbol,
                         s.entry, stop, lots));

   DrawSetup(s, stop, first_target, runner_target);

   if(InpMode == MODE_ADVISOR)
   {
      Print("ADVISOR MODE -- no order placed. Execute manually if you agree.");
      return;
   }

   if(CountOpenPositions() >= MAX_OPEN_POSITIONS)
   {
      Note("already at the position limit");
      return;
   }

   //--- Place with the stop attached. Never send a naked order and add the
   //--- stop afterwards: the gap between the two is exactly when gold moves.
   bool ok = s.is_long
      ? trade.Buy(lots, _Symbol, 0.0, stop, 0.0, s.id + " " + s.name)
      : trade.Sell(lots, _Symbol, 0.0, stop, 0.0, s.id + " " + s.name);

   if(!ok)
   {
      PrintFormat("order failed: %d %s", trade.ResultRetcode(),
                  trade.ResultRetcodeDescription());
      return;
   }

   // ResultOrder() is an order ticket and ResultDeal() is a deal ticket --
   // neither is the position ticket that PositionModify and PositionClose
   // need. Resolve it by symbol and magic, which is unambiguous because this
   // EA holds at most one position.
   managed.ticket = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(!pos.SelectByIndex(i)) continue;
      if(pos.Symbol() == _Symbol && pos.Magic() == InpMagic)
      {
         managed.ticket = pos.Ticket();
         break;
      }
   }
   if(managed.ticket == 0)
   {
      Print("order filled but the position could not be resolved. Managing it "
            "by hand is now required -- check the Trade tab.");
      return;
   }

   managed.entry             = pos.PriceOpen();
   managed.initial_stop      = stop;
   managed.risk_per_unit     = risk_per_unit;
   managed.first_target      = first_target;
   managed.runner_target     = runner_target;
   managed.first_target_done = false;
   managed.initial_volume    = lots;
   managed.opened_at         = utc;
   managed.setup_id          = s.id;

   day.trades_taken++;
   PrintFormat("opened #%I64u, %d of %d trades today",
               managed.ticket, day.trades_taken, MAX_TRADES_PER_DAY);
}

//+------------------------------------------------------------------+
//| Chart drawing                                                     |
//+------------------------------------------------------------------+
void DrawSetup(const Setup &s, const double stop, const double t1,
               const double t2)
{
   const string tag = "GSA_setup_";
   ObjectsDeleteAll(0, tag);
   DrawLine(tag + "entry", s.entry, clrDodgerBlue, "entry");
   DrawLine(tag + "stop",  stop,    clrCrimson,    "stop (1R)");
   DrawLine(tag + "t1",    t1,      clrLimeGreen,  "T1");
   DrawLine(tag + "t2",    t2,      clrSeaGreen,   "T2");
}

void DrawLine(const string name, const double price, const color clr,
              const string text)
{
   ObjectCreate(0, name, OBJ_HLINE, 0, 0, price);
   ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, name, OBJPROP_STYLE, STYLE_DOT);
   ObjectSetInteger(0, name, OBJPROP_WIDTH, 1);
   ObjectSetString(0, name, OBJPROP_TEXT, text);
}

void DrawDashboard(const datetime utc)
{
   string session_label;
   const SessionQuality q = ClassifySession(utc, session_label);
   string stop_reason;
   const bool stopped = ShouldStopTrading(day, utc, stop_reason);

   const string quality_text =
      (q == QUALITY_PRIME)    ? "PRIME" :
      (q == QUALITY_GOOD)     ? "good"  :
      (q == QUALITY_MARGINAL) ? "marginal" : "AVOID";

   const string text = StringFormat(
      "GoldScalpAssistant  [%s]\n"
      "Session: %s (%s)\n"
      "Day: %+.2f%%   Trades: %d/%d   Losses in a row: %d\n"
      "%s",
      (InpMode == MODE_ADVISOR ? "ADVISOR" : "AUTO"),
      quality_text, session_label,
      DayPnLPercent(day), day.trades_taken, MAX_TRADES_PER_DAY,
      day.consecutive_losses,
      (stopped ? "STOPPED: " + stop_reason : "running"));

   const string name = "GSA_panel";
   if(ObjectFind(0, name) < 0)
   {
      ObjectCreate(0, name, OBJ_LABEL, 0, 0, 0);
      ObjectSetInteger(0, name, OBJPROP_CORNER, CORNER_LEFT_UPPER);
      ObjectSetInteger(0, name, OBJPROP_XDISTANCE, 10);
      ObjectSetInteger(0, name, OBJPROP_YDISTANCE, 20);
      ObjectSetInteger(0, name, OBJPROP_FONTSIZE, 9);
      ObjectSetString(0, name, OBJPROP_FONT, "Consolas");
   }
   ObjectSetString(0, name, OBJPROP_TEXT, text);
   ObjectSetInteger(0, name, OBJPROP_COLOR,
                    stopped ? clrCrimson
                            : (q == QUALITY_PRIME ? clrLimeGreen : clrSilver));
}

//+------------------------------------------------------------------+
