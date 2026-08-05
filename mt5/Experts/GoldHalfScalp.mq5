//+------------------------------------------------------------------+
//|                                              GoldHalfScalp.mq5   |
//|                                                                  |
//|  The half-target scalp: many short trades, banked at half the    |
//|  projected move. Port of metals/halfscalp.py -- the two must     |
//|  stay in step, because every number published about this         |
//|  strategy describes the Python side.                             |
//|                                                                  |
//|  WHAT IT DOES                                                    |
//|  Watches M1. When a bar moves at least InpTriggerAtr ATRs and    |
//|  closes decisively in one direction, it projects how far the     |
//|  move would plausibly go -- the bar itself, continued -- and      |
//|  takes a position AGAINST that push (reversion). It closes at    |
//|  HALF the projection, keeps a stop at the full projection, and    |
//|  gives up after InpMaxHoldMinutes.                               |
//|                                                                  |
//|  READ THIS BEFORE YOU RUN IT                                     |
//|  The edge measured for this strategy comes from the simulator's  |
//|  round-number magnet. Switch that feature off in the generator   |
//|  and the edge disappears (+0.033 -> -0.013 R, band across zero). |
//|  The magnet is in the generator because somebody believed gold   |
//|  behaves that way, so measuring it back out proves nothing about |
//|  gold. See findings A34 and A35 in docs/REPO-AUDIT.md.           |
//|                                                                  |
//|  It also matters which version you run. The strategy exactly as  |
//|  first described -- following the push instead of fading it,     |
//|  target of one measured move -- lost on 85 of 85 simulated days. |
//|  The defaults below are NOT that version.                        |
//|                                                                  |
//|  This EA therefore refuses to run on a live account unless you   |
//|  deliberately switch that refusal off.                           |
//+------------------------------------------------------------------+
#property copyright "Trade- project"
#property link      "https://github.com/arthursideload-star/Trade-"
#property version   "1.00"
#property strict
#property description "Half-target scalp on M1. Demo accounts by default."

#include <Trade\Trade.mqh>

//====================================================================
// SECTION 1 -- RISK LIMITS
//
// These are constants, not inputs, and that is deliberate: the
// project rule is that risk limits live in code so that changing one
// requires a commit and shows up in a diff. An input can be nudged
// at 2am from the Properties dialog and leaves no trace.
//====================================================================

//--- Per trade. Note how much lower this is than the 1% the other EA
//--- uses: that one takes at most four trades a day, this one takes
//--- around a hundred. Same 1% at this frequency would put a fifth of
//--- the account through the market's teeth on an ordinary day.
//---
//--- Where 0.25 comes from: the measured worst day was -4.26 R and the
//--- worst peak-to-trough -10.8 R. At 0.25% per trade that is a 1.1%
//--- day and a 2.7% drawdown -- survivable without heroics.
const double RISK_PER_TRADE_PCT = 0.25;

//--- The day stops here, whatever the signals say.
const double DAILY_LOSS_LIMIT_PCT = 5.0;

//--- A ceiling, not a target. At the measured rate (~7 trades an hour
//--- inside tradable windows) a normal day lands near 100; 200 means
//--- something is wrong and the EA should stop rather than discover
//--- what.
const int MAX_TRADES_PER_DAY = 200;

//--- A stop is never tighter than this many ATRs. M1 noise on gold
//--- takes out anything closer, and a stop inside the noise turns a
//--- winning idea into a losing one.
const double MIN_STOP_ATR = 0.8;

//--- The half-target must clear the round-trip cost by this factor or
//--- the trade is refused. A trade that cannot pay its own spread does
//--- not have a small edge, it has a negative one.
const double MIN_EDGE_MULTIPLE = 1.5;

//--- Extra adverse fill beyond the spread, as a fraction of it. Same
//--- figure as BacktestConfig.slippage_fraction and HalfScalpConfig in
//--- Python, so the cost gate here refuses exactly what the measured
//--- version refused.
const double SLIPPAGE_FRACTION = 0.5;

//--- Friday: no new positions after this hour UTC. A stop does not
//--- cover a weekend gap. A #define rather than a const, to match the
//--- declaration in GoldScalpAssistant.mq5 -- the parity test compares
//--- the two literally, and two spellings of the same number would make
//--- it either fail or be weakened until it stopped catching drift.
#define FRIDAY_FLAT_HOUR_UTC    19     // M1: a stop does not cover a gap

//====================================================================
// SECTION 2 -- INPUTS
//====================================================================

enum ENUM_SIGNAL_MODE
{
   SIGNAL_REVERSION,   // fade the push  (measured positive)
   SIGNAL_MOMENTUM     // follow the push (measured negative in all 9 variants)
};

