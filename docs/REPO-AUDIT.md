# Repo-Audit: was weg musste, was falsch war, was bleibt

Durchgang vom 29.07.2026 über das gesamte Repository — 75 versionierte Dateien,
rund 19.500 Zeilen. Gesucht wurde nach drei Dingen: was unnötig ist, was den Bot
schlechter macht, und was schlicht nicht stimmt.

Ergebnis vorweg: Ein Befund war ernst und ist behoben. Zwei weitere hätten kleine
Konten belogen. Der Rest ist Aufräumen.

---

## A1 · Die Strategie umging die Risikoschicht — **schwerwiegend, behoben**

`metals/dayrange.py` handelte eine **feste Losgröße von 0,10** und rief
`metals/risk.size_position` nie auf. Die Regel R1 (maximal 1 % Risiko je Trade) galt
damit für den Chat-Assistenten und für die Handrechnung, aber nicht für die Strategie,
die tatsächlich automatisch handeln soll.

Das ist genau der Konstruktionsfehler, den die Forenbeiträge über gescheiterte Gold-EAs
beschreiben: 0,10 Lot ist eine vernünftige Größe auf 20.000 und eine
Alles-oder-nichts-Größe auf 400.

**Behoben.** `DayRangeConfig.risk_pct` leitet die Losgröße aus dem Stop-Abstand ab:

```python
pct = min(cfg.risk_pct, MAX_RISK_PER_TRADE_PCT)   # R1, und das ist ein Deckel
money = equity * pct / 100.0
lots = floor(money / (stop_distance_usd * oz_per_lot))
```

Drei Eigenschaften, die alle getestet sind:

- **Der Deckel greift nach unten, nie nach oben.** Wer `risk_pct=10.0` einträgt, bekommt
  1 %. Die Konfiguration kann nur vorsichtiger sein als die Regel, nie mutiger. Damit
  bleibt die Projektregel „Risikolimits gehören in den Code" intakt.
- **Es wird abgerundet, nie auf.**
- **Passt die kleinste Position nicht, gibt es 0,0 zurück und der Trade entfällt.**
  Nicht die Broker-Mindestgröße, keine Exception — null. Das Aufrunden auf 0,01 Lot ist
  die teuerste Zeile, die man hier schreiben kann: sie verwandelt „dieser Trade passt
  nicht" in „riskiere 7 % des Kontos".

Abgelehnte Signale werden gezählt (`skipped_too_small`), nicht stillschweigend verworfen.

