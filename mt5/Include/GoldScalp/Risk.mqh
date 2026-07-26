//+------------------------------------------------------------------+
//| Risk.mqh - hard risk rules for the gold scalping assistant        |
//|                                                                  |
//| Mirrors metals/risk.py and metals/exits.py. The limits are        |
//| compile-time constants, not inputs, for the same reason they are  |
//| module constants in Python: a limit you can change from the       |
//| settings dialog at 15:30 on a bad day is not a limit.             |
//+------------------------------------------------------------------+
#property copyright "Trade- project"
#property strict

//--- Hard limits. Changing one requires editing and recompiling.
#define RISK_PER_TRADE_PCT      1.0    // R1
#define DAILY_LOSS_LIMIT_PCT    3.0    // R2
#define DAILY_WIN_TARGET_PCT    2.0    // stop on a good day too
#define MIN_REWARD_RISK         2.0    // R3
#define MAX_TRADES_PER_DAY      4
#define MAX_CONSECUTIVE_LOSSES  2
#define COOLDOWN_AFTER_LOSS_MIN 20
#define MAX_OPEN_POSITIONS      1      // one scalp at a time

//--- Metal-specific (M1-M6)
#define MIN_STOP_ATR_MULTIPLE   0.8    // M1
#define STOP_BUFFER_ATR         0.35   // M2
#define MAX_SPREAD_ATR_FRACTION 0.15   // M3
#define MAX_SPREAD_PCT_OF_STOP  10.0   // S6 spread gate
#define FRIDAY_FLAT_HOUR_UTC    19     // M5

//+------------------------------------------------------------------+
//| Result of a risk check: why a trade was refused, in plain words.  |
//+------------------------------------------------------------------+
struct RiskVerdict
{
   bool     allowed;
   double   lots;
   string   reason;
};

//+------------------------------------------------------------------+
//| Broker constraints that a scalping stop routinely collides with.  |
//|                                                                  |
//| SYMBOL_TRADE_STOPS_LEVEL is the minimum distance, in points, that |
//| a stop or limit may sit from the current price. Gold brokers      |
//| commonly set it to 10-50 points, which on a 2-decimal quote is    |
//| 0.10-0.50 USD/oz. A scalping stop tighter than that is simply     |
//| rejected by the server -- a failure mode that does not exist in a |
//| backtest and bites immediately live.                              |
//+------------------------------------------------------------------+
double MinStopDistance(const string symbol)
{
   const long   stops_level = SymbolInfoInteger(symbol, SYMBOL_TRADE_STOPS_LEVEL);
   const long   freeze      = SymbolInfoInteger(symbol, SYMBOL_TRADE_FREEZE_LEVEL);
   const double point       = SymbolInfoDouble(symbol, SYMBOL_POINT);
   const double spread      = (SymbolInfoDouble(symbol, SYMBOL_ASK)
                               - SymbolInfoDouble(symbol, SYMBOL_BID));
   // Take the worst of the three constraints and add the current spread,
   // because the stop is checked against the opposite side of the book.
   const double from_level  = (double)MathMax(stops_level, freeze) * point;
   return from_level + spread;
}

//+------------------------------------------------------------------+
//| Position size from risk, using the broker's own tick value.       |
//|                                                                  |
//| This deliberately does NOT hard-code a contract size. The Python  |
//| side has to assume 100 oz per lot and warn about it; here the     |
//| terminal knows the real figure, so ask it. This is the one place  |
//| the MT5 version is strictly better than the Python one.           |
//+------------------------------------------------------------------+
double LotsForRisk(const string symbol, const double stop_distance,
                   const double risk_money, string &why)
{
   const double tick_value = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_VALUE);
   const double tick_size  = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_SIZE);
   const double vol_min    = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
   const double vol_max    = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MAX);
   const double vol_step   = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);

   if(tick_value <= 0.0 || tick_size <= 0.0 || stop_distance <= 0.0)
   {
      why = "cannot size: tick value/size unavailable or stop distance is zero";
      return 0.0;
   }

   const double loss_per_lot = (stop_distance / tick_size) * tick_value;
   if(loss_per_lot <= 0.0)
   {
      why = "cannot size: computed loss per lot is not positive";
      return 0.0;
   }

   double lots = risk_money / loss_per_lot;

   // Always round DOWN. Rounding up exceeds the risk limit, which is the one
   // direction the error must never take.
   lots = MathFloor(lots / vol_step) * vol_step;
   lots = NormalizeDouble(lots, 2);

   if(lots < vol_min)
   {
      why = StringFormat(
         "position rounds to %.4f lots, below the broker minimum of %.2f. "
         "A %.2f stop on this account cannot be taken within %.2f%% risk. "
         "That is an account-size constraint, not a signal problem -- do not "
         "solve it by widening risk.",
         lots, vol_min, stop_distance, RISK_PER_TRADE_PCT);
      return 0.0;
   }
   if(lots > vol_max)
      lots = vol_max;

   why = "";
   return lots;
}

