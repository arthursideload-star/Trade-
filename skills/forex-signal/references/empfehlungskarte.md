# Empfehlungskarte — Format

Nach TRADING-WISSEN.md XXVI.3. So fasst du (Claude) die Ausgabe von `recommend.py` für den
Nutzer zusammen. Ziel: klar, begründet, ehrlich über Unsicherheit — damit der Nutzer lernt und
nicht blind folgt.

## Aufbau

```
EUR/USD   LONG ▲   Konfidenz 74 %
Stand: 2026-07-22 14:00 UTC (letzter 15m-Schluss, kein Live-Tick)
Regime: Aufwärtstrend (nur Long)
────────────────────────────────────────────
Einstieg:   1.0842
Stop:       1.0810   (unter dem nächsten Support)
Ziel:       1.0906   (nächster Widerstand darüber)
R:R:        2.0
Größe:      50.000 Einheiten (0,50 Lot), Risiko 100 USD (1 %)
────────────────────────────────────────────
Begründung:
4h und 1h im Aufwärtstrend, 15m-Hammer am Support 1.0810, RSI dreht aus 38,
MACD-Histogramm positiv. Der nächste Widerstand bei 1.0906 gibt ein R:R von 2,0.

Warnungen / offen:
• R2 (Tagesverlust): Wie steht dein Konto heute? Unter −3 % keine neuen Trades.
• R4 (News): In den nächsten 30 Min kein Hochimpakt-Termin (NFP/CPI/FOMC/EZB)? Bitte prüfen.
```

## Regeln für die Karte

1. **Immer die Richtung des Regimes respektieren.** Das Skript blockt Gegentrend über das
   REGIME-Gate; wenn es „wait" sagt, ist die Karte eine Abwarten-Karte — kein Herumdeuten.
2. **Stop und Ziel kommen aus der Struktur.** Nie einen festen Pip-Stop erfinden. Das R:R ist
   gemessen; liegt es unter 1:2, ist es laut R3 **kein Trade**.
3. **`need_input`-Regeln sind offene Punkte, keine bestandenen.** R2 und R4 stehen so lange auf
   `need_input`, bis du sie klärst (R4 selbst prüfen, R2 beim Nutzer erfragen). Erst wenn alle
   Regeln `ok` sind, ist die Karte handelbar.
4. **Konfidenz ist keine Gewinnwahrscheinlichkeit.** Sie ist die interne Score-Bewertung.
   So auch benennen — keine Ertragsversprechen (CLAUDE.md).
5. **Größe nur mit Kontogröße.** Ohne `--account` gibt es Richtung, Level und R:R, aber keine
   Stückzahl. Frag nach der (Demo-)Kontogröße, wenn eine Größe gewünscht ist.
6. **Kontowährung.** Zeigt die Karte einen Währungshinweis (z. B. USD-Konto, EUR/GBP-Paar), gib
   ihn weiter — die Stückzahl ist dann exakt in der Kurswährung, aber umzurechnen.

## Abwarten-Karte

```
EUR/USD   ABWARTEN —   Konfidenz 41 %
Regime: Seitwärts (beide, vorsichtig)
────────────────────────────────────────────
Kein klares Setup: Trendausrichtung uneinheitlich, kein Muster am Level.
Kein Trade — auf einen saubereren Aufbau warten.
```

Abwarten ist ein vollwertiges Ergebnis. Die meisten Stunden bieten kein gutes Setup; das
ehrlich zu sagen ist Teil der Disziplin.