input group "=== Operation ==="
input long   InpMagic            = 20260805;  // Magic number
input bool   InpAllowLiveAccount  = false;     // Allow a LIVE account (danger)
input bool   InpDashboard        = true;      // On-chart panel

input group "=== The setup ==="
//--- 0.60 rather than 1.00. Measured out of sample on 30 markets that
//--- took no part in choosing it:
//---     trigger 0.6 -> +0.0284 R [+0.0172 .. +0.0397], a trade every 8.5 min
//---     trigger 1.0 -> +0.0412 R [+0.0293 .. +0.0531], a trade every 11.4 min
//--- The slower setting earns MORE per trade and slightly more per hour.
//--- 0.6 is the default because it is the one that meets the stated
//--- requirement of a trade at least every ten minutes. That requirement
//--- is not free, and this comment is where its price is written down.
input double InpTriggerAtr       = 0.60;      // Trigger bar size in ATRs
input double InpClosePositionMin = 0.70;      // How decisively it must close
input ENUM_SIGNAL_MODE InpSignal = SIGNAL_REVERSION;  // Direction of the trade

input group "=== Target and stop ==="
input double InpTargetMultiple   = 2.00;      // Projection = trigger bar x this
input double InpTakeFraction     = 0.50;      // Close at this share of it
input double InpStopFraction     = 1.00;      // Stop at this share of it

input group "=== Timing ==="
input int    InpMaxHoldMinutes   = 10;        // Give up after N minutes
input int    InpCooldownMinutes  = 1;         // Wait after a close
input bool   InpSessionFilter    = true;      // Open only in PRIME/GOOD windows

input group "=== Filters ==="
input int    InpAtrPeriod        = 14;        // ATR period (M1)

//====================================================================
// SECTION 3 -- STATE
//====================================================================

CTrade   trade;
int      hAtr = INVALID_HANDLE;
datetime lastBarTime = 0;
string   lastNote = "";
bool     journalBroken = false;

struct ManagedPosition
{
   ulong    ticket;
   ulong    position_id;
   double   entry;
   double   stop;
   double   take;
   double   risk_per_unit;
   double   risk_money;
   double   lots;
   datetime opened_at;      // UTC
   bool     is_long;
   string   session;
};
ManagedPosition managed;

struct DayState
{
   int      day_of_year;
   int      trades_taken;
   double   start_equity;
   bool     halted;
};
DayState day;

datetime cooldownUntil = 0;   // UTC

//====================================================================
// SECTION 4 -- TIME AND SESSIONS
//
// Identical arithmetic to GoldScalpAssistant.mq5. Duplicated rather
// than shared because the project ships ONE file per EA -- the setup
// guide tells the user to copy a single .mq5 into MQL5/Experts, and
// an #include would silently break that. tests/test_mt5_parity.py
// checks the two copies against each other so the duplication cannot
// drift.
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
   dt.year = year; dt.mon = month; dt.day = DaysInMonth(year, month);
   dt.hour = 0; dt.min = 0; dt.sec = 0;
   const datetime last_day = StructToTime(dt);
   MqlDateTime out;
   TimeToStruct(last_day, out);
   return last_day - out.day_of_week * 86400;
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
   const datetime start = LastSundayOfMonth(dt.year, 3)  + 3600;
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
   const int wd = dt.day_of_week;
   if(wd == 6) return false;
   if(wd == 0) return dt.hour >= 22;
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
   if(!MarketOpen(utc)) { label = "market closed"; return QUALITY_AVOID; }
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

   if(overlap)   { label = "London/New York overlap -- tightest spreads of the day"; return QUALITY_PRIME; }
   if(ny_kz)     { label = "New York killzone -- largest ranges, real participation"; return QUALITY_PRIME; }
   if(london_kz) { label = "London killzone -- the session's move usually starts here"; return QUALITY_PRIME; }

   if(dt.day_of_week == 5 && dt.hour >= FRIDAY_FLAT_HOUR_UTC)
   {
      label = "Friday late -- weekend gap risk, a stop does not cover a gap";
      return QUALITY_AVOID;
   }
   if(dt.hour < 7)
   {
      label = "Asian session -- thin for gold, breakouts fail more often";
      return QUALITY_MARGINAL;
   }
   label = "regular session hours";
   return QUALITY_GOOD;
}

string QualityLabel(const SessionQuality q)
{
   return (q == QUALITY_PRIME)    ? "PRIME"    :
          (q == QUALITY_GOOD)     ? "good"     :
          (q == QUALITY_MARGINAL) ? "marginal" : "AVOID";
}