//+------------------------------------------------------------------+
//| Day state, persisted across ticks and restarts within a session.  |
//+------------------------------------------------------------------+
struct DayState
{
   datetime day_start;
   double   start_equity;
   int      trades_taken;
   int      consecutive_losses;
   datetime last_close_time;
   bool     last_was_loss;
};

void ResetDay(DayState &state, const datetime now)
{
   MqlDateTime dt;
   TimeToStruct(now, dt);
   dt.hour = 0; dt.min = 0; dt.sec = 0;
   state.day_start          = StructToTime(dt);
   state.start_equity       = AccountInfoDouble(ACCOUNT_EQUITY);
   state.trades_taken       = 0;
   state.consecutive_losses = 0;
   state.last_close_time    = 0;
   state.last_was_loss      = false;
}

double DayPnLPercent(const DayState &state)
{
   if(state.start_equity <= 0.0)
      return 0.0;
   const double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   return (equity - state.start_equity) / state.start_equity * 100.0;
}

//+------------------------------------------------------------------+
//| Should trading continue at all right now?                         |
//|                                                                  |
//| Hard stops first and exclusively: once one fires, the softer      |
//| reasons are suppressed. Listing them alongside a hard stop only   |
//| invites the trader to negotiate with it.                          |
//+------------------------------------------------------------------+
bool ShouldStopTrading(const DayState &state, const datetime now, string &reason)
{
   const double pnl = DayPnLPercent(state);

   if(pnl <= -DAILY_LOSS_LIMIT_PCT)
   {
      reason = StringFormat(
         "R2: day at %.2f%%, the -%.1f%% limit is reached. Finished until the "
         "next session. This rule exists because the trade taken to recover a "
         "bad day is the one that turns a bad day into a bad month.",
         pnl, DAILY_LOSS_LIMIT_PCT);
      return true;
   }
   if(pnl >= DAILY_WIN_TARGET_PCT)
   {
      reason = StringFormat(
         "Day target reached at +%.2f%%. Stopping. Giving back a good day is "
         "the most common way a good week is lost.", pnl);
      return true;
   }
   if(state.consecutive_losses >= MAX_CONSECUTIVE_LOSSES)
   {
      reason = StringFormat(
         "%d losses in a row. Two consecutive losses usually mean the regime "
         "no longer matches the setups, not that the next trade is due.",
         state.consecutive_losses);
      return true;
   }
   if(state.trades_taken >= MAX_TRADES_PER_DAY)
   {
      reason = StringFormat(
         "%d trades today, the daily cap. Past this point you are trading "
         "boredom, not setups.", state.trades_taken);
      return true;
   }
   reason = "";
   return false;
}

//+------------------------------------------------------------------+
//| Cooldown after a loss. Not a hard stop -- a delay.                |
//+------------------------------------------------------------------+
bool InCooldown(const DayState &state, const datetime now, string &reason)
{
   if(!state.last_was_loss || state.last_close_time == 0)
      return false;
   const int elapsed_min = (int)((now - state.last_close_time) / 60);
   if(elapsed_min >= COOLDOWN_AFTER_LOSS_MIN)
      return false;
   reason = StringFormat(
      "cooldown: last trade was a loss %d minutes ago, waiting %d. The trade "
      "straight after a loss is statistically the worst of the day.",
      elapsed_min, COOLDOWN_AFTER_LOSS_MIN);
   return true;
}
//+------------------------------------------------------------------+
