//+------------------------------------------------------------------+
//| Sessions.mqh - session windows in UTC, with daylight saving       |
//|                                                                  |
//| Mirrors metals/sessions.py. Two things here are easy to get wrong |
//| and both silently break every time-dependent setup:               |
//|                                                                  |
//| 1. Broker server time is NOT UTC. It is commonly GMT+2/+3 and it  |
//|    shifts with the broker's own daylight saving. Everything below |
//|    works in UTC and converts once, at the edge.                   |
//| 2. London and New York shift on different dates. Hard-coding the  |
//|    overlap to a UTC range puts every London-open setup an hour    |
//|    out for several weeks a year.                                  |
//+------------------------------------------------------------------+
#property copyright "Trade- project"
#property strict

// FRIDAY_FLAT_HOUR_UTC lives in Risk.mqh. Declaring the dependency rather than
// relying on the EA happening to include Risk.mqh first.
#ifndef FRIDAY_FLAT_HOUR_UTC
   #include <GoldScalp\Risk.mqh>
#endif

//+------------------------------------------------------------------+
//| Broker server offset from UTC, in seconds.                        |
//|                                                                  |
//| TimeGMT() is the terminal's own idea of UTC and TimeTradeServer() |
//| is the broker's. The difference is the offset. In the Strategy    |
//| Tester TimeGMT() tracks the modelled time, so this works there    |
//| too -- but the tester cannot know the broker's historical DST      |
//| changes, so treat tester session boundaries as approximate.        |
//+------------------------------------------------------------------+
int ServerOffsetSeconds()
{
   return (int)(TimeTradeServer() - TimeGMT());
}

datetime ServerToUtc(const datetime server_time)
{
   return server_time - ServerOffsetSeconds();
}

//+------------------------------------------------------------------+
//| Daylight saving, computed rather than looked up.                  |
//| EU: last Sunday in March 01:00 UTC -> last Sunday in October.     |
//| US: second Sunday in March 07:00 UTC -> first Sunday in November. |
//+------------------------------------------------------------------+
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
   datetime first = StructToTime(dt);
   MqlDateTime out;
   TimeToStruct(first, out);
   const int to_sunday = (7 - out.day_of_week) % 7;
   return first + (to_sunday + (n - 1) * 7) * 86400;
}

bool EuSummerTime(const datetime utc)
{
   MqlDateTime dt;
   TimeToStruct(utc, dt);
   const datetime start = LastSundayOfMonth(dt.year, 3)  + 3600;      // 01:00
   const datetime end   = LastSundayOfMonth(dt.year, 10) + 3600;
   return (utc >= start && utc < end);
}

bool UsDaylightTime(const datetime utc)
{
   MqlDateTime dt;
   TimeToStruct(utc, dt);
   const datetime start = NthSundayOfMonth(dt.year, 3, 2)  + 7 * 3600; // 07:00
   const datetime end   = NthSundayOfMonth(dt.year, 11, 1) + 6 * 3600; // 06:00
   return (utc >= start && utc < end);
}

int LondonOffsetHours(const datetime utc) { return EuSummerTime(utc) ? 1 : 0; }
int NewYorkOffsetHours(const datetime utc) { return UsDaylightTime(utc) ? -4 : -5; }

//+------------------------------------------------------------------+
//| Session classification                                            |
//+------------------------------------------------------------------+
enum SessionQuality
{
   QUALITY_PRIME,      // tightest spreads, cleanest structure
   QUALITY_GOOD,
   QUALITY_MARGINAL,   // tradable but noisy
   QUALITY_AVOID       // rollover, deep Asia, Friday late, closed
};

//--- Local wall-clock hour in a given city, from a UTC timestamp.
int LocalHour(const datetime utc, const int offset_hours)
{
   MqlDateTime dt;
   TimeToStruct(utc + offset_hours * 3600, dt);
   return dt.hour;
}

bool MarketOpen(const datetime utc)
{
   MqlDateTime dt;
   TimeToStruct(utc, dt);
   const int wd = dt.day_of_week;        // 0 = Sunday in MQL5
   if(wd == 6) return false;             // Saturday
   if(wd == 0) return dt.hour >= 22;     // Sunday evening open
   if(wd == 5 && dt.hour >= 21) return false;
   return true;
}

//+------------------------------------------------------------------+
//| The rollover window: 21:00-23:00 UTC. Spreads multiply and swap   |
//| is charged. Not a trading window under any circumstances.         |
//+------------------------------------------------------------------+
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

   const bool london_kz  = (ldn >= 7  && ldn < 10);
   const bool ny_kz      = (nyc >= 8  && nyc < 11);
   const bool overlap    = (ldn >= 13 && ldn < 17) && (nyc >= 8 && nyc < 12);

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
      label = "London killzone -- the session's directional move starts here";
      return QUALITY_PRIME;
   }

   // Friday afternoon: position squaring plus weekend gap risk on anything held.
   if(dt.day_of_week == 5 && dt.hour >= FRIDAY_FLAT_HOUR_UTC)
   {
      label = "Friday late session -- weekend gap risk, a stop does not cover a gap";
      return QUALITY_AVOID;
   }

   // Asian hours: thin for gold. Measured across 100 simulated markets as the
   // worst session by a wide margin; excluded rather than merely discounted.
   if(dt.hour < 7)
   {
      label = "Asian session -- thin for gold, breakouts fail more often";
      return QUALITY_MARGINAL;
   }

   label = "regular session hours";
   return QUALITY_GOOD;
}

bool IsTradableSession(const datetime utc, const bool prime_only, string &label)
{
   const SessionQuality q = ClassifySession(utc, label);
   if(q == QUALITY_AVOID)
      return false;
   if(prime_only && q != QUALITY_PRIME)
   {
      label = "not a prime window: " + label;
      return false;
   }
   if(q == QUALITY_MARGINAL)
   {
      label = "marginal session: " + label;
      return false;
   }
   return true;
}
//+------------------------------------------------------------------+