string SessionWord(const datetime utc)
{
   string ignored;
   string word = QualityLabel(ClassifySession(utc, ignored));
   StringToLower(word);
   return word;
}

//====================================================================
// SECTION 5 -- THE JOURNAL
//
// Deliberately the SAME schema as GoldScalpAssistant.csv, so that
// `python -m metals journal` and `python -m metals vault` read this
// EA's output with no changes at all. Only the filename differs.
//====================================================================

#define JOURNAL_FILE "GoldHalfScalp.csv"

string JournalHeader()
{
   return "timestamp,kind,symbol,setup,direction,session,mode," +
          "entry,stop,target1,target2,atr,spread,risk_per_unit," +
          "lots,taken,skip_reason,exit_reason,r_multiple,pnl," +
          "minutes_held,confidence";
}

string IsoUtc(const datetime utc)
{
   return TimeToString(utc, TIME_DATE | TIME_SECONDS);
}

string CsvSafe(const string text)
{
   string out = text;
   StringReplace(out, ",", ";");
   StringReplace(out, "\n", " ");
   StringReplace(out, "\r", " ");
   return out;
}

string Num(const double value, const int digits = 2)
{
   if(value == EMPTY_VALUE) return "";
   return DoubleToString(value, digits);
}

void Note(const string text)
{
   if(text == lastNote) return;
   lastNote = text;
   Print(text);
}

void JournalAppend(const string line)
{
   if(journalBroken) return;
   const int handle = FileOpen(JOURNAL_FILE,
                               FILE_READ | FILE_WRITE | FILE_TXT | FILE_ANSI |
                               FILE_SHARE_READ);
   if(handle == INVALID_HANDLE)
   {
      journalBroken = true;
      PrintFormat("journal disabled: cannot open %s (error %d). Trading is "
                  "unaffected, but nothing will be recorded for review.",
                  JOURNAL_FILE, GetLastError());
      return;
   }
   FileSeek(handle, 0, SEEK_END);
   if(FileTell(handle) == 0)
      FileWriteString(handle, JournalHeader() + "\r\n");
   FileWriteString(handle, line + "\r\n");
   FileClose(handle);
}

//--- A signal, taken or refused. The refusals matter more than usual
//--- here: at a hundred trades a day, a gate that quietly blocks
//--- everything looks exactly like a quiet market.
void JournalSignal(const bool is_long, const string session,
                   const double entry, const double stop, const double take,
                   const double atr_value, const double spread,
                   const double risk_per_unit, const double lots,
                   const bool taken, const string skip_reason)
{
   JournalAppend(StringFormat(
      "%s,signal,%s,HS,%s,%s,auto,%s,%s,%s,,%s,%s,%s,%s,%s,%s,,,,,",
      IsoUtc(ServerToUtc(TimeTradeServer())), _Symbol,
      (is_long ? "long" : "short"), session,
      Num(entry, _Digits), Num(stop, _Digits), Num(take, _Digits),
      Num(atr_value, 3), Num(spread, _Digits), Num(risk_per_unit, 3),
      Num(lots), (taken ? "1" : "0"), CsvSafe(skip_reason)));
}

//--- A position closed. r_multiple is money made over money risked at
//--- entry, which is the only figure comparable across account sizes.
void JournalClose(const double profit, const double r_multiple,
                  const double minutes_held, const string exit_reason)
{
   JournalAppend(StringFormat(
      "%s,close,%s,HS,%s,%s,auto,%s,%s,%s,,,,%s,%s,,,%s,%s,%s,%s,",
      IsoUtc(ServerToUtc(TimeTradeServer())), _Symbol,
      (managed.is_long ? "long" : "short"), managed.session,
      Num(managed.entry, _Digits), Num(managed.stop, _Digits),
      Num(managed.take, _Digits),
      Num(managed.risk_per_unit, 3), Num(managed.lots),
      CsvSafe(exit_reason), Num(r_multiple, 3), Num(profit),
      Num(minutes_held, 0)));
}

//====================================================================
// SECTION 6 -- SIZING
//====================================================================

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

