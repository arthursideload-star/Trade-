//+------------------------------------------------------------------+
//|                                        GoldScalpAssistant.mq5    |
//|                                             Trade- project        |
//|                                                                  |
//| Gold scalping assistant for MetaTrader 5. ONE FILE -- copy it to  |
//| MQL5/Experts and press F7. No include folder to create.           |
//|                                                                  |
//| Implements the same setups and the same hard risk limits as the   |
//| Python package in metals/, so that what is measured there and     |
//| what runs here are the same system rather than two similar ones.  |
//| tests/test_mt5_parity.py checks that the limits below still equal |
//| their Python counterparts.                                        |
//|                                                                  |
//| MODES                                                             |
//|   Advisor - draws the setup, sizes it, prints the plan, alerts.   |
//|             Places no orders. The default, and the honest place   |
//|             to start: it lets you compare its judgement against   |
//|             your own before it is allowed to spend anything.      |
//|   Auto    - places and manages the trade itself.                  |
//|                                                                  |
//| READ BEFORE ENABLING AUTO                                         |
//| The strategy behind this EA has NOT been shown to have a positive |
//| expectancy. It was evaluated across 100 simulated markets in 17   |
//| configurations and every one lost money, including a variant with |
//| zero spread. That evaluation could not test its core bet (see     |
//| docs/BACKTEST-ERGEBNISSE.md), so the result is inconclusive, not  |
//| damning -- but "inconclusive" is not "profitable". Demo only,     |
//| until you have your own numbers over at least 30 trades.          |
//|                                                                  |
//| What this EA does reliably is enforce discipline: position sizes  |
//| that are correct, stops that survive normal noise, a daily loss   |
//| limit that actually stops, and a refusal to trade the windows     |
//| where gold's spread eats the edge.                                |
//+------------------------------------------------------------------+
#property copyright "Trade- project"
#property link      "https://github.com/arthursideload-star/Trade-"
#property version   "1.10"
#property strict

#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>

//====================================================================
// SECTION 1 -- HARD LIMITS
//
// These are #defines, not inputs, on purpose. A risk limit you can
// change from the settings dialog at 15:30 on a bad day is not a
// limit. Changing one requires editing this file and recompiling,
// which leaves a trace and takes a minute of thought.
//====================================================================

#define RISK_PER_TRADE_PCT      1.0    // R1
#define DAILY_LOSS_LIMIT_PCT    3.0    // R2
#define DAILY_WIN_TARGET_PCT    2.0    // stop on a good day too
#define MIN_REWARD_RISK         2.0    // R3
#define MAX_TRADES_PER_DAY      4
#define MAX_CONSECUTIVE_LOSSES  2
#define COOLDOWN_AFTER_LOSS_MIN 20
#define MAX_OPEN_POSITIONS      1      // one scalp at a time

// Metal-specific (M1-M6 in the Python package)
#define MIN_STOP_ATR_MULTIPLE   0.8    // M1: tighter than this is noise
#define STOP_BUFFER_ATR         0.35   // M2: beyond the level, never on it
#define MAX_SPREAD_ATR_FRACTION 0.15   // M3
#define MAX_SPREAD_PCT_OF_STOP  10.0   // S6 spread gate
#define FRIDAY_FLAT_HOUR_UTC    19     // M5: a stop does not cover a gap

//====================================================================
// SECTION 2 -- INPUTS
//====================================================================

enum ENUM_RUN_MODE
{
   MODE_ADVISOR = 0,   // Advisor - signals only, places no orders
   MODE_AUTO    = 1    // Auto - places and manages trades
};

input group "=== Operation ==="
input ENUM_RUN_MODE InpMode            = MODE_ADVISOR; // Run mode
input long          InpMagic           = 20260726;     // Magic number
input bool          InpPrimeOnly       = true;         // Prime windows only
input bool          InpAlerts          = true;         // Pop-up on a signal
input bool          InpDashboard       = true;         // On-chart panel

input group "=== Setups (all read M5) ==="
input bool          InpUseS2           = true;  // S2 Pullback Window Break
input bool          InpUseS4           = true;  // S4 Round Number Fade
input bool          InpUseS5           = true;  // S5 Momentum Continuation

input group "=== Exits ==="
input double        InpFirstTargetR    = 0.5;   // First target in R (measured: 0.5 beats 1.0)
input double        InpFirstTargetPct  = 60.0;  // Percent closed at first target
input double        InpRunnerTargetR   = 2.5;   // Runner target in R
input double        InpTrailAtrMult    = 1.2;   // Trail distance in ATR
input int           InpTimeStopMinutes = 45;    // Close regardless after N minutes

input group "=== Filters ==="
input int           InpAtrPeriod       = 14;    // ATR period (M5)
input int           InpNewsBlackoutMin = 30;    // Minutes around the data windows
input bool          InpBlockNewsWindow = true;  // Apply the news blackout

//====================================================================
// SECTION 3 -- GLOBALS
//====================================================================

CTrade         trade;
CPositionInfo  pos;

int      hAtr   = INVALID_HANDLE;
int      hEma9  = INVALID_HANDLE;
int      hEma21 = INVALID_HANDLE;
int      hEma50 = INVALID_HANDLE;

datetime lastBarTime = 0;

struct DayState
{
   datetime day_start;
   double   start_equity;
   int      trades_taken;
   int      consecutive_losses;
   datetime last_close_time;
   bool     last_was_loss;
};
DayState day;

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

