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

## A6 · VWAP wurde versprochen, aber nicht gerechnet — **behoben**

`metals/setups.py` nennt bei mehreren G-Setups als Zielregel „the opposite prior-day
extreme, **or the day's VWAP**". `indicators.vwap_session` existierte, sauber geschrieben
und mit korrekter Behandlung fehlenden Volumens — wurde aber **von nichts aufgerufen**.
Der Assistent nannte also ein Ziel, das er nicht ausrechnen konnte.

Bei der Nachprüfung stellte sich der Befund als kleiner heraus als zunächst angenommen:
`target_rule` wird **nirgends** in eine Zahl umgesetzt, sondern nur ausgedruckt. Es war
also kein Rechenfehler, sondern eine Beschreibung ohne Deckung.

**Behoben.** `Context.vwap` wird jetzt berechnet und steht auf der Empfehlungskarte, samt
Angabe, ob der Kurs darüber oder darunter liegt. Drei Eigenschaften sind getestet:

- **Rücksetzung am Broker-Rollover (21:00 UTC), nicht um Mitternacht.** Sonst mittelt er
  über zwei Handelstage — eine andere Zahl unter demselben Namen. (Meine erste Fassung
  hatte hier einen Fehler: beide Zweige der Bedingung lieferten dasselbe Datum, die
  Rollover-Stunde wurde ignoriert.)
- **Ohne Volumen gibt es `None`, keinen ungewichteten Mittelwert.** Ein ungewichtetes
  Mittel sähe aus wie ein VWAP und wäre etwas anderes.
- Der Wert liegt innerhalb von Hoch und Tief der Serie.

**Was bewusst nicht passiert ist:** VWAP wird *nicht* als Ausstiegsregel in die Strategie
eingebaut. Das wäre eine Strategieänderung und gehört gemessen, nicht nebenbei verdrahtet.

---

---

## A12 · Der EA-Ausstieg kostet nicht 20 %, sondern 89 % — und der Zeitstop ist schuld

A11 konnte den Unterschied nur **schätzen**, indem zwei Zeilen einer Ziel-Tabelle gemischt
wurden: „grob +0,088 R gegen +0,110 R, rund 20 % weniger". Die EA-Struktur ist jetzt im
Python-Motor nachgebaut (`DayRangeConfig.ea_exit`) und damit **gemessen**, 20 Märkte à
15.000 Bars:

| | Trades | Treffer | Erwartung | Median |
|---|---:|---:|---:|---:|
| Python-Ausstieg, Zeitstop 240 (Basis) | 54 | 57,8 % | **+0,1281 R** | +11,63 % |
| Python-Ausstieg, Zeitstop **45** | 152 | 48,6 % | +0,0237 R | +4,97 % |
| EA-Ausstieg, Zeitstop 240 | 63 | 66,9 % | +0,0755 R | +7,05 % |
| **EA-Ausstieg, Zeitstop 45 (der echte EA)** | 153 | 50,4 % | **+0,0145 R** | +3,42 % |

**−89 %, nicht −20 %.** Und die Aufteilung dreht die Schuldfrage um:

- der **Zeitstop allein** kostet 81 % (+0,128 → +0,024 R)
- die **geteilte Ausstiegsstruktur allein** kostet 41 % (+0,128 → +0,076 R)

A11 hatte den Zeitstop in seiner Tabelle stehen, aber **nicht in die Schätzung
eingerechnet**. Der Hauptschaden kommt von dort, und der Grund ist inhaltlich einleuchtend:
Die Tagesspanne-Strategie zielt auf das **andere Ende der Tagesspanne**. Das dauert Stunden.
Ein Schnitt nach 45 Minuten schließt die meisten dieser Trades, bevor ihre eigene These
überhaupt entschieden ist.

**Behoben, und zwar hart.** `InpTimeStopMinutes` ist ein globaler Input — 45 Minuten sind
für die Scalping-Setups richtig und für DR falsch. Der EA **verweigert jetzt den Start**
(`INIT_PARAMETERS_INCORRECT`), wenn `InpUseDayRange = true` mit weniger als
`DR_MIN_TIME_STOP_MINUTES` (240) kombiniert wird:

```
REFUSED: InpUseDayRange needs InpTimeStopMinutes >= 240 (currently 45).
```

Verweigert statt gewarnt, weil der Fehler unsichtbar ist: Der EA handelt einfach weiter und
verdient weniger. Eine Warnung im Log hätte niemand gelesen.

**Was offen bleibt:** Ob die Datei kompiliert, konnte hier weiterhin niemand prüfen. Der
Wächter ist als Quelltextprüfung getestet, nicht als Programmlauf.


---

## A13 · Auf einem kleinen Konto gibt es den Teilschluss gar nicht — **modelliert, und eine Empfehlung zurückgezogen**

Beim Nachbau des EA-Ausstiegs (A12) fiel auf, dass mein Python-Modell einen Fall falsch
behandelte, der auf **deinem** Konto der Normalfall ist.

60 % von 0,01 Lot sind 0,006 — unter dem Broker-Minimum. Der Rest wäre es auch. Der EA hat
dafür eine Rückfalllinie, und sie ist nicht „lass laufen":

```
first target reached but a partial is not possible: 0.00/0.01 lots
against a 0.01 minimum. Closing in full.
```

**Er schließt komplett bei 0,5 R.** Auf einem Mindestlot-Konto existiert der Runner also
nie, und jeder Trade ist bei 0,5 R gedeckelt. Mein Modell ließ die Position stattdessen
weiterlaufen — das war eine andere Strategie als die, die der EA handelt. Korrigiert.

### Und dann das Ergebnis, das eine Empfehlung verhindert hat

| Ausstieg | Trades | Treffer | Erwartung | 95 %-Band |
|---|---:|---:|---:|---|
| EA 60/40-Teilung (0,10 Lot) | 1.245 | 65,1 % | +0,0599 R | +0,031 … +0,089 |
| EA voll bei 0,5 R (0,01 Lot) | 1.254 | 65,2 % | +0,0929 R | +0,063 … +0,123 |
| ein Ziel bei 1,0 R (0,01 Lot) | 1.058 | 54,5 % | +0,0926 R | +0,051 … +0,135 |

Der Reihenfolge nach sieht es aus, als wäre die 60/40-Teilung die schlechteste Variante.
**Die Bänder überlappen aber immer noch** (+0,063 gegen +0,089). Bei rund 1.200 Trades je
Variante ist der Unterschied nicht belegt.

Ich hatte an dieser Stelle schon „der Runner verliert Geld" formuliert. Das gibt die Messung
nicht her, und die Zeile ist wieder raus. Als Test steht jetzt fest, dass die Bänder
überlappen — sollten sie sich je trennen, muss der Test umgeschrieben werden, und dann
*ist* es ein Befund.

**Eine Zahl in dieser Tabelle war schon einmal falsch.** In der ersten Fassung stand für
„voll bei 0,5 R" **+0,0690 R**. Ursache war ein Fehler in meinem Modell: Der ATR-Trail lief
auch auf der Position weiter, die der EA bereits komplett schließt. Dadurch stieg das Modell
gelegentlich zu einem *besseren* nachgezogenen Stop aus als beim ersten Ziel — ein Pfad, den
der EA gar nicht geht. Behoben; das höchste R liegt jetzt exakt bei +0,500, wie es der
Deckel verlangt. Der korrigierte Wert ist **+0,0929 R**.

Nebenbei ein Befund, der stehen bleibt: Voll bei 0,5 R erreicht denselben Erwartungswert wie
ein Ziel bei 1,0 R, aber mit **65,2 % statt 54,5 % Trefferquote und einem engeren Band**.
Gleicher Ertrag bei weniger Streuung — das ist kein großer, aber ein echter Unterschied.

**Warum der Zeitstop-Wächter aus A12 trotzdem bleibt:** Dessen Effekt war mit +0,128 → +0,024 R
mehrfach so groß und auf derselben Stichprobenbasis gemessen. Große Effekte überstehen
Unsicherheitsbänder, kleine nicht — und das ist genau die Grenze, an der eine Messung aufhört,
eine Empfehlung zu sein.


---

## A14 · Der eine Regler, der auf deinem Konto zählt — und warum er bleibt, wo er ist

Aus A13 folgt: Auf einem Mindestlot-Konto schließt der EA **jeden** Trade komplett beim
ersten Ziel. Damit ist `InpFirstTargetR` nicht einer von mehreren Reglern, sondern der
einzige, der das Ergebnis bestimmt. Der Kommentar im Code sagt „measured: 0.5 beats 1.0" —
gemessen wurde das aber für die Scalping-Setups, nicht für die Tagesspanne-Strategie.