//--- Asks the terminal for the contract arithmetic rather than assuming
//--- 100 oz per lot. Always rounds DOWN: rounding up exceeds the risk
//--- limit, which is the one direction the error must never take.
double LotsForRisk(const double stop_distance, const double risk_money,
                   string &why)
{
   const double tick_value = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   const double tick_size  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   const double vol_min    = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   const double vol_max    = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   const double vol_step   = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);

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

   double lots = MathFloor((risk_money / loss_per_lot) / vol_step) * vol_step;
   lots = NormalizeDouble(lots, 2);

   if(lots < vol_min)
   {
      //--- Say what would be enough, not merely that this is not. The
      //--- number is exact and it is the only thing the reader can act on:
      //--- widening the risk is the one wrong answer, and a message that
      //--- stops at "too small" invites it.
      const double needed = loss_per_lot * vol_min * 100.0
                          / RISK_PER_TRADE_PCT;
      why = StringFormat(
         "position rounds to %.4f lots, below the broker minimum of %.2f. "
         "A %.2f stop at %.2f%% risk needs about %.0f in the account; this "
         "one has %.0f. That is an account-size constraint, not a signal "
         "problem -- do not solve it by widening risk, open a larger demo.",
         lots, vol_min, stop_distance, RISK_PER_TRADE_PCT, needed,
         AccountInfoDouble(ACCOUNT_EQUITY));
      return 0.0;
   }
   if(lots > vol_max) lots = vol_max;
   why = "";
   return lots;
}

//====================================================================
// SECTION 7 -- DAY STATE
//====================================================================

datetime StartOfDayUtc(const datetime utc)
{
   MqlDateTime dt;
   TimeToStruct(utc, dt);
   dt.hour = 0; dt.min = 0; dt.sec = 0;
   return StructToTime(dt);
}

//--- Rebuilt from the deal history, not merely zeroed.
//---
//--- The obvious version -- set the counters to zero and today's equity as
//--- the starting point -- has a hole big enough to drive through: restart
//--- the terminal after a 4% losing day and both limits begin again from
//--- nothing. A risk limit that a restart clears is not a limit, and
//--- restarts are routine on a VPS.
//---
//--- So today's own deals are counted back. The `start_equity > 0` in the
//--- guard matters too: MqlDateTime.day_of_year is zero-based, so on the
//--- first of January the zeroed struct would otherwise look like a day
//--- that had already been rebuilt.
void RebuildDayState(const datetime utc)
{
   MqlDateTime dt;
   TimeToStruct(utc, dt);
   if(day.day_of_year == dt.day_of_year && day.start_equity > 0.0) return;

   day.day_of_year  = dt.day_of_year;
   day.trades_taken = 0;
   day.halted       = false;

   const datetime from_server = StartOfDayUtc(utc) + ServerOffsetSeconds();
   if(!HistorySelect(from_server, TimeTradeServer() + 60))
   {
      day.start_equity = AccountInfoDouble(ACCOUNT_EQUITY);
      PrintFormat("new trading day, history unavailable. Equity %.2f, "
                  "limits: %.1f%% loss, %d trades.",
                  day.start_equity, DAILY_LOSS_LIMIT_PCT, MAX_TRADES_PER_DAY);
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
      realised += HistoryDealGetDouble(ticket, DEAL_PROFIT)
                + HistoryDealGetDouble(ticket, DEAL_SWAP)
                + HistoryDealGetDouble(ticket, DEAL_COMMISSION);
   }

   //--- Equity at the start of the day, derived backwards from what has
   //--- been realised since. Not exact if something else trades the same
   //--- account, which is one more reason to give this EA one to itself.
   day.start_equity = AccountInfoDouble(ACCOUNT_EQUITY) - realised;
   if(day.start_equity <= 0.0)
      day.start_equity = AccountInfoDouble(ACCOUNT_EQUITY);

   if(day.trades_taken > 0)
      PrintFormat("recovered day state: %d trade(s) already taken today, "
                  "realised %.2f. Limits continue from there, not from zero.",
                  day.trades_taken, realised);
   else
      PrintFormat("new trading day. Equity %.2f, limits: %.1f%% loss, "
                  "%d trades.", day.start_equity, DAILY_LOSS_LIMIT_PCT,
                  MAX_TRADES_PER_DAY);
}

//--- Returns true when the day is over, whatever the chart says.
bool DayIsOver()
{
   if(day.halted) return true;
   if(day.start_equity <= 0.0) return false;

   const double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   const double drop_pct = (day.start_equity - equity) / day.start_equity * 100.0;
   if(drop_pct >= DAILY_LOSS_LIMIT_PCT)
   {
      day.halted = true;
      PrintFormat("STOPPED for today: down %.2f%% (limit %.1f%%). This is not "
                  "negotiable and does not reset until tomorrow.",
                  drop_pct, DAILY_LOSS_LIMIT_PCT);
      return true;
   }
   if(day.trades_taken >= MAX_TRADES_PER_DAY)
   {
      day.halted = true;
      PrintFormat("STOPPED for today: %d trades, the ceiling. A normal day is "
                  "around a hundred, so hitting this means something is off.",
                  day.trades_taken);
      return true;
   }
   return false;
}