string lastNote = "";

//--- Log a reason once rather than on every bar.
void Note(const string text)
{
   if(text == lastNote) return;
   lastNote = text;
   Print(text);
}

//====================================================================
// SECTION 4 -- TIME AND SESSIONS
//
// Two things here are easy to get wrong and both silently break every
// time-dependent setup:
//
// 1. Broker server time is NOT UTC. It is commonly GMT+2/+3 and it
//    shifts with the broker's own daylight saving. Everything below
//    works in UTC and converts once, at the edge.
// 2. London and New York shift on different dates. Hard-coding the
//    overlap to a UTC range puts every London-open setup an hour out
//    for several weeks a year.
//
// The daylight-saving arithmetic here is checked hourly across four
// years against the Python implementation in tests/test_mt5_parity.py.
//====================================================================

int ServerOffsetSeconds()
{
   return (int)(TimeTradeServer() - TimeGMT());
}

datetime ServerToUtc(const datetime server_time)
{
   return server_time - ServerOffsetSeconds();
}

int DaysInMonth(const int year, const int month)
{
   const int days[12] = {31,28,31,30,31,30,31,31,30,31,30,31};
   if(month == 2)
   {
      const bool leap = (year % 4 == 0 && year % 100 != 0) || (year % 400 == 0);
      return leap ? 29 : 28;
   }
   return days[month - 1];
}

datetime LastSundayOfMonth(const int year, const int month)
{
   MqlDateTime dt;
   dt.year = year;
   dt.mon  = month;
   dt.day  = DaysInMonth(year, month);
   dt.hour = 0; dt.min = 0; dt.sec = 0;
   const datetime last_day = StructToTime(dt);
   MqlDateTime out;
   TimeToStruct(last_day, out);
   return last_day - out.day_of_week * 86400;   // day_of_week: 0 = Sunday
}

datetime NthSundayOfMonth(const int year, const int month, const int n)
{
   MqlDateTime dt;
   dt.year = year; dt.mon = month; dt.day = 1;
   dt.hour = 0; dt.min = 0; dt.sec = 0;
   const datetime first = StructToTime(dt);
   MqlDateTime out;
   TimeToStruct(first, out);
   const int to_sunday = (7 - out.day_of_week) % 7;
   return first + (to_sunday + (n - 1) * 7) * 86400;
}

bool EuSummerTime(const datetime utc)
{
   MqlDateTime dt;
   TimeToStruct(utc, dt);
   const datetime start = LastSundayOfMonth(dt.year, 3)  + 3600;   // 01:00 UTC
   const datetime end   = LastSundayOfMonth(dt.year, 10) + 3600;
   return (utc >= start && utc < end);
}

bool UsDaylightTime(const datetime utc)
{
   MqlDateTime dt;
   TimeToStruct(utc, dt);
   const datetime start = NthSundayOfMonth(dt.year, 3, 2)  + 7 * 3600;
   const datetime end   = NthSundayOfMonth(dt.year, 11, 1) + 6 * 3600;
   return (utc >= start && utc < end);
}

int LondonOffsetHours(const datetime utc)  { return EuSummerTime(utc) ? 1 : 0; }
int NewYorkOffsetHours(const datetime utc) { return UsDaylightTime(utc) ? -4 : -5; }

int LocalHour(const datetime utc, const int offset_hours)
{
   MqlDateTime dt;
   TimeToStruct(utc + offset_hours * 3600, dt);
   return dt.hour;
}

enum SessionQuality
{
   QUALITY_PRIME,
   QUALITY_GOOD,
   QUALITY_MARGINAL,
   QUALITY_AVOID
};

bool MarketOpen(const datetime utc)
{
   MqlDateTime dt;
   TimeToStruct(utc, dt);
   const int wd = dt.day_of_week;        // 0 = Sunday
   if(wd == 6) return false;             // Saturday
   if(wd == 0) return dt.hour >= 22;     // Sunday evening open
   if(wd == 5 && dt.hour >= 21) return false;
   return true;
}

bool InRollover(const datetime utc)
{
   MqlDateTime dt;
   TimeToStruct(utc, dt);
   return (dt.hour >= 21 && dt.hour < 23);
}

SessionQuality ClassifySession(const datetime utc, string &label)
{
   if(!MarketOpen(utc))
   {
      label = "market closed";
      return QUALITY_AVOID;
   }
   if(InRollover(utc))
   {
      label = "daily rollover: spreads widen severalfold, swap is charged";
      return QUALITY_AVOID;
   }

   MqlDateTime dt;
   TimeToStruct(utc, dt);
   const int ldn = LocalHour(utc, LondonOffsetHours(utc));
   const int nyc = LocalHour(utc, NewYorkOffsetHours(utc));

   const bool london_kz = (ldn >= 7  && ldn < 10);
   const bool ny_kz     = (nyc >= 8  && nyc < 11);
   const bool overlap   = (ldn >= 13 && ldn < 17) && (nyc >= 8 && nyc < 12);

   if(overlap)
   {
      label = "London/New York overlap -- tightest spreads of the day";
      return QUALITY_PRIME;
   }
   if(ny_kz)
   {
      label = "New York killzone -- largest ranges, real participation";
      return QUALITY_PRIME;
   }
   if(london_kz)
   {
      label = "London killzone -- the session's move usually starts here";
      return QUALITY_PRIME;
   }
   if(dt.day_of_week == 5 && dt.hour >= FRIDAY_FLAT_HOUR_UTC)
   {
      label = "Friday late -- weekend gap risk, a stop does not cover a gap";
      return QUALITY_AVOID;
   }
   if(dt.hour < 7)
   {
      // Measured across 100 simulated markets as the worst session by a wide
      // margin. Excluded rather than merely discounted.
      label = "Asian session -- thin for gold, breakouts fail more often";
      return QUALITY_MARGINAL;
   }

   label = "regular session hours";
   return QUALITY_GOOD;
}