Also nachgemessen, 20 Märkte à 15.000 Bars:

| erstes Ziel | Trades | Treffer | Erwartung | 95 %-Band |
|---:|---:|---:|---:|---|
| 0,25 R | 1.803 | 80,0 % | +0,0830 R | +0,066 … +0,100 |
| 0,40 R | 1.354 | 71,4 % | +0,1003 R | +0,075 … +0,126 |
| **0,50 R (Standard)** | 1.225 | 67,7 % | +0,1044 R | +0,074 … +0,135 |
| 0,75 R | 1.085 | 61,9 % | +0,1187 R | +0,081 … +0,157 |

**Ergebnis: kein Grund, etwas zu ändern.** 0,75 R sieht am besten aus, aber sein Band
(+0,081 … +0,157) überlappt das von 0,25 R (+0,066 … +0,100). Über die ganze sinnvolle
Spannbreite ist der Erwartungswert innerhalb der Unsicherheit gleich.

Sauber ist nur die Trefferquote: 80 % → 62 %, monoton fallend mit dem Zielabstand. Genau
das muss sein, und es ist die Plausibilitätsprüfung für die ganze Reihe.

### Zwei Zeilen, die ich weggelassen habe — und warum das wichtig ist

Der erste Durchlauf enthielt auch 1,00 R und 1,50 R. Beide sind **wertlos**, und zwar
unbemerkt: Die Strategie hat ein eigenes Ziel bei 50 % der Vorhersage, also bei 1,0 R. Ein
„erstes Ziel" bei 1,5 R wird nie erreicht, bevor das eigene Ziel feuert — die Zeile
misst schlicht die Basisvariante unter falschem Namen. Nachweis: `unsplittable_closes = 0`
und identische Endstände.

Eine Parametersuche, die stillschweigend Zeilen enthält, die nichts messen, liest sich wie
sechs vergleichbare Ergebnisse und ist es nicht. Ein Test prüft jetzt, dass ein Ziel
unterhalb von 1,0 R tatsächlich greift und eines darüber als entartet erkannt wird.


---

## A15 · Regel M5 galt für die Strategie nicht — **behoben, zum dritten Mal derselbe Fehler**