//====================================================================
// SECTION 8 -- THE SETUP
//
// Port of _entry_signal() and _projection() in metals/halfscalp.py.
// A bar of at least InpTriggerAtr ATRs closing in the outer
// (1 - InpClosePositionMin) of its own range is a push. Reversion
// trades against it; momentum trades with it.
//====================================================================

struct Setup
{
   bool   found;
   bool   is_long;
   double entry;
   double stop;
   double take;
   double projection;
   double atr;
};

Setup DetectHalfScalp(const double atr_value)
{
   Setup s;
   ZeroMemory(s);

   MqlRates r[];
   ArraySetAsSeries(r, true);
   if(CopyRates(_Symbol, PERIOD_M1, 1, 2, r) < 2) return s;

   const double range = r[0].high - r[0].low;
   if(range <= 0.0) return s;
   if(atr_value <= 0.0) return s;
   if(range < atr_value * InpTriggerAtr) return s;

   const double close_pos = (r[0].close - r[0].low) / range;

   bool pushed_up;
   if(close_pos >= InpClosePositionMin)            pushed_up = true;
   else if(close_pos <= 1.0 - InpClosePositionMin) pushed_up = false;
   else return s;

   //--- Reversion fades the push. Momentum follows it, and lost in all
   //--- nine measured configurations -- the input exists so that claim
   //--- stays checkable, not because it is an alternative.
   const bool is_long = (InpSignal == SIGNAL_REVERSION) ? !pushed_up : pushed_up;

   //--- A measured move: the bar just printed, continued by as much
   //--- again. Floored at one ATR so a narrow bar cannot project a
   //--- target smaller than the noise it sits in.
   const double projection = MathMax(range, atr_value) * InpTargetMultiple;

   const double take_distance = projection * InpTakeFraction;
   double stop_distance = MathMax(projection * InpStopFraction,
                                  atr_value * MIN_STOP_ATR);

   //--- The broker's own constraint, which does not exist in a backtest.
   const double min_dist = MinStopDistance(_Symbol);
   if(stop_distance < min_dist) stop_distance = min_dist;

   const double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   const double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);

   s.found      = true;
   s.is_long    = is_long;
   s.entry      = is_long ? ask : bid;
   s.projection = projection;
   s.atr        = atr_value;
   s.stop = is_long ? (s.entry - stop_distance) : (s.entry + stop_distance);
   s.take = is_long ? (s.entry + take_distance) : (s.entry - take_distance);
   s.stop = NormalizeDouble(s.stop, _Digits);
   s.take = NormalizeDouble(s.take, _Digits);
   return s;
}

//====================================================================
// SECTION 9 -- OPENING
//====================================================================

ulong FindOurPosition()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      const ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      return ticket;
   }
   return 0;
}