**Nicht geändert:** `metals/microscalp.py` hat denselben Aufbau, behält ihn aber. Das
Modul ist die Messung deiner ursprünglichen Idee („sofort schließen, wenn im Plus") und
kein Verfahren, das laufen soll — die dort veröffentlichten Zahlen müssen vergleichbar
bleiben. Im Modulkopf steht das jetzt.

**Kein Befund:** `metals/backtest.py` rechnet bewusst in R statt in Währung und braucht
deshalb keine Positionsgröße. Das ist im Modulkopf begründet und richtig so.

---

## A2 · Der Bericht schmeichelte kleinen Konten — **behoben**

Ein 432-$-Konto unter der 1-%-Regel ergab:

```
Trades pro Markt            1
Trefferquote           100.0%
Erwartungswert         +1.000R
```

Das sieht hervorragend aus. Verschwiegen wurde, dass **202 von 203 Signalen abgelehnt
wurden**, weil das Konto zu klein war. Eine Trefferquote auf dem einen Trade, den man
sich leisten konnte, ist keine Trefferquote.

Der Bericht zeigt jetzt Signale, Ablehnungen und den genutzten Anteil **vor** der
Trefferquote — in dieser Reihenfolge, weil so niemand die schöne Zahl liest, ohne die
Bedingung dazu gesehen zu haben.

---

## A3 · Veralteter Startkurs im Simulator — **behoben**

`simulate.MarketParams.start_price` stand auf **4.500 $**, während Gold um 4.100 lief.

Für die meisten Kennzahlen ist das egal — R-Vielfache und Renditen sind skaleninvariant.
Es ist genau dort **nicht** egal, wo in Dollar gerechnet wird: Margin, Stop-out-Schwelle,
und ob eine Mindestposition auf ein kleines Konto passt. Also genau bei den Zahlen, um
die es bei 100/200/400 € geht. Auf 4.100 gesetzt, mit Begründung im Code.

Derselbe Fehler war zuvor schon einmal in der Margin-Meldung von `microscalp` aufgetreten
und dort behoben worden. Beim zweiten Mal im selben Repo ist es ein Muster: **jede
hartkodierte Preisannahme ist ein Ablaufdatum ohne Erinnerung.**

---

## A4 · Toter Code — drei Definitionen entfernt

| Was | Warum weg |
|---|---|
| `risk.RiskViolation` | Exception mit dem Docstring „Raised when a trade would break a hard limit" — die nie geworfen wird. Der Modulkopf sagt ausdrücklich das Gegenteil: „Nothing here raises on a rule breach". Eine Exception, die suggeriert, dass irgendwo geworfen wird, ist schlimmer als keine. |
| `journal.write_header` | Zweiter Schreiber desselben CSV-Schemas neben `append`, das den Header selbst anlegt. Zwei Stellen, die dasselbe Schema kennen, driften auseinander — und das Schema ist mit dem MQL5-EA geteilt. |
| `sources.registry.by_category` | Nie aufgerufen. |

## A5 · Totes Wissen — verdrahtet statt gelöscht

`seasonality.year_end_illiquidity` und `summer_doldrums` waren korrekt geschrieben,
dokumentiert — und wurden nirgends aufgerufen. `read()` gab sie nicht aus.

Das ist kein toter Code im selben Sinn: Es ist richtiges Wissen ohne Anschluss. Statt zu
löschen, jetzt in `SeasonalRead.liquidity_note` verdrahtet, getrennt vom Monatsscore, weil
es eine Aussage über **Markttiefe** ist und nicht über Richtung — es ändert, welchen
Setups man traut, nicht wohin man lehnt.

---

## A6 · Offen: VWAP wird versprochen, aber nicht gerechnet

`metals/setups.py` nennt bei G-Setups als Zielregel „the opposite prior-day extreme, **or
the day's VWAP**". `indicators.vwap_session` existiert, ist sauber geschrieben und
behandelt fehlendes Volumen korrekt — wird aber **von nichts aufgerufen**. Der Assistent
nennt also ein Ziel, das er nicht ausrechnen kann.

Nicht behoben, bewusst. Es zu verdrahten heißt, eine zweite Zielregel in die Auswertung
einzuziehen, und das ist eine Strategieänderung, die gemessen gehört und nicht nebenbei
mitläuft. Bis dahin steht es hier als offener Punkt, statt als stiller Widerspruch.

---

## A7 · Die Nachrichtensperre R4 galt für die Strategie nicht — **behoben**

Aufgefallen an Sitzung 6 des Papier-Laufs: Es war **FOMC-Tag**, die Fed hielt bei
3,50–3,75 %, und der Bot handelte durch, als wäre nichts.

Regel R4 („kein Einstieg innerhalb von 30 Minuten um eine hochwirksame Veröffentlichung")
steht in `metals/risk.py` und wird von `size_position` durchgesetzt. `metals/dayrange.py`
enthielt **null** Vorkommen von „news". Exakt dieselbe Fehlerklasse wie A1: Die Regel galt
für den Chat-Assistenten, nicht für den Code, der handelt.

**Behoben.** `DayRangeConfig.news_times_utc` nimmt die Veröffentlichungszeiten, und
`in_news_blackout` verweigert den Einstieg im Fenster — mit `NEWS_BLACKOUT_MINUTES` aus
`risk.py`, damit es eine Definition gibt und nicht zwei. Der Zeitplan wird bewusst **nicht**
dupliziert: für echte Historie kommen die Zeiten aus `metals.sources.calendar`, wo die
Live-Regel bereits liegt.

**Was die Messung dazu sagt: nichts, und das ist die ehrliche Antwort.** Auf dem Simulator
ändert die Sperre den Erwartungswert von +0,107 R auf +0,099 R (nur FOMC) bzw. +0,128 R
(FOMC und CPI) — das ist Rauschen. Es kann gar nicht anders sein: die Sprünge des Simulators
sind zufällig verteilt und hängen an keiner Uhrzeit. **Der Simulator kann diese Regel nicht
bewerten.**

Sie steht trotzdem drin, und der Grund ist kein Backtest, sondern das dokumentierte Verhalten
von Gold um CPI, NFP und FOMC: Spreads von 1–2 auf 15–20 Punkte, dazu Slippage (C8). Ein
Einstieg in diesem Fenster ist ein anderer Trade als der, den die Regeln kalkuliert haben.
Der Test prüft deshalb, dass die Sperre **eingehalten** wird — nicht, dass sie nützt.

---

## A8 · Zwei Engines, zwei Kostenmodelle — **behoben**

`metals/backtest.py` berechnet Einstiegskosten als **Spread × (1 + Slippage)** mit
Slippage-Anteil 0,5, also das Anderthalbfache des Spreads. `metals/dayrange.py` berechnete
**nur den Spread**.

Damit war jede Zahl aus der Tagesspanne-Strategie zu einem Drittel zu billig gerechnet —
gemessen mit Kosten, die die eigene Backtest-Engine des Projekts nicht akzeptiert hätte.

Das verstößt direkt gegen die Projektregel *„Backtest, Paper und Live nutzen identischen
Code"*. Und es ist die unangenehme Sorte Fehler: Es fällt nicht auf, weil beide Zahlen
plausibel aussehen. Sie hören nur auf, vergleichbar zu sein.

**Behoben.** `DayRangeConfig.slippage_fraction` mit derselben Voreinstellung und derselben
Formel; ein Test prüft beides gegen `BacktestConfig`, nicht gegen eine abgeschriebene Zahl.

**Wirkung, gemessen über 20 Märkte à 15.000 Bars:**

| Einstiegskosten | Erwartungswert | Median |
|---|---:|---:|
| nur Spread (alt) | +0,1576 R | +10,45 % |
| Spread × 1,5 (Backtest-Konvention) | +0,1474 R | +10,25 % |
| Spread × 2 | +0,1416 R | +9,67 % |

Also **−6,5 % vom Erwartungswert** — klein, aus demselben Grund wie bei C2: Bei einem Ziel
von rund 31 $ sind auch anderthalb Spreads Kleingeld. Die Korrektur war trotzdem nötig,
denn ihre Größe ist ein Ergebnis der Messung und war vorher nicht bekannt.

**Die Sitzungen 1–9 des Papier-Laufs sind mit `slippage_fraction=0.0` markiert**, weil sie
so gerechnet wurden. Nachträglich umzurechnen hätte die Kette verfälscht; sie zu markieren
macht den Bruch sichtbar.

---

## Was geprüft wurde und in Ordnung war

- **Keine Zugangsdaten im Repository.** Vor jedem Commit läuft eine Suche nach den
  Werten, die einmal in einem Screenshot sichtbar waren. `mt5/install-ea.sh` liest sie
  bewusst zur Laufzeit aus der Container-Umgebung; ein Test hält fest, dass die Datei
  selbst keine enthält.
- **`.gitignore` deckt das Richtige ab** — `.env`, Journaldaten mit Kontozahlen, Caches.
- **Keine Altlasten:** keine unbenutzten Abhängigkeiten (reine Standardbibliothek), keine
  eingecheckten Binärdateien, keine verwaisten Zweige im Arbeitsbaum.
- **Die Risikolimits stimmen über alle drei Sprachen überein.** Python, MQL5 und das
  JavaScript des Web-Rechners führen je eine Kopie; jede wird gegen ihre Quelle getestet.
- **`metals/evaluate.py` ist nicht tot.** Sah bei der ersten Suche danach aus — wird aber
  von `tests/test_scalping_and_backtest.py` und aus `docs/BACKTEST-ERGEBNISSE.md` heraus
  benutzt. Hier notiert, weil ein Audit, das die eigenen Fehlalarme verschweigt, seine
  Trefferquote schönt.

## Was ausdrücklich *nicht* gestrichen wurde

Der Simulator, die Fremdkapital-Simulation und `microscalp` sehen nach Ballast aus, sind
aber die drei Stellen, an denen dieses Projekt bisher tatsächlich etwas widerlegt hat:
einen Messfehler in der eigenen Strategie, ein Ertragsversprechen und eine
Kontogrößenbehauptung. Ein Repository, das nur noch das enthält, was funktioniert, kann
nicht mehr zeigen, warum das andere nicht funktioniert.