`metals/dayrange.py` enthielt **kein einziges Vorkommen** von „weekend" oder „Friday". Regel
M5 („flach bis Freitag 19:00 UTC, Stops schützen nicht gegen Wochenendlücken") steht in
`metals/risk.py`, wird von `size_position` durchgesetzt — und der Code, der tatsächlich
handelt, kannte sie nicht.

**Das ist jetzt zum dritten Mal derselbe Fehlertyp:**

| | Regel | Wo sie stand | Wo sie fehlte |
|---|---|---|---|
| A1 | R1, 1 % Risiko je Trade | `risk.py` | `dayrange.py` |
| A7 | R4, Nachrichtensperre | `risk.py` | `dayrange.py` |
| **A15** | **M5, flach vor dem Wochenende** | `risk.py` | `dayrange.py` |

Dreimal dasselbe Muster ist kein Zufall mehr, sondern ein Konstruktionsproblem: Die
Risikoschicht war als Bibliothek gebaut, die *aufgerufen werden muss*, und die
Strategie-Engine rief sie nie auf. Jede Regel musste einzeln nachgetragen werden, und
gefunden wurden sie einzeln — durch Nachlesen, nicht durch eine Prüfung.

**Behoben.** `DayRangeConfig.weekend_flat` ist **standardmäßig an**, weil M5 eine harte
Metallregel ist und keine Vorliebe. Ab Freitag 19:00 UTC werden offene Positionen geschlossen
(Ausstiegsgrund `weekend_flat`) und keine neuen mehr eröffnet.

### Was die Messung sagt: nichts — und das ist wieder die ehrliche Antwort

+0,1051 R mit Regel gegen +0,1071 R ohne. Die Bänder sind praktisch deckungsgleich, 30
M5-Schlüsse über 20 Märkte.

Der Simulator **kann** die Regel nicht bewerten: Er überspringt geschlossene Stunden, eine
über das Wochenende gehaltene Position setzt am nächsten Bar einfach fort. Es gibt dort
keine Lücke. Genau wie bei A7 prüft der Test deshalb, dass die Regel **eingehalten** wird,
nicht dass sie nützt.

### Wofür die Regel dann da ist — die Zahl, die der Simulator nicht liefert

Dokumentierte Wochenendlücken bei Gold liegen bei größeren Ereignissen zwischen **30 und
50 $ je Unze**, im Extremfall um 80 $. Ein Stop schützt dagegen nicht — er wird zu dem Kurs,
den man *nach* der Lücke bekommt. Auf dem aktuellen Kontostand (rund 1.930 $) und dem
typischen Stop dieser Strategie von 30,77 $:

| Lücke | Verlust statt Stop | Anteil am Konto | = Vielfaches des Stops |
|---:|---:|---:|---:|
| 10 $ | 40,77 $ | 2,1 % | 1,3× |
| 30 $ | 60,77 $ | 3,1 % | 2,0× |
| 50 $ | 80,77 $ | 4,2 % | 2,6× |
| 80 $ | 110,77 $ | 5,7 % | 3,6× |

Bei 0,01 Lot ist das verkraftbar. Der Punkt ist nicht die Höhe, sondern dass **das Risiko
nicht mehr das ist, das die Regeln kalkuliert haben** — und genau das soll R1 verhindern.


---

## A16 · Die Prüfung, die das Nachlesen ersetzt — und R2, die sie sofort fand

A15 endete mit der Feststellung, dass dreimal derselbe Fehler auftrat und jedes Mal durch
Nachlesen gefunden wurde. Das ist kein Verfahren. Also eine Registratur:

`dayrange.RULE_COVERAGE` führt **jede** Regel aus `metals.risk.RULES` mit einem Status —
`implemented` oder `n/a` **mit Begründung**. Ein Test schlägt fehl, sobald eine Regel dort
keinen Eintrag hat. Eine Regel, die neu in die Risikoschicht kommt, kann damit nicht mehr
still an der handelnden Engine vorbeigehen.

Die Registratur fand beim ersten Lauf sofort einen Fall:

| Regel | Status | |
|---|---|---|
| **R2** — Tagesverlustlimit −3 % | **fehlte** | jetzt implementiert |
| R3 — Mindest-CRV 1:2 | n/a | folgt aus `take_fraction`/`stop_fraction`, die gesweept werden; ein hartes 1:2 löschte den Hauptregler der Strategie |
| R6 — kein Martingale | n/a | Größe steigt nach einem Verlust konstruktionsbedingt nie: entweder festes Lot oder aus dem (gefallenen) Kapital abgeleitet |
| M2 — Puffer jenseits des Levels | n/a | der Stop ist ein Anteil der Vorhersage, kein Level mit Puffer — es gibt hier kein strukturelles Level |
| M4 — gemeinsames Metallbudget | n/a | diese Engine handelt ein Symbol; das Budget gehört in die Schicht, die beide führt |

### R2, und warum die Messung verkehrt herum aussieht

| | Trades | Erwartung | Median | schlechtester Markt |
|---|---:|---:|---:|---:|
| mit R2 | 67 | +0,1002 R | +9,90 % | **−2,78 %** |
| ohne R2 | 68 | +0,1127 R | +11,79 % | **+0,86 %** |

Die Schutzregel macht den schlechtesten Markt **schlechter**. Wer das flüchtig liest, hält R2
für schädlich.

Was tatsächlich dasteht: Der Simulator gibt der Strategie eine echte Kante. Wer nach einem
schlechten Tag aufhört, verpasst die Erholung, die dieser Markt anschließend liefert. **Ein
Markt, der einen fürs Weitermachen bezahlt, kann eine Versicherung nicht bepreisen.**

R2 ist die Versicherung gegen den Fall, dass die Kante **nicht** da ist — und das ist genau der
Fall, den für echtes Gold niemand ausgeschlossen hat. Dieselbe Lage wie bei R4 und M5: Der
Simulator kann die Regel nicht bewerten, der Test prüft ihre Einhaltung, nicht ihren Nutzen.

Der Tag wird dabei am **Broker-Rollover** begrenzt, nicht um Mitternacht UTC — sonst füllte
sich das Budget mitten in der New Yorker Session wieder auf, also genau dort, wo die Verluste
entstehen, die es auslösen.


---

## A17 · R2 und der Risikodeckel greifen ineinander — und R2 kippt das 400-€-Konto

Kaum war R2 aktiv, fielen zwei Tests um. Beide waren **keine** Testfehler.

### Erstens: R2 macht aus einem Gewinntag einen Verlusttag

Auf dem 400-€-Konto, 40 unabhängige Handelstage:

| | Median | Tage im Plus | schlechtester | bester |
|---|---:|---:|---:|---:|
| mit R2 | **−2,73 %** | 40 % | −9,20 % | +34,00 % |
| ohne R2 | **+8,19 %** | 75 % | −14,30 % | +34,00 % |

Der Grund ist Arithmetik, nicht Marktverhalten: Auf diesem Konto erzwingt das Mindestlot
**1,3 % bis 8,7 % Risiko je Trade**. Ein Tageslimit von −3 % ist damit nach **ein bis zwei
Verlierern** erreicht — und der Tag ist vorbei, oft während das Konto unten steht.

R2 wurde für ein Konto entworfen, das R1 einhalten kann: Bei 1 % je Trade bedeutet −3 % *drei*
Verlierer. **R1 und R2 sind aufeinander kalibriert. Wenn R1 nicht einhaltbar ist, wird R2 zu
etwas anderem.**

Das ist kein Argument, R2 abzuschalten — der schlechteste Tag verbessert sich von −14,3 % auf
−9,2 %, die Regel tut genau das, wofür sie da ist. Es ist ein weiteres Argument dafür, dass
**400 € für dieses Regelwerk zu wenig sind**, dieselbe Schlussfolgerung wie in
[KONTOGROESSE.md](./KONTOGROESSE.md).

Der Regelstand steht ab jetzt **in jeder Journalzeile** (`daily_loss_limit`), wie schon der
Slippage-Wechsel. Die 54 Sitzungen davor liefen ohne R2 und sind mit späteren nicht direkt
vergleichbar.

### Zweitens: Ein Deckel über dem Tageslimit macht daraus ein Ein-Trade-Limit

| Deckel | Bars mit aktivem R2 | größter Einsatz |
|---:|---:|---:|
| keiner | **17,9 %** | 15,3 % |
| 10 % | 17,8 % | 12,2 % |
| 6 % | 16,3 % | 6,8 % |
| 4 % | 12,1 % | 4,4 % |
| **2,5 %** | **4,3 %** | 2,5 % |
| 2 % | 1,4 % | 2,0 % |

Monoton, und die Kante liegt genau dort, wo der Deckel unter die 3 % des Tageslimits fällt.
Solange ein einzelner Trade mehr riskieren darf als der Tag erlaubt, beendet **ein** Verlierer
den Tag.

**Praktische Folge:** Wer `max_risk_pct` setzt, sollte es unter `DAILY_LOSS_LIMIT_PCT` setzen,
sonst hebt der Deckel das Tageslimit auf, statt mit ihm zusammenzuarbeiten.

### Was dabei ein Test falsch behauptet hat

Der umgefallene Deckel-Test behauptete, ein engerer Deckel koste Erwartungswert je Trade. Über
40 Märkte gemessen überlappen die Bänder vollständig (+0,10…+0,30 gegen +0,00…+0,35) — die
Differenz war **nie belegt**. Der Test hielt Rauschen fest und ging erwartungsgemäß kaputt,
sobald R2 es verschob.

Neu prüft er, was monoton und robust ist: Der Deckel gibt Rendite ab und verbessert den
schlechtesten Fall. Das ist weniger, als ich damals geschrieben habe, und es ist das, was die
Daten hergeben.


---

## A18 · Das Trainingslog mischt Regelwerke, und fünf von sechs Siegern lagen am Rand

Der Trainingsloop sammelt Durchgänge über Tage. Die Engine hat sich in derselben Zeit
mehrfach geändert — Slippage (A8), R2 und M5 (A15/A16). Das Log hielt nur `slippage_fraction`
fest. `summarise()` poolte trotzdem über alles.

**Die Warnung deckt sofort einen bestehenden Bruch auf:**

```
ACHTUNG: dieses Log mischt Regelwerke.
    3 Durchgaenge mit Slippage 0, R2 aus, M5 aus
    3 Durchgaenge mit Slippage 0.5, R2 aus, M5 aus
```

Die Hälfte der Durchgänge wurde also zu einem Drittel zu billig gerechnet, und die
Gesamtbilanz verglich sie trotzdem miteinander. `regime_of()` liest fehlende Felder als „aus"
— ein Durchgang von vor der Regel lief tatsächlich ohne sie, alles andere wäre eine
rückwirkende Umdeutung.

### Und ein Muster, das vorher niemand gezählt hat

| Durchgang | Stellschraube | Sieger | getestetes Raster | |
|---:|---|---:|---|---|
| #0 | take_fraction | **1,0** | 0,3 … 1,0 | **Rand** |
| #1 | stop_fraction | **0,25** | 0,25 … 1,0 | **Rand** |
| #2 | edge_fraction | **0,15** | 0,15 … 0,45 | **Rand** |
| #3 | confirm_bars | **2** | 2 … 5 | **Rand** |
| #4 | min_range_atr | 10,0 | 2,0 … 35,0 | innen |
| #5 | time_stop_bars | **480** | 60 … 480 | **Rand** |

**Fünf von sechs Siegern liegen am Ende ihres Rasters.** Ein Sieger am Rand heißt nicht
„dieser Wert ist optimal", sondern „das Raster ist ausgegangen" — was jenseits davon liegt,
wurde nie gemessen. Wer solche Werte übernimmt, verschiebt eine Stellschraube an eine Grenze,
die nie gegen ihr Jenseits geprüft wurde.

Der Bericht sagt das jetzt (`RANDTREFFER`). Zusammen mit dem bereits vorhandenen Vermerk
„kein Vorsprung über dem Rauschen", den **fünf von sechs** Durchgängen tragen, bleibt von
sechs gekürten Siegern kein einziger übrig, den man guten Gewissens übernehmen würde.

Das ist kein Argument gegen den Trainingsloop. Es ist genau das, was er leisten soll: sagen,
wann eine Zahl nichts bedeutet. Vorher hat er sechsmal einen Sieger gemeldet und nie dazu,
wie wenig das heißt.


---

## A19 · Der beobachtete Spread ist dreimal so hoch wie der berechnete — und in einer Tagessitzung entscheidet er

Beim Kursabruf stand heute **Bid 4.048,35 / Ask 4.049,39**, also ein Spread von **1,04 $/oz**.
Die Kette hat in **53 von 56** Sitzungen mit **0,34 $** gerechnet — dem Wert aus einer
früheren Abfrage. Das ist das Dreifache.

Und in einer Ein-Tages-Sitzung ist das nicht egal:

| Spread | Erwartung je Trade | 95 %-Band |
|---:|---:|---|
| 0,00 $ | +0,1841 R | +0,058 … +0,310 |
| **0,34 $ (bisher berechnet)** | **+0,1141 R** | −0,014 … +0,242 |
| 0,68 $ | +0,0139 R | −0,115 … +0,142 |
| **1,04 $ (heute beobachtet)** | **−0,0647 R** | −0,191 … +0,062 |
| 1,50 $ | −0,2104 R | −0,334 … −0,087 |

**Beim tatsächlich beobachteten Spread ist der Erwartungswert negativ.** Und schon bei 0,34 $
schneidet das Band die Null.

### Warum C2 das Gegenteil sagt — und beide stimmen

C2 misst „kein Nulldurchgang bis 1,20 $" und gilt weiter; neu gemessen unter dem aktuellen
Kostenmodell steht dort +0,0675 R bei 1,20 $. Der Unterschied ist **nicht** das Kostenmodell
und **nicht** R2 — beides geprüft und ausgeschlossen.

Es ist die **Zielgröße**:

| Bars | Trades | mittleres Ziel | Spread-Anteil am Ziel |
|---:|---:|---:|---:|
| 1.440 (eine Sitzung) | 7,8 | **19,44 $** | 2,6 % |
| 12.000 (C2) | 42,4 | **30,24 $** | 1,7 % |

Über einen einzelnen Handelstag hat die Tagesspanne-Rückschau weniger Material, die
vorhergesagte Bewegung fällt kleiner aus, und derselbe absolute Spread ist ein größerer
Anteil davon. Der Erwartungswert selbst hängt **nicht** von der Lauflänge ab — das ist
geprüft und wäre sonst die naheliegendere Erklärung gewesen.

**Konsequenz:** Die Zahlen aus dem Papier-Lauf sind mit dem günstigeren von zwei beobachteten
Spreads gerechnet, und die Strategie ist in dieser Betriebsart empfindlicher gegen den Spread
als C2 nahelegt. Zwei Beobachtungen sind keine Verteilung — was daraus folgt, ist nicht „der
Spread ist 1,04", sondern **„der Spread gehört bei jeder Sitzung frisch abgelesen, nicht
fortgeschrieben"**.

### Behoben: `--spread` wird verlangt, nicht vorbelegt

Genau das war vorher nicht durchsetzbar. `--spread` fiel still auf **0,30 $** zurück, wenn
man es wegließ — also auf den Wert, der nach der Tabelle oben über das Vorzeichen entscheidet.
Ein Vorgabewert, der das Ergebnis dreht, ist keine Bequemlichkeit.

`python -m metals paper` bricht jetzt mit **Rückgabecode 5** ab, wenn `--spread` fehlt, und
nennt die Quelle (Ask minus Bid aus derselben Kursabfrage). Anders als bei der angesetzten
Spanne (Code 4) und beim übersampelten Tag (Code 3) gibt es dafür **kein `--force`**: Diese
beiden überstimmen eine Einschätzung, die man sehen kann. Hier gäbe es nichts zu überstimmen
außer einer Zahl, die man sich ausdenken müsste.

Ein ausdrücklich angegebener Spread von 0,00 $ bleibt erlaubt. Er ist für Gold falsch, aber
er steht dann im Kostenmodell der Ledger-Zeile und ist damit angreifbar — im Unterschied zu
einem, den nie jemand getippt hat.


## A26 · Die beiden Dateien, die den Bot tatsächlich steuern, waren aus der ersten Woche

Während 25 Auditbefunde entstanden, blieben zwei Dateien unangetastet — ausgerechnet die,
aus denen der Assistent seine Anweisungen zieht: `.claude/skills/gold-silber-analyse/SKILL.md`
und `.claude/commands/trade.md`. Vier konkrete Fehler:

**1. Die hervorgehobene Kennzahl war um Größenordnungen zu klein.** SKILL.md nannte unter
der Überschrift *„Die eine Zahl, die beim Scalping zuerst kommt"*:

> Bei 3 USD/oz Stop und 0,20 USD/oz Spread startet jeder Trade 6,7 % seines Risikos im Minus.

0,20 $/oz gilt in der London/NY-Überlappung. Beim Rollover sind es rund **5 $/oz**, in den
Sekunden um NFP/CPI/FOMC rund **8–15 $/oz** — also **167 %** bzw. **270–500 %** desselben
Stops. Der prominenteste Satz der Datei nannte den Bestfall als *den* Fall.

**2. Eine Anweisung, die der Nutzer nicht ausführen kann.** `trade.md` verlangte
„Ziel 1 → 60 % schließen, Rest laufen lassen". 60 % von 0,01 Lot sind 0,006, unter dem
Broker-Minimum. Auf einem Mindestlot-Konto gibt es den Teilschluss nicht — [A13](#) hatte
das gemessen und die Vorlage stand unverändert daneben.

**3. Eine erfundene Zahl mit dem Anschein einer gemessenen.** Die Antwortvorlage verlangte
`KONFIDENZ: <n>%`. Diese Zahl existiert nicht; sie wäre geraten. Das Projekt arbeitet sonst
ausschließlich mit Konfidenz**bändern** aus Messungen — und SKILL.md verbietet im selben
Atemzug „‚hohe Wahrscheinlichkeit'-Formulierungen ohne die Unsicherheit dazu".

**4. Die zentrale Einschränkung fehlte ganz.** Keine der beiden Dateien erwähnte, dass
**kein einziges Ergebnis dieses Repositories an echter Intraday-Historie geprüft ist**. Ein
Assistent, der `docs/URTEIL.md` liest und „+0,198 R" zitiert, ohne zu wissen, dass die Zahl
vom Simulator stammt, gibt eine Simulation als Marktaussage aus.

Alle vier behoben, und die Nachschlagetabelle nennt jetzt auch `REPO-AUDIT.md`,
`PAPIER-LAUF.md`, `URTEIL.md`, `KONTOGROESSE.md`, `LERNEN.md` und `YOUTUBE-RECHERCHE.md` —
also die Seiten, auf denen die gemessenen Ergebnisse überhaupt stehen.


## A25 · Der Regelkatalog verschwieg eine Grenze, die der Code durchsetzt — und die Messung dazu kippte sie

`metals rules` überschreibt sich mit *„HARD RISK RULES (in code, not configuration)"* und
listete vierzehn. Der Code setzt fünfzehn durch: `exits.DAILY_WIN_TARGET_PCT = 2.0` sagt seit
jeher **AUFHÖREN** bei +2 % am Tag, stand aber in keinem Katalog. Dieselbe Form wie A20 und
A23 — ein Verzeichnis, das weniger meldet, als es gibt.

Eingetragen als **R2b**. Und weil `RULE_COVERAGE` erzwingt, dass jede Regel der Risikoschicht
in der Strategie eine Entscheidung bekommt, hat der Eintrag sofort eine echte Frage
aufgeworfen: **Soll der Bot bei +2 % auch aufhören?**

### Gemessen statt entschieden

Implementiert als `daily_win_limit`, gepaart über identische Kursreihen — dieselben Märkte
zweimal, einmal mit und einmal ohne Regel:

| | ohne R2b | mit R2b |
|---|---:|---:|
| Median | −1,26 % | **+2,39 %** |
| Verlusttage | 54,2 % | **34,5 %** |
| schlimmster Tag | −11,35 % | **−9,18 %** |
| **Mittelwert** | **+1,75 %** | **+0,77 %** |

**Drei von vier Zahlen, auf die ein Mensch schaut, werden besser. Die eine, die zahlt, wird
schlechter.** Über 1.200 Märkte: **−1,34 % je Tag, Band −1,72 … −0,96**, klar unter der Null.

Das ist genau Behauptung **C1 im zweiten Kostüm**: Ein Gewinnziel kauft Trefferquote mit
Erwartungswert. Es verwandelt eine Verteilung in einen Haufen bei exakt +2 % plus die
Verlierer — und bezahlt das mit den Tagen, die den Monat gemacht hätten.

**Eine Vorsichtsmaßnahme, die sich gelohnt hat:** Die erste Messung über 200 Märkte ergab
−0,14 % mit einem Band, das die Null schneidet. Das ist eine unterbesetzte Stichprobe, keine
Widerlegung — nachgeprüft mit drei unabhängigen Seed-Blöcken zu je 400 Märkten: −0,98 %,
−1,30 %, −1,64 %, alle Bänder klar unter Null. Beinahe hätte ich das Gegenteil veröffentlicht.

**Konsequenz:** R2b gilt **dem Menschen am Rechner** und nicht der Strategie. Der Unterschied
ist kein Taschenspielertrick: R2b adressiert, dass jemand nach einem guten Tag anfängt zu
zocken. Eine Strategie tut das nicht, und ein Verhaltensmittel auf etwas ohne Verhalten
anzuwenden kostet 1,3 % am Tag. Der Regeltext sagt das jetzt, und `RULE_COVERAGE` trägt die
Messung als Begründung.


## A24 · Eine Broker-Werbezahl stand als Kontraktspezifikation im Code — **behoben**

`metals/specs.py` führte in den Notizen zu XAUUSD:

> PU Prime quotes roughly 0.30 USD/oz average on Standard accounts and 0.08 USD/oz on
> Prime/ECN accounts

Das ist die Eigenwerbung **eines** Brokers, geführt als Teil der Kontraktspezifikation.
`CLAUDE.md` verbietet das wörtlich: *„Marketingzahlen nicht als Fakten führen."*
Und `thin_spread_usd_oz` stand auf **1,00** — der beobachtete Spot-Spread am 31.07. lag mit
1,04 bereits über dem, was die Spezifikation als *dünnen Markt* auswies.

Ersetzt durch Spannen mit Quellenart, und um die beiden Zahlen ergänzt, die dem Projekt
gefehlt haben:

| Wann | Spread | gegen einen 3-$-Stop |
|---|---:|---:|
| London/NY-Überlappung, kompetitiver Broker | 0,10–0,25 $/oz | 3–8 % |
| Standardkonto, liquide Zeit | 0,20–0,40 $/oz | 7–13 % |
| **Rollover (~22:00 Serverzeit)** | **~5 $/oz** | **167 %** |
| **Sekunden um eine hochwirksame Veröffentlichung** | **~8–15 $/oz** | **270–500 %** |

Quellenart: Broker-Vergleiche und Broker-Schulungsseiten. Keine akademische Quelle, keine
Messung eines Kontos — Größenordnung.

**Warum die letzten beiden Zeilen wichtiger sind als der Rest.** R4 und R5 waren in diesem
Projekt Maximen. Sie sind Arithmetik: Beim Rollover ist der Spread allein größer als der
ganze Stop, um NFP das Drei- bis Fünffache. **Es gibt keinen Einstiegskurs, der das rettet.**

Und das ist der Grund, warum keine Messung dieses Repositories je auf diese Regeln kommen
konnte: **Der Simulator berechnet einen Spread für den ganzen Tag.** Eine Regel, die die
eigene Messmaschine strukturell nicht begründen kann, braucht trotzdem eine Begründung —
deshalb stehen die Zahlen jetzt in der Spezifikation und nicht in einem Fließtext.

### Nachtrag zu A19: was 1,04 $ war und was nicht

A19 nannte „Bid 4.048,35 / Ask 4.049,39" den *beobachteten Spread*. Genauer: Das war der
Spot-Quote **eines Datenanbieters**, nicht der Quote eines MT5-Brokers. Die **Messung** von
A19 steht unverändert — der Spread entscheidet in einer Tagessitzung das Vorzeichen. Die
**Zuordnung** war unpräzise: 1,04 $ ist für ein Broker-Konto in liquider Zeit eher zu
pessimistisch, 0,34 $ eher zu optimistisch. Was daraus folgt, ändert sich nicht, sondern wird
schärfer: **Der Spread gehört bei jeder Sitzung von der eigenen Plattform abgelesen.**

### Und die 10er-Falle, als Arithmetik statt als Warnung

`price_decimals` entscheidet die Pip-Konvention: Ein Broker mit zwei Nachkommastellen nennt
0,10 $/oz einen Pip, einer mit drei nennt 0,01 $/oz einen Pip. Eine der Quellen für die
Tabelle oben schreibt „30 Pips = 3 USD pro Lot", was 1 Pip = 0,001 $/oz erfordert und der
eigenen Notierung widerspricht. `PIP_CONVENTIONS_USD_OZ` hält beide Konventionen fest —
deshalb rechnet dieses Paket nirgends in Pips.


## A23 · „Umgesetzt" bedeutete zweierlei — und R4 war in 37 von 57 Sitzungen aus

Die Tabelle `RULE_COVERAGE` in `metals/dayrange.py` gibt es wegen A16: Dreimal war eine
Regel der Risikoschicht nie in der Strategie angekommen (R1 in A1, R4 in A7, M5 in A15),
und jedes Mal blieb die *nächste* Lücke unsichtbar, bis zufällig jemand hinsah. Die Tabelle
sollte das beenden.

Sie hatte selbst eine Lücke, und ausgerechnet bei R4.

`weekend_flat`, `daily_loss_limit`, `max_positions` und `min_range_atr` sind standardmäßig
**an**. Wer nichts konfiguriert, ist durch sie geschützt. R4 ist es nicht:

```python
news_times_utc: tuple[tuple[int, int], ...] = ()      # Vorgabe: leer
...
if not news_times_utc:
    return False                                       # sperrt nichts
```

Beide standen in der Tabelle als `"implemented"`. Im Journal heißt das:

```
20 von 57 Sitzungen hatten ueberhaupt Sperrzeiten gesetzt
R4 war also in 37 Sitzungen wirkungslos
```

Eine abgeschaltete Regel schützt genau so viel wie eine nie geschriebene. Und **drei
Auditbefunde sind dieselbe Regel**, die nirgends ankommt: A7 (die Strategie sah die Sperre
nie), A9 (`--news` war an die falsche Funktion verdrahtet und tat zehn Sitzungen lang
nichts), A20 (der Kalender dahinter hatte kein FOMC). Jeder wurde behoben, und R4 blieb aus.

**Zwei Änderungen.**

**1. Die Tabelle bekommt einen dritten Status.** `"needs-input"`: Der Mechanismus ist da und
getestet, und er ist aus, bis ihn jemand füttert. `rules_needing_input()` listet sie auf, und
ein Test weist die Wirkungslosigkeit **mechanisch** nach — er prüft alle 96 Viertelstunden
eines Tages gegen eine Standardkonfiguration, statt dem Kommentar zu glauben. Wird R4
irgendwann standardmäßig eingeschaltet, schlägt der Test fehl und die Tabelle muss korrigiert
werden. Genau darum geht es: Die letzten drei Male hat es niemand bemerkt.

**2. Der Kalender ist jetzt das, was ohne Entscheidung passiert.** `--news` greift ohne
Angabe auf den eingebauten Kalender zurück. R4 abzuschalten muss man tippen, und es wird
angesagt:

```
R4 ausgeschaltet (--news none): keine Nachrichtensperre.
```

Angegebene Zeiten schlagen weiterhin den Kalender.


## A22 · `metals minimum` fragte nach einem Kontostand ohne Währung — **behoben**

Direkt neben A21 aufgefallen und dieselbe Familie. `metals minimum` rechnet durchgehend in
Dollar — „account needed 240 USD", „risk 1.80 USD" — und nahm `--equity` **ohne Einheit**
entgegen:

```
YOUR ACCOUNT: 185.00
```

Das Beispiel in der README lautet `minimum XAUUSD --equity 55`, und das Konto, um das
dieses ganze Projekt gebaut ist, läuft in **Euro**. Wer seinen Euro-Stand eintippt, wird
gegen Dollar-Schwellen geprüft und damit um den Wechselkurs zu klein gerechnet — rund 15 %
beim Kurs vom 31.07.2026.

Und das bleibt nicht bei der Beschriftung. Bei **215 €**:

| Kurs | in Dollar | Verdikt bei 2,40 $/oz Stop |
|---:|---:|---|
| 1,0800 | 232,20 $ | REFUSED — über dem 1-%-Limit |
| 1,1476 | 246,73 $ | OK |

Ein 2,40-$-Stop braucht 240 $, damit die 1-%-Regel hält. Die beiden Kurse liegen auf
**verschiedenen Seiten** dieser Schwelle: dasselbe Konto, entgegengesetzte Antwort.

**Behoben.** Ohne Angabe wird `--equity` ausdrücklich als Dollar beschriftet und auf die
Alternative hingewiesen; `--eur` deutet ihn als Euro und zeigt beide Beträge samt Kurs und
dessen Status:

```
YOUR ACCOUNT: 185.00 USD (use --eur if this balance is in euro)
YOUR ACCOUNT: 185.00 EUR = 212.31 USD  (EUR/USD 1.1476, abgelesen)
YOUR ACCOUNT: 185.00 EUR = 199.80 USD  (EUR/USD 1.0800, ANGENOMMEN)
```


## A21 · Der Wechselkurs war eine Konstante, und die Konstante war falsch

`metals/paper.py` rechnet seit der ersten Sitzung mit

```python
ASSUMED_EUR_USD = 1.08
```

Der EZB-Referenzkurs am 30.07.2026 war **1,1476**. Die Abweichung beträgt 6,3 %, und sie
steht unter **jeder Euro-Zahl, die dieses Projekt je veröffentlicht hat.**

Daneben stand dieser Kommentar:

> „Written down rather than fetched: the rate moves, and **nothing here turns on its
> third decimal**."

Das ist der eigentliche Befund. Der Satz ist falsch, und zwar nicht knapp.

### Warum sich der Kurs nicht herauskürzt

Die naheliegende Annahme ist, dass er es tut: Euro rein mal Kurs, Dollar handeln, Euro
raus durch Kurs — das müsste sich aufheben. Bei **fester Losgröße** tut es das nicht.

Eine 0,01-Lot-Position riskiert eine Anzahl **Dollar**, die vom Stop-Abstand bestimmt
wird, nicht davon, was das Konto in Euro wert ist. Das Dollar-Ergebnis einer Sitzung
steht also fest, egal welcher Kurs eingesetzt wird — gemessen:

| Kurs | Ergebnis in € | × Kurs = in $ |
|---:|---:|---:|
| 1,0000 | −16,61 | −16,61 |
| 1,0800 | −15,38 | −16,61 |
| 1,1476 | −14,47 | −16,61 |
| 1,2000 | −13,84 | −16,61 |

Damit ist die Euro-Zahl das feste Dollar-Ergebnis **geteilt durch den Kurs**, und die
ganze Kette skaliert mit 1/Kurs. Ein Kursfehler ist hier kein Rundungsthema, sondern ein
proportionaler Fehler in jeder Euro-Zahl.

### Was das für die Kette heißt

```
Berichtet     1.799,24 €   (Gewinn +1.399,24 €)   bei Kurs 1,0800
Umgerechnet   1.716,82 €   (Gewinn +1.316,82 €)   bei Kurs 1,1476
Differenz       −82,42 €   (−5,89 % des Gewinns)
```

**Der ausgewiesene Gewinn ist um 5,9 % zu hoch.** Zwei weitere Zahlen hängen mit dran:

- **Das gemeldete Risiko je Trade ist zu hoch angesetzt.** Dieselbe Sitzung meldet 4,07 %
  bei Kurs 1,08 und 3,83 % bei 1,1476 — das Konto ist in Dollar größer, als die Rechnung
  annimmt.
- **Die Mindestkontogröße stimmt nicht.** `docs/PAPIER-LAUF.md` nennt „unter etwa 190 €
  kann gar nicht gehandelt werden". Bei 205 $ Margin sind das bei 1,08 tatsächlich
  189,81 €, bei 1,1476 aber **178,63 €**.

### Am Margin-Rand ist es keine Berichtsfrage mehr

Oberhalb der Margin-Schwelle verschiebt ein falscher Kurs nur Zahlen: dieselben Trades,
skalierte Euro-Beträge. **An der Schwelle entscheidet er, ob überhaupt gehandelt wird.**

Dieselbe Sitzung, dasselbe Konto, nur der Kurs unterschiedlich:

```
180 € bei Kurs 1,0800:  margin 202 USD > equity 194 USD   → kein Trade
180 € bei Kurs 1,1476:  4 Trades
185 € bei Kurs 1,0800:  margin 202 USD > equity 200 USD   → kein Trade
185 € bei Kurs 1,1476:  4 Trades
```

„Reicht mein Konto?" ist eine Frage, die dieses Projekt laut beantwortet — `metals minimum`
tut nichts anderes. Es hat sie mit einer Konstanten beantwortet, und für Konten zwischen
178 € und 190 € war die Antwort falsch.

### Was nicht modelliert ist — und das ist der größere Punkt

Derselbe Kurs auf beiden Seiten heißt: Die Kette hat in 57 Sitzungen **null
Währungsrisiko** modelliert. Ein Euro-Konto, das XAUUSD handelt, trägt es aber:
Gold kann in Dollar steigen und das Konto trotzdem in Euro verlieren, wenn der Euro
gleichzeitig stärker wird. Der Kurs bewegt sich zwischen Eröffnung und Schluss einer
Position, und keine einzige Zahl im Journal enthält davon irgendetwas.

Das ist keine Kleinigkeit für ein 400-€-Konto: EUR/USD bewegt sich an einem normalen Tag
um 0,3–0,6 %, an einem EZB- oder FOMC-Tag deutlich mehr. Das ist in derselben
Größenordnung wie das, was die Strategie an einem Tag verdienen soll.

### Was geändert wurde

**Der Kurs wird pro Zeile aufgezeichnet**, mit dem Vermerk, ob er abgelesen oder
angenommen wurde — dieselbe Behandlung wie `range_observed`:

```
EUR/USD 1.1476 (abgelesen) — jede Euro-Zahl haengt daran
EUR/USD 1.0800 (ANGENOMMEN) — jede Euro-Zahl haengt daran
```

`--eur-usd` nimmt den abgelesenen Kurs. Er ist bewusst **nicht** verpflichtend wie
`--spread` nach A19: Ein falscher Spread dreht das Vorzeichen des Erwartungswerts, ein
falscher Kurs skaliert das Ergebnis. Beides ist schlecht, aber nur das erste macht aus
einem Verlust einen Gewinn.

**Die 57 bestehenden Zeilen werden nicht stillschweigend umgerechnet.** Sie wurden unter
1,08 geschrieben, das steht jetzt in ihnen, und `paper --restate 1.1476` liest die Kette
zu einem anderen Kurs, ohne sie zu verändern. Die Bilanz warnt, solange Zeilen mit einer
Annahme darin stehen.

**Die Nachrechnung nimmt den Kurs der jeweiligen Zeile**, nicht den heutigen. Eine
Prüfung, die eine Zeile mit einem neueren Kurs nachrechnet, rechnet eine andere Sitzung
nach und nennt die Differenz dann einen Fehler.


## A20 · Der Kalender versprach FOMC und lieferte nie eines — **behoben**

Der Modul-Docstring von `metals/sources/calendar.py` sagt seit jeher:

> „FOMC statements at 14:00 ET on their published schedule … so the schedule is
> *computed* here rather than fetched."

`IMPACT_NOTES` enthielt einen FOMC-Eintrag. Die Alias-Tabelle kannte vier Schreibweisen
davon. Nur eines fehlte: **`StaticCalendar.events()` gab kein einziges FOMC-Ereignis aus.**
Erzeugt wurden ausschließlich NFP, CPI-Fenster und Erstanträge.

Nachgewiesen am 29.07.2026, einem FOMC-Entscheidungstag:

```
Ereignisse 27.07.–03.08.2026:
  2026-07-30 12:30 UTC  medium  Initial Jobless Claims
FOMC enthalten? False
blackout() um 14:00 ET: (False, None)
```

Ein Sieben-Tage-Fenster über einen Zinsentscheid liefert **ein** Ereignis, und das
ist nicht der Zinsentscheid.

### Warum das durchrutschte

Weil es nicht wie ein Fehler aussieht. Ein Kalender ohne FOMC meldet keine Ausnahme
und gibt keine leere Liste zurück — er meldet **eine ruhige Woche**. Genau deshalb
konnte A7 als „behoben" gelten: A7 hat dafür gesorgt, dass `news_times_utc` die
Strategie erreicht, aber der Kalender, der die Zeit liefern sollte, hatte keine.
Die Reparatur lag eine Schicht zu hoch.

Ableitbar war es auch nicht: NFP ist „erster Freitag", CPI ist „10. bis 15." — ein
Zinsentscheid ist das, was das Gremium veröffentlicht hat. Deshalb steht er jetzt als
**Liste** im Code, nicht als Regel.

**Behoben.** `FOMC_DECISION_DATES` (2026 bestätigt, 2027 vorläufig, Quelle
federalreserve.gov) und `ECB_DECISION_DATES` (Quelle ecb.europa.eu). Je Entscheid
werden **zwei** Ereignisse erzeugt — Statement 14:00 ET und Pressekonferenz 14:30 ET.
Mit je 30 Minuten Sperre davor und danach ergibt das ein durchgehendes Fenster von
13:30 bis 15:00 ET. Das ist beabsichtigt: Die Pressekonferenz dreht die Bewegung des
Statements regelmäßig um.

Die EZB ist mit aufgenommen, aus einem Grund, den man leicht übersieht: **Das Konto
läuft in Euro.** Ein EZB-Entscheid verändert das Ergebnis, ohne dass Gold sich bewegt.

### Zwei Fehler, die beim Einbau aufgefallen sind

**1. Ein falsches Datum in der übernommenen Quelle.** Worldmonitors Kalender-Seeder
führt als ersten EZB-Termin 2026 den **30.01.2026**. Das ist ein **Freitag** — der
EZB-Rat verkündet donnerstags. Der tatsächliche erste Entscheid 2026 war der
**05.02.2026** (EZB-Pressemitteilung `ecb.mp260205`). Gefunden hat das kein Mensch,
sondern ein Test, der auf jedem Datum der Liste den Wochentag prüft. Er bleibt drin.

**2. „Rate Decision" gehörte der falschen Notenbank.** `_match_note` nimmt den ersten
Treffer, und FOMC stand vor EZB und besaß die Wendung `"rate decision"`. Eine
Live-Feed-Zeile „ECB Rate Decision" bekam damit die Fed-Notiz: falsche Notenbank,
falsche Währung, falsche erwartete Bewegung. Die Reihenfolge ist jetzt umgekehrt und
durch einen Test festgehalten.

### Und wo die Liste endet, sagt sie das

Eine Liste läuft irgendwann aus. Eine ausgelaufene Liste, die stumm bleibt, antwortet
„keine hochwirksame Veröffentlichung" für ein Datum, über das sie nichts weiß — also
exakt derselbe Fehler wie A20, nur verschoben auf das Jahr, in dem die Liste endet.
`horizon_gap()` nennt den letzten abgedeckten Tag, und `known_through()` nimmt den
**früheren** der beiden Listenenden, nicht den späteren.


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

## A8 · Drei Engines, drei Kostenmodelle — **behoben**

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

**Nachtrag: `metals/microscalp.py` hatte dieselbe Lücke** und ist ebenfalls behoben. Der
Unterschied zum festen Lot, das dort bewusst bleibt: Das feste Lot **ist** der Gegenstand der
Messung, Teil der geprüften Strategie. Slippage ist eine Eigenschaft der Welt — sie
wegzulassen ließ den Ansatz besser aussehen, als er ist, und das schwächt ausgerechnet einen
Befund, dessen Aussage lautet, dass der Ansatz ruinös ist.

Gemessen an der Werbevideo-Konfiguration (0,02 Lot, 8 Positionen, 1:500), 25 Märkte:

| | nur Spread | Spread × 1,5 |
|---|---:|---:|
| Trefferquote | 99,2 % | 97,9 % |
| Median | −98,4 % | −98,4 % |
| **Stop-out** | **68 %** | **76 %** |

Die Korrektur verschärft den Befund also. **Die Zahlen in
[MICRO-SCALPING.md](./MICRO-SCALPING.md) und [WERBEVIDEO-ANALYSE.md](./WERBEVIDEO-ANALYSE.md)
stammen aus Läufen vor dieser Änderung** und sind entsprechend eher zu freundlich. Sie werden
nicht überschrieben — die Tabelle oben stammt aus einer nachgebauten Konfiguration, und eine
nachgebaute Zahl an die Stelle einer gemessenen zu setzen wäre eine Verschlechterung, keine
Korrektur.

---

## A9 · `--news` war zehn Sitzungen lang wirkungslos — **behoben**

Nach A7 wurde die Nachrichtensperre in `run_session` eingebaut und ab Sitzung 7 bei jedem
Lauf mit `--news "12:30,18:00"` übergeben. Das Journal zeigt für **jede** dieser Sitzungen
`news_times_utc=[]`.

Grund: Beim Verdrahten landete das Argument in `cmd_analyse` statt in `cmd_paper` — eine
Textersetzung traf die erste passende Stelle. Damit war gleichzeitig `analyse` kaputt
(`unexpected keyword argument`), was nur deshalb nicht auffiel, weil dieser Befehl in
dieser Umgebung ohnehin am 403 der Kursanbieter scheitert.

**Die Testlücke ist der eigentliche Befund.** Vier Tests prüften die Sperre — alle riefen
`run_session(...)` direkt auf. Sie liefen grün, während `python -m metals paper --news ...`
nichts tat. **Ein Test der Engine kann einen Befehl nicht prüfen, der die Engine nie
erreicht.**

Behoben, und drei Tests gehen jetzt durch Parser *und* Kommandofunktion und prüfen, dass
`--news` und `--spread` tatsächlich in der Sitzung ankommen.

**Und die Lücke war größer als dieser eine Befehl.** Eine Zählung ergab: von 18
Unterbefehlen hatten **5** überhaupt einen Test, der durch den Parser geht.
`tests/test_cli_smoke.py` deckt das jetzt ab — jeder Befehl wird geparst, dispatcht und
ausgeführt. Drei Befehle (`analyse`, `quote`, `ratio`) sind ausdrücklich als
netzabhängig gelistet, und ein Test schlägt fehl, wenn ein neuer Befehl weder eine
Smoke-Prüfung noch diesen Eintrag bekommt: **Ein ungetesteter Befehl soll eine sichtbare
Entscheidung sein, kein Versehen.**

Zwei der Smoke-Fälle sind sofort fehlgeschlagen — beide an meinem Testcode, nicht am
Programm (`--source simulated` statt `sim`, und `journal` schreibt seine Meldung nach
stderr). Genau dafür sind sie da.

**Für die Kette heißt das:** Die Sitzungen 1–16 liefen alle **ohne** Nachrichtensperre. Die
Einträge sagen das korrekt (`news_times_utc=[]`) — die Behauptung, sie sei aktiv gewesen,
stand nur in meinem Bericht, nicht in den Daten.

---

## A10 · Der EA handelte eine andere Strategie als die, die gemessen wird — **portiert, Kompilierung offen**

Das ist der schwerste Befund des Projekts, und er ist noch nicht behoben.

`mt5/Experts/GoldScalpAssistant.mq5` implementiert **drei Scalping-Setups**: S2 (Pullback
Window Break), S4 (Round Number Fade), S5 (Momentum Continuation). Die Datei enthält
**null** Vorkommen der Tagesspanne-Strategie.

Die Tagesspanne-Strategie ist aber die, die der Nutzer vorgegeben hat („Bewegung
vorhersagen, die Hälfte mitnehmen, Stop auf der Gegenseite"), die in `metals/dayrange.py`
steht, und über die **jede Zahl** in [PAPIER-LAUF.md](./PAPIER-LAUF.md) und
[KONTOGROESSE.md](./KONTOGROESSE.md) spricht — 21 Sitzungen, 180 Trades, Konfidenzbänder,
Design-Effekt.

**Konsequenz, unmissverständlich:** Wer den EA installiert, handelt die drei Setups oben —
nicht die Strategie, um die es die ganze Zeit ging. Keine der gemessenen Zahlen beschreibt,
was diese Datei tun würde.

Der Modulkopf des EA behauptete bis eben: *„Implements the same setups and the same hard
risk limits as the Python package"*. Für die Scalping-Setups stimmt das. Als Aussage über
„die Strategie" führt es in die Irre, und ein Leser nach 21 Sitzungen Tagesspanne-Ergebnissen
liest es genau so. Der Kopf sagt jetzt ausdrücklich, was **nicht** drin ist.

**Portiert.** `DetectDayRange` steht jetzt im EA — als zusätzliches Setup „DR" im
bestehenden EA, nicht als zweite Datei. Damit erbt es die geprüfte Infrastruktur:
Risikoschicht, Journal, Positionsverwaltung, Sessionerkennung. Ein zweiter EA hätte all das
dupliziert.

Abgesichert wird der Port nach dem Muster, das im Projekt schon für die Zeitzonen-Arithmetik
existiert (`tests/test_mt5_dayrange_parity.py`), mit drei verschiedenen Arten von Prüfung:

1. **Die Konstanten sind dieselben Zahlen.** Aus der `.mq5`-Quelle gelesen, nicht hier
   abgeschrieben — eine Änderung auf einer der beiden Seiten lässt den Test fehlschlagen
   statt auseinanderdriften.
2. **Die Logik feuert auf denselben Bars.** Eine bewusst wörtliche Transliteration des MQL5
   läuft gegen `metals.dayrange.predict` über 12.000 Bars: jedes Signal, jede Richtung und
   jedes vorhergesagte Ziel müssen übereinstimmen. Tun sie.
3. **Der Stop ist nie enger als in Python** — und das ist eine *Ungleichung*, mit Absicht.
   Der EA übergibt eine Stop-Ebene, und danach greifen M2 (Puffer jenseits des Levels), M1
   (mindestens 0,8 ATR) und der Broker-Mindestabstand. Die können nur weiten. Eine harte
   Risikoregel steht über der exakten Übereinstimmung mit einem Backtest.

**Standardmäßig ausgeschaltet** (`InpUseDayRange = false`). Die Kante ist auf echtem Gold
nicht nachgewiesen — 180 Trades auf dem Simulator ergeben ein Band, das die Null gerade
eben verlässt, nach zwanzig Blicken auf eine wachsende Stichprobe. Einschalten für Demokonto
und Strategietester, nicht weil eine Zahl gut aussah.

**Was weiterhin offen ist:** Ob die Datei **kompiliert**, kann hier niemand prüfen. Das
braucht MetaEditor. Alle Paritätstests der Welt ersetzen kein `F7`.

---

## A11 · Der Port hat Parität beim Einstieg, nicht beim Ausstieg — **gemessen, dokumentiert**

Der Paritätstest aus A10 prüft das **Signal**: Auf 12.000 Bars feuern MQL5-Port und Python
auf denselben Kerzen, in derselben Richtung, mit demselben vorhergesagten Ziel. Das ist
notwendig — und es ist nicht alles.

**Die Ausstiege sind verschieden:**

| | Python (`dayrange.py`) | EA (SECTION 10) |
|---|---|---|
| Ziel | **ein** Ziel bei 50 % der Vorhersage (= 1,0 R) | 60 % der Position bei **0,5 R**, Rest bis **2,5 R** |
| Rest | — | ATR-Trail (1,2 × ATR) |
| Zeitstop | 240 Bars (4 h) | 45 Minuten |

Wie viel das ausmacht, gemessen über 20 Märkte à 15.000 Bars:

| Ziel | in R | Trefferquote | Erwartungswert |
|---:|---:|---:|---:|
| 0,25 der Vorhersage | 0,5 R | 66,2 % | +0,099 R |
| **0,50 (Python-Standard)** | **1,0 R** | 57,0 % | **+0,110 R** |
| 1,00 | 2,0 R | 53,1 % | +0,085 R |
| 1,25 | 2,5 R | 52,5 % | +0,072 R |

Die EA-Struktur ist eine Mischung aus der 0,5-R- und der 2,5-R-Zeile, also grob
**+0,088 R gegen +0,110 R** — rund **20 % weniger**, wobei der Trail das in beide
Richtungen verschieben kann.

**Konsequenz, klar gesagt:** Der Erwartungswert, den der Papier-Lauf ausweist, beschreibt den
**Python-Ausstieg**. Der EA mit `InpUseDayRange = true` würde auf denselben Signalen ein
etwas niedrigeres Ergebnis liefern. Der Unterschied ist nicht dramatisch, aber er ist da, und
„portiert" heißt nicht „identisch".

*Hier stand ursprünglich eine konkrete Zahl („die +0,176 R aus PAPIER-LAUF.md"). Sie war zum
Zeitpunkt des Nachlesens weder dort noch sonst irgendwo aktuell — die Kette wächst, und der
Wert wandert mit ihr. Ein Dokument, das den beweglichen Wert eines anderen einfriert, ist nach
zwei Tagen falsch. Der aktuelle Stand kommt aus dem Befehl, nicht aus dieser Datei:*

```bash
python -m metals paper --evidence
```

**Warum nicht angeglichen:** Beide Ausstiege haben ein Argument. Der EA-Ausstieg (Teilgewinn
früh, Rest laufen lassen) ist in `docs/BACKTEST-ERGEBNISSE.md` für die Scalping-Setups
gemessen worden und dort besser als ein einzelnes Ziel. Der Python-Ausstieg ist der, den der
Nutzer beschrieben hat („bei der Hälfte schließen"). Einen davon dem anderen anzupassen wäre
eine Strategieentscheidung, keine Aufräumarbeit — und sie gehört auf echte Daten, nicht auf
den Simulator.

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

---

## A12 · Vier Trainingsläufe optimierten einen wirkungslosen Regler — **behoben**

Aufgefallen beim Walk-Forward-Test (C13), der den Optimierer gegen frische Märkte prüft:
`min_range_atr` wurde als „ROT" gemeldet, weil die getunte Einstellung out-of-sample
**exakt** denselben Erwartungswert lieferte wie der Standard. Exakte Gleichheit auf drei
Nachkommastellen ist kein Messrauschen, sondern ein Hinweis.

Nachgemessen, ein Markt, 12.000 Bars:

| `min_range_atr` | Signale | Trades | Erwartung |
|---:|---:|---:|---:|
| 0,5 | 43 | 43 | +0,1694 R |
| 1,0 | 43 | 43 | +0,1694 R |
| 2,0 | 43 | 43 | +0,1694 R |
| 3,5 | 43 | 43 | +0,1694 R |
| 5,0 | 43 | 43 | +0,1694 R |
| 20 | 26 | 26 | +0,2275 R |

**Der Regler tut zwischen 0,5 und 5 nichts.** Der Grund ist eine Größenordnung: Die
Tagesspanne von Gold ist auf M1 das **20- bis 100-fache** von ATR(14). Eine Untergrenze von
„2 × ATR" ist damit immer erfüllt. `train.py` hat vier Läufe lang genau (1,0 / 2,0 / 3,5 /
5,0) gesweept — vier identische Ergebnisse — und daraus einen „besten Wert" ins Log
geschrieben. Das ist Rauschen, protokolliert als Befund.

Der Test, der das hätte fangen sollen, benutzt `min_range_atr=1_000.0` und ging deshalb
durch: er prüft, *dass* die Grenze wirken **kann**, nicht dass die verwendeten Werte wirken.

**Behoben** — der Sweep läuft jetzt über (2,0 / 10 / 20 / 35), also über Werte, die
tatsächlich binden. Und weil das eine allgemeine Fehlerklasse ist, prüft ein neuer Test
**jeden** Regler in `DIALS`: Wenn der erste und der letzte Wert eines Sweeps dieselben
Trades und denselben Erwartungswert produzieren, ist die Optimierung darüber keine
Optimierung.

**Der Standard bleibt bei 2,0**, und zwar mit Messung: über 20 Märkte fällt der
Erwartungswert, sobald der Filter greift — +0,154 R bei 2 (wirkungslos), +0,118 R bei 20,
+0,071 R bei 35. Der Filter schadet, sobald er etwas tut. Er bleibt als Regler erhalten,
weil er eine sinnvolle Absicht ausdrückt, aber er wird nicht scharf gestellt.

---

## A13 · Der Misch-Test entschied auf einer Zahl, die von 0 % bis 205 % schwankt — **behoben**

Der Misch-Test ist die wichtigste Diagnose dieses Projekts: Er zerstört die Reihenfolge der
Kerzen und lässt alles andere gleich. Überlebt die Kante das, kommt sie nicht aus dem Chart.
Er hat hier schon einmal einen echten Fehlbefund gefangen.

In Trainingsdurchgang 6 schlug er an — 52 % überlebten bei `time_stop_bars = 480`. Bevor
daraus eine Konsequenz wurde, die Gegenprobe: **dieselbe Konfiguration auf zwölf Blöcken zu
je acht Seeds.**

| | |
|---|---|
| Spanne der Überlebensquote | **0 % bis 70 %** |
| Median | 12 % |
| Blöcke über der 50-%-Warnschwelle | **2 von 12** |

Die Quote ist also kein Urteil, sondern ein Münzwurf mit Nachkommastellen. Der Grund ist
mathematisch: Sie teilt durch einen verrauschten Nenner. Bei 16 Seeds kam sogar ein Block
mit **205 %** heraus — eine Prozentangabe über 100, die als Größe gar nicht interpretierbar
ist.

**Behoben.** Der Test rechnet jetzt die **gepaarte Differenz** original minus gemischt, Markt
für Markt, mit Standardfehler. Kein Nenner, ein Fehlerbalken, und derselbe Block liest sich
statt „205 %" als −0,034 R ± 0,046 — also klar: nichts gemessen. Dazu 16 statt 8 Märkte.

**Was das nicht gebracht hat, und das gehört dazu:** Die Fehlalarmquote sinkt **nicht** —
2 von 12 bei beiden Regeln, bei denselben Blöcken. Die Streuung sitzt *zwischen* den
Marktblöcken, nicht innerhalb. Mehr Seeds pro Durchgang lösen das nicht.

**Die eigentliche Konsequenz** ist deshalb: Ein einzelner Durchgang kann diese Frage gar
nicht entscheiden. Das Urteil wandert in die Gesamtbilanz, wo alle Durchgänge
inversvarianz-gewichtet zusammengefasst werden.

### Was dabei über die Trainingsergebnisse herauskam

Mit dem zweiten neuen Maß — dem Vorsprung des Siegers auf den Zweitplatzierten, gepaart
gemessen — steht in der Bilanz jetzt:

| Stellschraube | bester Wert | Vorsprung über dem Rauschen? |
|---|---:|---|
| `confirm_bars` | 2 | **nein** |
| `edge_fraction` | 0,15 | **nein** |
| `min_range_atr` | 10 | **nein** |
| `stop_fraction` | 0,25 | **nein** |
| `take_fraction` | 1,0 | **nein** |
| `time_stop_bars` | 480 | ja (+0,0507 R ± 0,0123) |

**Fünf von sechs „besten Werten" im Trainingslog waren der größte von vier Stichproben.**
Und der eine mit echtem Vorsprung — `time_stop_bars = 480` — fällt durch den Misch-Test
(+0,0817 R ± 0,0601, also 1,4 Standardfehler). Das passt zum Mechanismus: Wer länger hält,
erntet Drift und Volatilität, und die liefert ein gemischter Chart genauso.

**`time_stop_bars` bleibt deshalb bei 240.** Der Wert, der am besten aussah, ist der einzige,
der die Prüfung nicht besteht.