void TryToOpen(const datetime utc, const double atr_value)
{
   string label;
   const SessionQuality quality = ClassifySession(utc, label);
   const string session_word = SessionWord(utc);

   if(quality == QUALITY_AVOID)
   {
      Note("AVOID window (" + label + "). No new positions.");
      return;
   }
   if(InpSessionFilter && quality == QUALITY_MARGINAL)
   {
      Note("marginal window (" + label + "). The session filter is on: "
           "opening here was measured at -0.018 R per trade (A35).");
      return;
   }

   Setup s = DetectHalfScalp(atr_value);
   if(!s.found) return;

   const double spread = SymbolInfoDouble(_Symbol, SYMBOL_ASK)
                       - SymbolInfoDouble(_Symbol, SYMBOL_BID);
   const double risk_per_unit = MathAbs(s.entry - s.stop);
   const double take_distance = MathAbs(s.take - s.entry);

   //--- The gate that matters most at this horizon.
   //---
   //--- The round trip is ONE spread plus slippage, not two: a long buys
   //--- at the ask and sells at the bid, so the bid-ask difference is
   //--- paid once across the pair. metals/halfscalp.py charges
   //--- `spread * (1 + slippage_fraction)` with slippage_fraction 0.5,
   //--- and this has to be the same number or every figure published
   //--- about this strategy describes a different one.
   const double round_trip = spread * (1.0 + SLIPPAGE_FRACTION);
   if(take_distance < round_trip * MIN_EDGE_MULTIPLE)
   {
      Note(StringFormat(
         "refused: half-target %.2f does not clear %.1fx the %.2f round trip. "
         "At this spread the trade cannot pay for itself.",
         take_distance, MIN_EDGE_MULTIPLE, round_trip));
      JournalSignal(s.is_long, session_word, s.entry, s.stop, s.take,
                    atr_value, spread, risk_per_unit, EMPTY_VALUE, false,
                    "cost gate: half-target under the round trip");
      return;
   }

   const double risk_money = AccountInfoDouble(ACCOUNT_EQUITY)
                           * RISK_PER_TRADE_PCT / 100.0;
   string why;
   const double lots = LotsForRisk(risk_per_unit, risk_money, why);
   if(lots <= 0.0)
   {
      Note("cannot size: " + why);
      JournalSignal(s.is_long, session_word, s.entry, s.stop, s.take,
                    atr_value, spread, risk_per_unit, EMPTY_VALUE, false,
                    "position size below the broker minimum");
      return;
   }

   //--- Stop and target go on with the order. At this frequency,
   //--- managing exits from OnTick is a liability: one disconnected
   //--- minute and a position sits there with no protection. The broker
   //--- holds both sides from the moment of the fill.
   //--- The stop goes into the order comment as well as onto the order.
   //--- Not decoration: on MetaTrader's own VPS the EA's journal file stays
   //--- on the VPS and cannot be read from the PC, so the only record that
   //--- comes home is the broker's deal history -- and a deal export stores
   //--- what a trade MADE, never what it RISKED. Without the stop, every
   //--- trade arrives without an R multiple and drops straight out of the
   //--- analysis, which is denominated in R throughout.
   //--- metals/sources/mt5report.py reads this back. Some brokers truncate
   //--- or replace comments; then the column is simply empty, which is the
   //--- correct outcome rather than a guessed denominator.
   const string comment = StringFormat("HS sl=%s", Num(s.stop, _Digits));

   const bool ok = s.is_long
      ? trade.Buy(lots, _Symbol, 0.0, s.stop, s.take, comment)
      : trade.Sell(lots, _Symbol, 0.0, s.stop, s.take, comment);

   if(!ok)
   {
      PrintFormat("order failed: %d %s", trade.ResultRetcode(),
                  trade.ResultRetcodeDescription());
      JournalSignal(s.is_long, session_word, s.entry, s.stop, s.take,
                    atr_value, spread, risk_per_unit, lots, false,
                    StringFormat("order rejected: %d %s",
                                 trade.ResultRetcode(),
                                 trade.ResultRetcodeDescription()));
      return;
   }

   const ulong ticket = FindOurPosition();
   if(ticket == 0)
   {
      Print("order reported success but no position found. Not tracking it.");
      return;
   }

   managed.ticket        = ticket;
   managed.position_id   = (ulong)PositionGetInteger(POSITION_IDENTIFIER);
   managed.entry         = PositionGetDouble(POSITION_PRICE_OPEN);
   managed.stop          = s.stop;
   managed.take          = s.take;
   managed.risk_per_unit = MathAbs(managed.entry - s.stop);
   managed.risk_money    = risk_money;
   managed.lots          = lots;
   managed.opened_at     = utc;
   managed.is_long       = s.is_long;
   managed.session       = session_word;

   day.trades_taken++;
   JournalSignal(s.is_long, session_word, managed.entry, s.stop, s.take,
                 atr_value, spread, managed.risk_per_unit, lots, true, "");
   PrintFormat("opened #%I64u %s %.2f lots, stop %.2f take %.2f "
               "(trade %d today)",
               ticket, (s.is_long ? "long" : "short"), lots, s.stop, s.take,
               day.trades_taken);
}

//====================================================================
// SECTION 10 -- MANAGING AND CLOSING
//====================================================================

//--- The only exit this EA manages itself. Stop and target are with the
//--- broker; the clock is not.
void EnforceTimeStop(const datetime utc)
{
   if(managed.ticket == 0) return;
   if(!PositionSelectByTicket(managed.ticket)) return;

   const int held = (int)((utc - managed.opened_at) / 60);
   if(held < InpMaxHoldMinutes) return;

   if(trade.PositionClose(managed.ticket))
      PrintFormat("time stop: closed #%I64u after %d minutes",
                  managed.ticket, held);
   else
      PrintFormat("time stop: could not close #%I64u (%d %s)",
                  managed.ticket, trade.ResultRetcode(),
                  trade.ResultRetcodeDescription());
}