bool IsTradableSession(const datetime utc, const bool prime_only, string &label)
{
   const SessionQuality q = ClassifySession(utc, label);
   if(q == QUALITY_AVOID) return false;
   if(q == QUALITY_MARGINAL)
   {
      label = "marginal session: " + label;
      return false;
   }
   if(prime_only && q != QUALITY_PRIME)
   {
      label = "not a prime window: " + label;
      return false;
   }
   return true;
}

//====================================================================
// SECTION 5 -- RISK AND SIZING
//====================================================================

//--- Broker constraints a scalping stop routinely collides with.
//--- SYMBOL_TRADE_STOPS_LEVEL is the minimum distance a stop may sit
//--- from price. On gold it is commonly 10-50 points = 0.10-0.50
//--- USD/oz. A tighter stop is simply rejected by the server -- a
//--- failure that does not exist in a backtest and bites immediately.
double MinStopDistance(const string symbol)
{
   const long   stops_level = SymbolInfoInteger(symbol, SYMBOL_TRADE_STOPS_LEVEL);
   const long   freeze      = SymbolInfoInteger(symbol, SYMBOL_TRADE_FREEZE_LEVEL);
   const double point       = SymbolInfoDouble(symbol, SYMBOL_POINT);
   const double spread      = SymbolInfoDouble(symbol, SYMBOL_ASK)
                            - SymbolInfoDouble(symbol, SYMBOL_BID);
   const double from_level  = (double)MathMax(stops_level, freeze) * point;
   return from_level + spread;
}

//--- Position size from risk, using the broker's own tick value.
//--- This deliberately does NOT hard-code a contract size. The Python
//--- side has to assume 100 oz per lot and warn about it; here the
//--- terminal knows the real figure, so ask it. This is the one place
//--- the MT5 version is strictly better than the Python one.
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

   // Always round DOWN. Rounding up exceeds the risk limit, which is the one
   // direction the error must never take.
   double lots = MathFloor((risk_money / loss_per_lot) / vol_step) * vol_step;
   lots = NormalizeDouble(lots, 2);

   if(lots < vol_min)
   {
      why = StringFormat(
         "position rounds to %.4f lots, below the broker minimum of %.2f. "
         "A %.2f stop on this balance cannot be taken within %.1f%% risk. "
         "That is an account-size constraint, not a signal problem -- do not "
         "solve it by widening risk.",
         lots, vol_min, stop_distance, RISK_PER_TRADE_PCT);
      return 0.0;
   }
   if(lots > vol_max) lots = vol_max;

   why = "";
   return lots;
}

double DayPnLPercent()
{
   if(day.start_equity <= 0.0) return 0.0;
   return (AccountInfoDouble(ACCOUNT_EQUITY) - day.start_equity)
          / day.start_equity * 100.0;
}

//--- Hard stops first and exclusively: once one fires, the softer
//--- reasons are suppressed. Listing them alongside a hard stop only
//--- invites the trader to negotiate with it.
bool ShouldStopTrading(string &reason)
{
   const double pnl = DayPnLPercent();

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
   if(day.consecutive_losses >= MAX_CONSECUTIVE_LOSSES)
   {
      reason = StringFormat(
         "%d losses in a row. Two consecutive losses usually mean the regime "
         "no longer matches the setups, not that the next trade is due.",
         day.consecutive_losses);
      return true;
   }
   if(day.trades_taken >= MAX_TRADES_PER_DAY)
   {
      reason = StringFormat(
         "%d trades today, the daily cap. Past this point you are trading "
         "boredom, not setups.", day.trades_taken);
      return true;
   }
   reason = "";
   return false;
}

bool InCooldown(const datetime utc, string &reason)
{
   if(!day.last_was_loss || day.last_close_time == 0) return false;
   const int elapsed = (int)((utc - day.last_close_time) / 60);
   if(elapsed >= COOLDOWN_AFTER_LOSS_MIN) return false;
   reason = StringFormat(
      "cooldown: last trade was a loss %d minutes ago, waiting %d. The trade "
      "straight after a loss is statistically the worst of the day.",
      elapsed, COOLDOWN_AFTER_LOSS_MIN);
   return true;
}

//====================================================================
// SECTION 6 -- STATE RECOVERY
//
// The EA is reloaded on every timeframe change, parameter edit,
// terminal restart and VPS migration. Without recovery two things
// break, and both matter far more in Auto mode than they look:
//
//   * an open position becomes unmanaged -- no partial, no
//     break-even, no trail, no time stop. Only the original stop
//     protects it, which is the worst of both worlds.
//   * the day counters reset to zero, so the daily trade cap and the
//     loss limit can be silently exceeded by restarting.
//
// Both are reconstructed from the terminal's own records on init.
//====================================================================

datetime StartOfDayUtc(const datetime utc)
{
   MqlDateTime dt;
   TimeToStruct(utc, dt);
   dt.hour = 0; dt.min = 0; dt.sec = 0;
   return StructToTime(dt);
}

//--- Rebuild today's counters from the deal history.
void RebuildDayState(const datetime utc)
{
   day.day_start          = StartOfDayUtc(utc);
   day.trades_taken       = 0;
   day.consecutive_losses = 0;
   day.last_close_time    = 0;
   day.last_was_loss      = false;

   const datetime from_server = day.day_start + ServerOffsetSeconds();
   if(!HistorySelect(from_server, TimeTradeServer() + 60))
   {
      day.start_equity = AccountInfoDouble(ACCOUNT_EQUITY);
      return;
   }

   double realised = 0.0;
   const int deals = HistoryDealsTotal();
   for(int i = 0; i < deals; i++)
   {
      const ulong ticket = HistoryDealGetTicket(i);
      if(ticket == 0) continue;
      if(HistoryDealGetInteger(ticket, DEAL_MAGIC) != InpMagic) continue;
      if(HistoryDealGetString(ticket, DEAL_SYMBOL) != _Symbol) continue;

      const long entry_type = HistoryDealGetInteger(ticket, DEAL_ENTRY);
      if(entry_type == DEAL_ENTRY_IN)
      {
         day.trades_taken++;
         continue;
      }
      if(entry_type != DEAL_ENTRY_OUT) continue;

      const double profit = HistoryDealGetDouble(ticket, DEAL_PROFIT)
                          + HistoryDealGetDouble(ticket, DEAL_SWAP)
                          + HistoryDealGetDouble(ticket, DEAL_COMMISSION);
      realised += profit;
      day.last_close_time = ServerToUtc(
         (datetime)HistoryDealGetInteger(ticket, DEAL_TIME));
      day.last_was_loss = (profit < 0.0);
      if(profit < 0.0) day.consecutive_losses++;
      else             day.consecutive_losses = 0;
   }

   // Equity at the start of the day, derived backwards from what has been
   // realised since. Not exact when other EAs trade the same account, which
   // is one reason to give this EA an account to itself.
   day.start_equity = AccountInfoDouble(ACCOUNT_EQUITY) - realised;
   if(day.start_equity <= 0.0)
      day.start_equity = AccountInfoDouble(ACCOUNT_EQUITY);

   if(day.trades_taken > 0)
      PrintFormat("recovered day state: %d trade(s) already taken today, "
                  "%d consecutive loss(es), day P/L %.2f%%",
                  day.trades_taken, day.consecutive_losses, DayPnLPercent());
}

//--- Adopt a position this EA opened before the reload.
bool AdoptExistingPosition(const datetime utc)
{
   ZeroMemory(managed);
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(!pos.SelectByIndex(i)) continue;
      if(pos.Symbol() != _Symbol || pos.Magic() != InpMagic) continue;

      const bool is_long = (pos.PositionType() == POSITION_TYPE_BUY);
      managed.ticket         = pos.Ticket();
      managed.entry          = pos.PriceOpen();
      managed.initial_stop   = pos.StopLoss();
      managed.initial_volume = pos.Volume();
      managed.opened_at      = ServerToUtc(pos.Time());
      managed.setup_id       = "adopted";

      if(managed.initial_stop <= 0.0)
      {
         // A position with no stop is the one situation this EA must never
         // leave alone. Close it rather than manage something whose risk is
         // undefined (R7).
         Print("adopted a position with NO stop loss. Closing it: a position "
               "without a defined invalidation is not a trade, it is an open "
               "bill.");
         trade.PositionClose(managed.ticket);
         ZeroMemory(managed);
         return false;
      }

      managed.risk_per_unit = MathAbs(managed.entry - managed.initial_stop);

      // Whether the partial was already taken cannot be read back directly.
      // A stop at or beyond entry means break-even was set, which only
      // happens after the first target fills -- so infer from that, and
      // err towards "already done" so the partial is never taken twice.
      managed.first_target_done = is_long
         ? (managed.initial_stop >= managed.entry - _Point)
         : (managed.initial_stop <= managed.entry + _Point);

      if(managed.first_target_done)
      {
         // Break-even is in place, so the original risk is unknown. Rebuild
         // it from ATR rather than from a stop that has already moved.
         double atr[];
         if(CopyBuffer(hAtr, 0, 1, 1, atr) > 0 && atr[0] > 0.0)
            managed.risk_per_unit = atr[0] * MIN_STOP_ATR_MULTIPLE;
      }

      managed.first_target = is_long
         ? managed.entry + managed.risk_per_unit * InpFirstTargetR
         : managed.entry - managed.risk_per_unit * InpFirstTargetR;
      managed.runner_target = is_long
         ? managed.entry + managed.risk_per_unit * InpRunnerTargetR
         : managed.entry - managed.risk_per_unit * InpRunnerTargetR;

      PrintFormat("adopted open position #%I64u (%s %.2f lots from %s). "
                  "First target %s. Management resumes.",
                  managed.ticket, (is_long ? "long" : "short"),
                  managed.initial_volume,
                  TimeToString(pos.Time(), TIME_DATE | TIME_MINUTES),
                  (managed.first_target_done ? "already taken" : "still ahead"));
      return true;
   }
   return false;
}