//--- Detect that our position is gone, work out what it made, record it.
void ReapClosedPosition(const datetime utc)
{
   if(managed.ticket == 0) return;
   if(PositionSelectByTicket(managed.ticket)) return;   // still open

   double profit = 0.0;
   string reason = "unknown";

   if(HistorySelectByPosition(managed.position_id))
   {
      const int deals = HistoryDealsTotal();
      for(int i = 0; i < deals; i++)
      {
         const ulong deal = HistoryDealGetTicket(i);
         if(deal == 0) continue;
         if(HistoryDealGetInteger(deal, DEAL_ENTRY) != DEAL_ENTRY_OUT) continue;
         profit += HistoryDealGetDouble(deal, DEAL_PROFIT)
                 + HistoryDealGetDouble(deal, DEAL_SWAP)
                 + HistoryDealGetDouble(deal, DEAL_COMMISSION);
         const long dr = HistoryDealGetInteger(deal, DEAL_REASON);
         reason = (dr == DEAL_REASON_TP) ? "half_target"
                : (dr == DEAL_REASON_SL) ? "stop"
                : "time_stop";
      }
   }

   //--- R is money over money risked at entry. Recomputing the risk now
   //--- would be wrong: the position is gone and its original stop is no
   //--- longer readable from anywhere.
   const double r_multiple = (managed.risk_money > 0.0)
                           ? profit / managed.risk_money : 0.0;
   const double minutes = (double)((utc - managed.opened_at) / 60);

   JournalClose(profit, r_multiple, minutes, reason);
   PrintFormat("closed #%I64u: %s, %.2f (%.2f R) after %.0f min",
               managed.ticket, reason, profit, r_multiple, minutes);

   ZeroMemory(managed);
   cooldownUntil = utc + InpCooldownMinutes * 60;
}

//--- A position from before a restart. Adopted rather than ignored: an
//--- untracked position with our magic on it would never get its time
//--- stop and would never reach the journal.
void AdoptExistingPosition(const datetime utc)
{
   const ulong ticket = FindOurPosition();
   if(ticket == 0) return;

   managed.ticket      = ticket;
   managed.position_id = (ulong)PositionGetInteger(POSITION_IDENTIFIER);
   managed.entry       = PositionGetDouble(POSITION_PRICE_OPEN);
   managed.stop        = PositionGetDouble(POSITION_SL);
   managed.take        = PositionGetDouble(POSITION_TP);
   managed.lots        = PositionGetDouble(POSITION_VOLUME);
   managed.opened_at   = ServerToUtc((datetime)PositionGetInteger(POSITION_TIME));
   managed.is_long     = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY);
   managed.session     = SessionWord(managed.opened_at);
   managed.risk_per_unit = MathAbs(managed.entry - managed.stop);

   if(managed.stop <= 0.0)
   {
      Print("adopted a position with NO stop loss. Closing it: a position "
            "without a defined invalidation is not a trade, it is an open "
            "bill.");
      trade.PositionClose(ticket);
      ZeroMemory(managed);
      return;
   }

   //--- The risk in money cannot be recovered after the fact, so it is
   //--- reconstructed from the stop distance and today's equity. The
   //--- journal row will say so via an empty confidence and an R that
   //--- rests on this reconstruction.
   const double tick_value = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   const double tick_size  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tick_value > 0.0 && tick_size > 0.0)
      managed.risk_money = (managed.risk_per_unit / tick_size) * tick_value
                         * managed.lots;

   PrintFormat("adopted position #%I64u opened at %.2f, stop %.2f",
               ticket, managed.entry, managed.stop);
}

//====================================================================
// SECTION 11 -- PANEL
//====================================================================

void DrawDashboard(const datetime utc)
{
   string label;
   const SessionQuality quality = ClassifySession(utc, label);
   const string name = "HS_PANEL";

   const string text = StringFormat(
      "GoldHalfScalp  %s  |  Session: %s  |  Trades heute: %d/%d  |  %s",
      (day.halted ? "GESTOPPT" : "aktiv"),
      QualityLabel(quality), day.trades_taken, MAX_TRADES_PER_DAY,
      (managed.ticket > 0 ? "Position offen" : "flach"));

   if(ObjectFind(0, name) < 0)
   {
      ObjectCreate(0, name, OBJ_LABEL, 0, 0, 0);
      ObjectSetInteger(0, name, OBJPROP_CORNER, CORNER_LEFT_UPPER);
      ObjectSetInteger(0, name, OBJPROP_XDISTANCE, 10);
      ObjectSetInteger(0, name, OBJPROP_YDISTANCE, 20);
      ObjectSetInteger(0, name, OBJPROP_FONTSIZE, 9);
      ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
   }
   ObjectSetString(0, name, OBJPROP_TEXT, text);
   ObjectSetInteger(0, name, OBJPROP_COLOR,
                    day.halted ? clrOrangeRed : clrGainsboro);
}