//====================================================================
// SECTION 7 -- LIFECYCLE
//====================================================================

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

   const datetime utc = ServerToUtc(TimeTradeServer());
   RebuildDayState(utc);
   AdoptExistingPosition(utc);

   if(StringFind(_Symbol, "XAU") < 0 && StringFind(_Symbol, "GOLD") < 0)
      Print("WARNING: this EA is built for gold. Symbol is ", _Symbol,
            " -- the ATR bands, the round-number grid and the session logic "
            "assume XAU/USD and will be wrong elsewhere.");

   if(!AccountInfoInteger(ACCOUNT_TRADE_EXPERT))
      Print("WARNING: algo trading is disabled for this account. Nothing will "
            "be placed even in Auto mode.");

   const bool is_demo =
      (AccountInfoInteger(ACCOUNT_TRADE_MODE) == ACCOUNT_TRADE_MODE_DEMO);
   if(InpMode == MODE_AUTO && !is_demo && !MQLInfoInteger(MQL_TESTER))
      Print("WARNING: Auto mode on a LIVE account. This strategy has no "
            "demonstrated positive expectancy -- see "
            "docs/BACKTEST-ERGEBNISSE.md. Demo is where this belongs.");

   PrintFormat("GoldScalpAssistant %s | %s | risk %.1f%%/trade, daily stop "
               "-%.1f%%, daily target +%.1f%%, max %d trades/day",
               (InpMode == MODE_ADVISOR ? "ADVISOR (no orders)" : "AUTO"),
               (is_demo ? "DEMO" : "LIVE"),
               RISK_PER_TRADE_PCT, DAILY_LOSS_LIMIT_PCT,
               DAILY_WIN_TARGET_PCT, MAX_TRADES_PER_DAY);

   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   IndicatorRelease(hAtr);
   IndicatorRelease(hEma9);
   IndicatorRelease(hEma21);
   IndicatorRelease(hEma50);
   ObjectsDeleteAll(0, "GSA_");
}

void OnTick()
{
   const datetime utc = ServerToUtc(TimeTradeServer());

   RollDayIfNeeded(utc);

   // Managing an open position happens every tick; looking for a new one
   // happens once per closed bar. Exits must not wait for a bar close.
   if(managed.ticket != 0)
      ManageOpenPosition(utc);

   if(InpDashboard) DrawDashboard(utc);

   const datetime bar = iTime(_Symbol, PERIOD_M5, 0);
   if(bar == lastBarTime) return;
   lastBarTime = bar;

   if(managed.ticket == 0)
      LookForSetup(utc);
}

void RollDayIfNeeded(const datetime utc)
{
   if(StartOfDayUtc(utc) == day.day_start) return;
   PrintFormat("New session. Yesterday closed at %.2f%% over %d trade(s).",
               DayPnLPercent(), day.trades_taken);
   day.day_start          = StartOfDayUtc(utc);
   day.start_equity       = AccountInfoDouble(ACCOUNT_EQUITY);
   day.trades_taken       = 0;
   day.consecutive_losses = 0;
   day.last_close_time    = 0;
   day.last_was_loss      = false;
}

//====================================================================
// SECTION 8 -- EXIT MANAGEMENT
//====================================================================

void ManageOpenPosition(const datetime utc)
{
   if(!pos.SelectByTicket(managed.ticket))
   {
      // Closed outside our control: stop hit, manual close, margin call.
      RecordClosedTrade();
      ZeroMemory(managed);
      return;
   }

   const bool   is_long = (pos.PositionType() == POSITION_TYPE_BUY);
   const double price   = is_long ? SymbolInfoDouble(_Symbol, SYMBOL_BID)
                                  : SymbolInfoDouble(_Symbol, SYMBOL_ASK);

   //--- Time stop. A scalp that has not worked inside its own horizon is no
   //--- longer the trade that was entered; it is a swing trade with a
   //--- scalping stop, which is the worst combination.
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
      if(hit) TakePartialAndMoveToBreakEven(is_long, price);
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

   TrailRunner(is_long, price);
}

void TakePartialAndMoveToBreakEven(const bool is_long, const double price)
{
   const double vol_step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   const double vol_min  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double part = MathFloor((pos.Volume() * InpFirstTargetPct / 100.0) / vol_step)
                 * vol_step;
   const double remaining = pos.Volume() - part;

   // If either side of the split falls under the broker minimum, a partial is
   // impossible. Closing in full is the honest fallback -- a small win beats
   // an order the server rejects while price walks away.
   if(part < vol_min || remaining < vol_min)
   {
      CloseAll(StringFormat(
         "first target reached but a partial is not possible: %.2f/%.2f lots "
         "against a %.2f minimum. Closing in full.", part, remaining, vol_min));
      return;
   }

   if(!trade.PositionClosePartial(managed.ticket, part))
   {
      PrintFormat("partial close failed: %d %s", trade.ResultRetcode(),
                  trade.ResultRetcodeDescription());
      return;
   }

   managed.first_target_done = true;
   PrintFormat("banked %.0f%% at %.2f (%.2fR). Remainder runs.",
               InpFirstTargetPct, managed.first_target, InpFirstTargetR);

   const double min_dist = MinStopDistance(_Symbol);
   if(MathAbs(price - managed.entry) < min_dist)
   {
      Print("break-even stop is inside the broker's minimum stop distance; "
            "leaving the original stop until price moves further");
      return;
   }
   if(!trade.PositionModify(managed.ticket,
                            NormalizeDouble(managed.entry, _Digits),
                            pos.TakeProfit()))
      PrintFormat("break-even modify failed: %d %s", trade.ResultRetcode(),
                  trade.ResultRetcodeDescription());
   else
      Print("stop to break-even -- the remainder is now a free option, which "
            "is the point of taking the partial");
}

void TrailRunner(const bool is_long, const double price)
{
   double atr[];
   if(CopyBuffer(hAtr, 0, 0, 1, atr) < 1) return;
   const double use_dist = MathMax(atr[0] * InpTrailAtrMult,
                                   MinStopDistance(_Symbol));
   const double current  = pos.StopLoss();
   double candidate = NormalizeDouble(
      is_long ? (price - use_dist) : (price + use_dist), _Digits);

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

void RecordClosedTrade()
{
   if(!HistorySelect(day.day_start + ServerOffsetSeconds(),
                     TimeTradeServer() + 60))
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
   if(profit < 0.0) day.consecutive_losses++;
   else             day.consecutive_losses = 0;

   PrintFormat("trade closed, result %.2f %s. Day %.2f%%, %d trades, %d "
               "consecutive loss(es).", profit,
               AccountInfoString(ACCOUNT_CURRENCY), DayPnLPercent(),
               day.trades_taken, day.consecutive_losses);
}

//====================================================================
// SECTION 9 -- SETUP DETECTION
//====================================================================

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

   if(ShouldStopTrading(reason))       { Note("STOP: " + reason); return; }
   if(InCooldown(utc, reason))         { Note(reason);            return; }

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

   Setup s; ZeroMemory(s);
   if(InpUseS2 && !s.found) s = DetectS2(atr_value);
   if(InpUseS5 && !s.found) s = DetectS5(atr_value);
   if(InpUseS4 && !s.found) s = DetectS4(atr_value);
   if(!s.found)
   {
      Note("no setup. Most bars are not an opportunity.");
      return;
   }

   ExecuteOrAdvise(s, atr_value, session_label);
}

//--- S2: EMA stack sets direction, 1-3 counter-trend candles form the
//--- pullback, the break of its extreme is the entry. The depth cap is
//--- the point: a pullback deeper than three bars is a reversal in
//--- progress, not a pause.
Setup DetectS2(const double atr_value)
{
   Setup s; ZeroMemory(s);

   double e9[], e21[], e50[], e21_prev[];
   if(CopyBuffer(hEma9,  0, 1, 1, e9)       < 1) return s;
   if(CopyBuffer(hEma21, 0, 1, 1, e21)      < 1) return s;
   if(CopyBuffer(hEma50, 0, 1, 1, e50)      < 1) return s;
   if(CopyBuffer(hEma21, 0, 6, 1, e21_prev) < 1) return s;

   const bool up   = (e9[0] > e21[0] && e21[0] > e50[0]);
   const bool down = (e9[0] < e21[0] && e21[0] < e50[0]);
   if(!up && !down) return s;

   //--- Slope filter. A flat stack is a range wearing a trend's clothes;
   //--- without this the setup fires all day in chop and loses on spread.
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

   const bool broke = up ? (r[0].close > trigger) : (r[0].close < trigger);
   if(!broke) return s;

   s.found            = true;
   s.id               = "S2";
   s.name             = "Pullback Window Break";
   s.is_long          = up;
   s.entry            = up ? SymbolInfoDouble(_Symbol, SYMBOL_ASK)
                           : SymbolInfoDouble(_Symbol, SYMBOL_BID);
   s.structural_level = extreme;
   s.evidence = StringFormat(
      "EMA9/21/50 stacked %s, 21-EMA slope %+.2f x ATR, %d-bar pullback "
      "broken at %.2f", (up ? "up" : "down"), slope, counter, trigger);
   s.failure_mode = "The EMA stack is flat and the 'trend' is a range. The "
                    "slope filter exists for this.";
   return s;
}

//--- S5: a bar of at least 1.5x ATR closing in the outer 20% of its
//--- range is a repricing, not noise. The shallow retracement that
//--- follows is the entry, invalidated at the impulse bar's origin.
//--- Same family as the well-known volatility-expansion scalpers.
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

   for(int i = 0; i < impulse; i++)
   {
      if(is_long  && r[i].close < origin) return s;
      if(!is_long && r[i].close > origin) return s;
   }

   const bool in_zone = is_long ? (r[0].low <= third) : (r[0].high >= third);
   if(!in_zone) return s;

   s.found            = true;
   s.id               = "S5";
   s.name             = "Momentum Continuation";
   s.is_long          = is_long;
   s.entry            = is_long ? SymbolInfoDouble(_Symbol, SYMBOL_ASK)
                                : SymbolInfoDouble(_Symbol, SYMBOL_BID);
   s.structural_level = origin;
   s.evidence = StringFormat(
      "impulse bar %.1f x ATR closing at %.0f%% of its range, retraced into "
      "its near third without breaking the origin at %.2f",
      range / atr_value, close_pos * 100.0, origin);
   s.failure_mode = "The impulse was a news spike. Those retrace fully and "
                    "continue through far more often than session-flow "
                    "impulses.";
   return s;
}