//====================================================================
// SECTION 12 -- LIFECYCLE
//====================================================================

int OnInit()
{
   trade.SetExpertMagicNumber(InpMagic);
   trade.SetMarginMode();
   trade.SetTypeFillingBySymbol(_Symbol);
   trade.SetDeviationInPoints(20);

   //--- Same refusal as the other EA, and for the same reason: on a
   //--- non-gold symbol every number here is nonsense computed without
   //--- error, and this EA places orders.
   if(StringFind(_Symbol, "XAU") < 0 && StringFind(_Symbol, "GOLD") < 0)
   {
      PrintFormat("REFUSED: this EA is built for gold and the chart symbol is "
                  "%s. Put it on a chart whose symbol contains XAU or GOLD.",
                  _Symbol);
      Alert("GoldHalfScalp: falsches Symbol (", _Symbol,
            "). Bitte auf einen XAUUSD-Chart ziehen.");
      return INIT_PARAMETERS_INCORRECT;
   }

   //--- The guard that matters most. What is known about this strategy
   //--- is that its measured edge came from a feature of the market
   //--- SIMULATOR. That is not a basis for real money, and a default
   //--- that permitted it would be this project's worst line of code.
   if(!InpAllowLiveAccount &&
      AccountInfoInteger(ACCOUNT_TRADE_MODE) != ACCOUNT_TRADE_MODE_DEMO)
   {
      Print("REFUSED: this is not a demo account. The edge measured for this "
            "strategy comes from the simulator's round-number magnet and "
            "vanishes when that feature is switched off (A34). Nothing here "
            "has been shown to work on real gold. Run it on a demo, collect "
            "a few hundred trades, and let `python -m metals journal` say "
            "whether it earns anything before you consider more.");
      Alert("GoldHalfScalp: kein Demokonto. Der EA verweigert den Start.");
      return INIT_PARAMETERS_INCORRECT;
   }

   if(_Period != PERIOD_M1)
      Print("NOTE: the chart is not M1. Everything is computed on M1 "
            "regardless -- the chart timeframe only changes what you see.");

   hAtr = iATR(_Symbol, PERIOD_M1, InpAtrPeriod);
   if(hAtr == INVALID_HANDLE)
   {
      Print("failed to create the ATR handle");
      return INIT_FAILED;
   }

   const datetime utc = ServerToUtc(TimeTradeServer());
   ZeroMemory(day);
   RebuildDayState(utc);
   ZeroMemory(managed);
   AdoptExistingPosition(utc);

   PrintFormat("GoldHalfScalp ready. %s, risk %.2f%% per trade, target = "
               "%.1fx the trigger bar, banked at %.0f%%, stop at %.0f%%, "
               "give up after %d min.",
               (InpSignal == SIGNAL_REVERSION ? "reversion" : "momentum"),
               RISK_PER_TRADE_PCT, InpTargetMultiple,
               InpTakeFraction * 100.0, InpStopFraction * 100.0,
               InpMaxHoldMinutes);
   PrintFormat("journal: %s in MQL5/Files (File -> Open Data Folder). "
               "Read it with: python -m metals journal --file %s",
               JOURNAL_FILE, JOURNAL_FILE);
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   if(hAtr != INVALID_HANDLE) IndicatorRelease(hAtr);
   ObjectDelete(0, "HS_PANEL");
}

void OnTick()
{
   const datetime utc = ServerToUtc(TimeTradeServer());
   RebuildDayState(utc);

   //--- These two run on every tick, not on every bar. A time stop that
   //--- only fires on a new bar is not a ten-minute time stop, and a
   //--- close that is only noticed a minute later delays the cooldown
   //--- and the journal row with it.
   ReapClosedPosition(utc);
   EnforceTimeStop(utc);

   if(InpDashboard) DrawDashboard(utc);

   //--- Everything below is once per closed M1 bar. The setup is a
   //--- property of a finished bar, so re-testing it tick by tick would
   //--- only mean entering on whichever tick happened to arrive first.
   const datetime bar_time = iTime(_Symbol, PERIOD_M1, 0);
   if(bar_time == lastBarTime) return;
   lastBarTime = bar_time;

   if(managed.ticket > 0) return;          // one position at a time
   if(utc < cooldownUntil) return;
   if(DayIsOver()) return;

   double atr_buf[];
   if(CopyBuffer(hAtr, 0, 1, 1, atr_buf) < 1) return;
   const double atr_value = atr_buf[0];
   if(atr_value <= 0.0) return;

   TryToOpen(utc, atr_value);
}
//+------------------------------------------------------------------+