//--- S4: gold respects its 10 and 50 handles because that is where
//--- resting orders sit. First or second touch only -- after that the
//--- level is being accumulated against, not defended.
Setup DetectS4(const double atr_value)
{
   Setup s; ZeroMemory(s);

   MqlRates r[];
   ArraySetAsSeries(r, true);
   if(CopyRates(_Symbol, PERIOD_M5, 1, 13, r) < 13) return s;

   const double handle = MathRound(r[0].close / 10.0) * 10.0;
   if(MathAbs(r[0].close - handle) > atr_value * 1.5) return s;

   const double run = MathAbs(r[0].close - r[12].open);
   if(run < atr_value * 2.0) return s;
   const bool approaching_up = (r[0].close > r[12].open);

   const double range = r[0].high - r[0].low;
   if(range <= 0.0) return s;
   const double body  = MathAbs(r[0].close - r[0].open);
   const double upper = r[0].high - MathMax(r[0].open, r[0].close);
   const double lower = MathMin(r[0].open, r[0].close) - r[0].low;

   const bool rejected_down = (upper >= atr_value * 0.6 && upper > lower * 2.0
                               && body / range < 0.45 && r[0].high >= handle);
   const bool rejected_up   = (lower >= atr_value * 0.6 && lower > upper * 2.0
                               && body / range < 0.45 && r[0].low <= handle);

   if(approaching_up  && !rejected_down) return s;
   if(!approaching_up && !rejected_up)   return s;

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
   s.evidence = StringFormat(
      "%.1f x ATR run into the %.0f handle, rejection candle, touch %d of a "
      "maximum 2", run / atr_value, handle, touches);
   s.failure_mode = "The handle breaks and becomes support. After the second "
                    "test it is being accumulated against.";
   return s;
}

//--- News blackout. MQL5's economic calendar is unavailable in the
//--- Strategy Tester and varies by broker, so this is a deliberately
//--- crude time-based guard around the New York data windows.
//---
//--- It WILL miss a surprise release, a rescheduled print and every
//--- non-US event. A floor under the veto, not a substitute for
//--- looking at a calendar before the session.
bool InNewsBlackout(const datetime utc, string &reason)
{
   const datetime ny = utc + NewYorkOffsetHours(utc) * 3600;
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

//====================================================================
// SECTION 10 -- FROM SETUP TO ORDER
//====================================================================

void ExecuteOrAdvise(const Setup &s, const double atr_value,
                     const string session_label)
{
   //--- M2: the stop sits beyond the structural level, never on it. Gold
   //--- reaches through obvious levels to collect the stops resting there.
   double stop = s.is_long ? (s.structural_level - atr_value * STOP_BUFFER_ATR)
                           : (s.structural_level + atr_value * STOP_BUFFER_ATR);

   //--- M1: never tighter than MIN_STOP_ATR_MULTIPLE. A stop inside one ATR
   //--- is noise, not risk. Widening shrinks the position, which is correct:
   //--- fewer ounces at a survivable distance beats more at a distance that
   //--- gets hit by noise.
   const double floor_dist = atr_value * MIN_STOP_ATR_MULTIPLE;
   if(MathAbs(s.entry - stop) < floor_dist)
      stop = s.is_long ? (s.entry - floor_dist) : (s.entry + floor_dist);

   //--- The broker constraint that does not exist in a backtest.
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

   const double first_target = s.is_long
      ? s.entry + risk_per_unit * InpFirstTargetR
      : s.entry - risk_per_unit * InpFirstTargetR;
   const double runner_target = s.is_long
      ? s.entry + risk_per_unit * InpRunnerTargetR
      : s.entry - risk_per_unit * InpRunnerTargetR;

   //--- The blended reward/risk is the honest headline. A plan taking 60% at
   //--- 0.5R and 40% at 2.5R is 1.3R, not 2.5R.
   const double frac    = InpFirstTargetPct / 100.0;
   const double blended = frac * InpFirstTargetR
                        + (1.0 - frac) * InpRunnerTargetR;

   const double risk_money = AccountInfoDouble(ACCOUNT_BALANCE)
                           * RISK_PER_TRADE_PCT / 100.0;
   string size_problem;
   const double lots = LotsForRisk(_Symbol, risk_per_unit, risk_money,
                                   size_problem);
   if(lots <= 0.0)
   {
      Note("cannot size: " + size_problem);
      return;
   }

   const string plan = StringFormat(
      "%s %s  %s\n"
      "  Entry  %.2f\n"
      "  Stop   %.2f   (%.2f = 1R, %.2f x ATR)\n"
      "  T1     %.2f   -> close %.0f%%  (%.2fR)\n"
      "  T2     %.2f   -> runner, stop to break-even after T1  (%.1fR)\n"
      "  Size   %.2f lots  (%.2f %s at risk = %.1f%%)\n"
      "  Blended R:R 1:%.2f\n"
      "  Why:   %s\n"
      "  Fails: %s\n"
      "  Session: %s",
      s.id, s.name, (s.is_long ? "LONG" : "SHORT"),
      s.entry, stop, risk_per_unit, risk_per_unit / atr_value,
      first_target, InpFirstTargetPct, InpFirstTargetR,
      runner_target, InpRunnerTargetR,
      lots, risk_money, AccountInfoString(ACCOUNT_CURRENCY),
      RISK_PER_TRADE_PCT, blended, s.evidence, s.failure_mode, session_label);

   Print(plan);
   DrawSetup(s, stop, first_target, runner_target);

   if(InpAlerts && !MQLInfoInteger(MQL_TESTER))
      Alert(StringFormat("%s %s %s @ %.2f  SL %.2f  %.2f lots",
                         s.id, (s.is_long ? "LONG" : "SHORT"), _Symbol,
                         s.entry, stop, lots));

   if(InpMode == MODE_ADVISOR)
   {
      Print("ADVISOR MODE -- no order placed. Execute manually if you agree.");
      return;
   }

   //--- Place with the stop attached. Never send a naked order and add the
   //--- stop afterwards: the gap between the two is exactly when gold moves.
   const bool ok = s.is_long
      ? trade.Buy(lots, _Symbol, 0.0, stop, 0.0, s.id + " " + s.name)
      : trade.Sell(lots, _Symbol, 0.0, stop, 0.0, s.id + " " + s.name);

   if(!ok)
   {
      PrintFormat("order failed: %d %s", trade.ResultRetcode(),
                  trade.ResultRetcodeDescription());
      return;
   }

   //--- ResultOrder() is an order ticket and ResultDeal() a deal ticket --
   //--- neither is the position ticket that PositionModify and PositionClose
   //--- need. Resolve by symbol and magic, unambiguous with one position.
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
      Print("order filled but the position could not be resolved. It has a "
            "stop attached, but the EA cannot manage it -- check the Trade tab.");
      return;
   }

   managed.entry             = pos.PriceOpen();
   managed.initial_stop      = stop;
   managed.risk_per_unit     = risk_per_unit;
   managed.first_target      = first_target;
   managed.runner_target     = runner_target;
   managed.first_target_done = false;
   managed.initial_volume    = lots;
   managed.opened_at         = ServerToUtc(TimeTradeServer());
   managed.setup_id          = s.id;

   day.trades_taken++;
   PrintFormat("opened #%I64u, %d of %d trades today",
               managed.ticket, day.trades_taken, MAX_TRADES_PER_DAY);
}

//====================================================================
// SECTION 11 -- CHART OUTPUT
//====================================================================

void DrawLine(const string name, const double price, const color clr,
              const string text)
{
   ObjectCreate(0, name, OBJ_HLINE, 0, 0, price);
   ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, name, OBJPROP_STYLE, STYLE_DOT);
   ObjectSetInteger(0, name, OBJPROP_WIDTH, 1);
   ObjectSetString(0, name, OBJPROP_TEXT, text);
}

void DrawSetup(const Setup &s, const double stop, const double t1,
               const double t2)
{
   ObjectsDeleteAll(0, "GSA_setup_");
   DrawLine("GSA_setup_entry", s.entry, clrDodgerBlue, "entry");
   DrawLine("GSA_setup_stop",  stop,    clrCrimson,    "stop (1R)");
   DrawLine("GSA_setup_t1",    t1,      clrLimeGreen,  "T1");
   DrawLine("GSA_setup_t2",    t2,      clrSeaGreen,   "T2");
}

void DrawDashboard(const datetime utc)
{
   string session_label;
   const SessionQuality q = ClassifySession(utc, session_label);
   string stop_reason;
   const bool stopped = ShouldStopTrading(stop_reason);

   const string quality_text =
      (q == QUALITY_PRIME)    ? "PRIME"    :
      (q == QUALITY_GOOD)     ? "good"     :
      (q == QUALITY_MARGINAL) ? "marginal" : "AVOID";

   const string position_text = (managed.ticket == 0)
      ? "no position"
      : StringFormat("in %s, T1 %s", managed.setup_id,
                     (managed.first_target_done ? "taken" : "pending"));

   const string text = StringFormat(
      "GoldScalpAssistant  [%s]\n"
      "Session: %s (%s)\n"
      "Day: %+.2f%%   Trades: %d/%d   Losses in a row: %d\n"
      "%s\n"
      "%s",
      (InpMode == MODE_ADVISOR ? "ADVISOR" : "AUTO"),
      quality_text, session_label,
      DayPnLPercent(), day.trades_taken, MAX_TRADES_PER_DAY,
      day.consecutive_losses, position_text,
      (stopped ? "STOPPED: " + stop_reason : "running"));

   if(ObjectFind(0, "GSA_panel") < 0)
   {
      ObjectCreate(0, "GSA_panel", OBJ_LABEL, 0, 0, 0);
      ObjectSetInteger(0, "GSA_panel", OBJPROP_CORNER, CORNER_LEFT_UPPER);
      ObjectSetInteger(0, "GSA_panel", OBJPROP_XDISTANCE, 10);
      ObjectSetInteger(0, "GSA_panel", OBJPROP_YDISTANCE, 20);
      ObjectSetInteger(0, "GSA_panel", OBJPROP_FONTSIZE, 9);
      ObjectSetString(0, "GSA_panel", OBJPROP_FONT, "Consolas");
   }
   ObjectSetString(0, "GSA_panel", OBJPROP_TEXT, text);
   ObjectSetInteger(0, "GSA_panel", OBJPROP_COLOR,
                    stopped ? clrCrimson
                            : (q == QUALITY_PRIME ? clrLimeGreen : clrSilver));
}
//+------------------------------------------------------------------+
