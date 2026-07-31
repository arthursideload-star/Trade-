# Papier-Lauf: 400 € Startkapital, fortlaufend

> **Das Ergebnis an der vorher festgelegten Stichprobe steht in
> [URTEIL.md](./URTEIL.md).** Diese Seite ist die Methodik dahinter.

Eine Kette von Sitzungen auf einem Konto, das mitläuft. Jede Sitzung ist ein Handelstag.
Das Konto startet bei dem Stand, mit dem die vorige Sitzung geendet hat — Gewinn wie
Verlust werden mitgenommen.

```bash
python -m metals paper --price 4114.79 --high 4120.16 --low 4028.77 \
    --spread 0.34 --news "18:00" --source "investing.com 30.07.2026"
python -m metals paper --summary
python -m metals paper --distribution --price 4114.79 \
    --high 4120.16 --low 4028.77
```

`--spread` kommt aus dem beobachteten Ask minus Bid, `--news` aus dem Wirtschaftskalender
(Rule R4 sperrt 30 Minuten um jede genannte Zeit). Ohne `--news` greift die Sperre **nicht**
— das steht dann auch so in der Ausgabe, damit ein durchgehandelter FOMC-Tag nicht
unbemerkt bleibt. Genau das war Auditbefund A7.

Das Journal liegt in `training/paper-ledger.jsonl`, eine Zeile je Sitzung.

> **Wichtig, bevor du eine dieser Zahlen auf den EA überträgst:** Die Tagesspanne-Strategie
> ist inzwischen als Setup „DR" in den EA portiert und per Paritätstest gegen diese Python-
> Implementierung geprüft — aber nur beim **Einstieg**: Der EA steigt anders aus (60 % bei
> 0,5 R, Rest bis 2,5 R statt einem Ziel bei 1,0 R), was rund 20 % des Erwartungswerts
> kostet ([A11](./REPO-AUDIT.md)). Er ist **standardmäßig ausgeschaltet**, und **ob die Datei
> kompiliert, konnte hier niemand prüfen**. Ohne `InpUseDayRange = true` handelt der EA die
> Scalping-Setups S2, S4 und S5, über die keine Zahl auf dieser Seite etwas sagt. Siehe
> [REPO-AUDIT.md, A10](./REPO-AUDIT.md).

## Was hier echt ist und was nicht

Das ist die wichtigste Seite dieses Dokuments, und sie steht deshalb vorn.

**Echt:**

- Der **Goldkurs**, vor jeder Sitzung nachgeschlagen. Der simulierte Markt startet genau
  dort.
- Die **Tagesspanne**. Die Volatilität des Marktes wird so kalibriert, dass seine
  Tagesspanne der echten entspricht — ein ruhiger und ein wilder Tag erzeugen dadurch
  wirklich verschiedene Märkte, nicht denselben Generator mit anderem Startpreis.
- Die gesamte **Kostenrechnung**: Margin, was 0,01 Lot gegen dieses Konto riskiert, wie
  viel Prozent des Kontos ein Stop ist. Alles aus dem tatsächlichen Kurs gerechnet.

**Nicht echt:**

- Der **Verlauf innerhalb des Tages**. Diese Umgebung kommt an keinen Intraday-Kursfeed —
  die Anbieter antworten durch den Proxy mit 403. Die Minutenkerzen sind erzeugt.

Daraus folgt, was ein Ergebnis wert ist: Es ist **keine Prognose**. Es ist, was diese
Regeln an *einem* Tag getan hätten, der sich so weit bewegt hat wie der heutige. Eine
Kette solcher Tage beantwortet die Frage „ist diese Kontogröße durchzuhalten" deutlich
besser als die Frage „verdient das Geld".

Die Kalibrierung trifft die Zielspanne auf etwa ±20 %. Sie rät nicht: sie startet mit der
Random-Walk-Formel, die rund 18 % zu niedrig liegt, weil der Generator zusätzlich
Sessionprofil, Mean-Reversion und Sprünge enthält — und korrigiert dann gegen das, was der
Generator tatsächlich produziert.

## Die Positionsgröße bricht die Regel, und das steht in jedem Eintrag

Regel R1 erlaubt 1 % Risiko je Trade. Auf einem 400-€-Konto ist die kleinste Goldposition,
die es gibt — 0,01 Lot = eine Unze — bei einem typischen Stop von rund 30 $ schon bei
**etwa 6 bis 7 %**.

Der Bot handelt hier trotzdem, weil das ist, was ein 400-€-Konto in der Realität tut. Aber
`forced_risk_pct` steht in jeder Zeile des Journals und in jeder Ausgabe, und es ist die
erste Zahl, die man lesen sollte. Wer die Rendite ohne diese Zahl liest, liest die Hälfte.

Rechnerisch: unter etwa **190 €** kann gar nicht gehandelt werden, weil 0,01 Lot bei 1:20
rund 205 $ Margin bindet. Ab etwa **2.850 €** wäre die 1-%-Regel eingehalten. Alles
dazwischen ist der Bereich, in dem das Konto handeln kann, aber über Limit.

Die vollständige Rechnung dazu: [KONTOGROESSE.md](./KONTOGROESSE.md).

## Der Einsatz schwankt um das Zehnfache — und das ist die eigentliche Gefahr

Bei fester Losgröße (0,01 Lot) ist der riskierte Betrag **nicht** gesteuert. Er ist,
wie groß die vorhergesagte Bewegung zufällig war. Gemessen in Sitzung 2:

| | Ziel-Abstand | Risiko am Konto |
|---|---:|---:|
| kleinster Trade | 8,59 $ | **1,9 %** |
| größter Trade | 84,51 $ | **18,2 %** |

Faktor **9,8** zwischen dem kleinsten und dem größten Einsatz, in einer einzigen Sitzung.

Was das anrichtet, zeigt dieselbe Sitzung: acht Trades, fünf gewonnen, Erwartungswert
**+0,064 R** — also praktisch null. Das Konto stieg trotzdem um **+16,5 %**, weil die
Gewinner zufällig die großen Trades waren und die Verlierer die kleinen. Bei umgekehrten
Vorzeichen wäre dieselbe Trefferquote ein Minus von ähnlicher Größe gewesen.

**Ein Ergebnis, das davon abhängt, *welche* Trades gewonnen haben statt *wie viele*, ist
kein Ergebnis.** Genau das verhindert die risikobasierte Positionsgröße (`--risk 1`): dort
ist jeder Einsatz gleich groß, und dann misst die Rendite tatsächlich die Trefferquote.

Deshalb steht in jeder Sitzung nicht nur der Mittelwert, sondern die Spanne, und ab Faktor
3 warnt die Ausgabe ausdrücklich.

## Der dritte Weg: Setups ablehnen statt Position verkleinern

Unter 0,01 Lot geht nichts mehr — die Position lässt sich nicht weiter verkleinern. Der
einzige Hebel, der bleibt, ist **welche Setups man annimmt**. `max_risk_pct` lehnt ein
Signal ab, wenn selbst die kleinste Position zu viel riskieren würde.

Gemessen auf 400 €, 30 Märkte à einem Handelstag:

| Deckel | Trades | abgelehnt | Median | schlechtester Markt | Erwartung je Trade |
|---:|---:|---:|---:|---:|---:|
| keiner | 8,4 | 0 | +6,89 % | **−14,07 %** | +0,218 R |
| 10 % | 8,0 | 7,7 | +6,61 % | −10,71 % | +0,216 R |
| 6 % | 7,1 | 22,9 | +4,03 % | −12,68 % | +0,197 R |
| 4 % | 5,0 | 45,7 | +1,85 % | −8,34 % | +0,158 R |
| 2,5 % | 3,0 | 56,9 | +0,31 % | −4,83 % | +0,133 R |

**Ein 10-%-Deckel ist fast umsonst:** kaum weniger Trades, praktisch derselbe
Erwartungswert, aber der schlechteste Markt verbessert sich von −14,1 % auf −10,7 %. Er
kappt die Extremfälle und sonst nichts.

**Enger als das kostet echte Kante.** Und zwar nicht nur Einsatzgröße, sondern Qualität:
der Erwartungswert fällt von +0,218 R auf +0,133 R. Der Grund ist unangenehm logisch — ein
weiter Stop bedeutet eine große vorhergesagte Bewegung, und die gibt es, wenn die
Tagesspanne weit ist und der Kurs am Rand steht. Das ist genau das Setup, für das die
Strategie gebaut wurde. Wer nach Stop-Breite filtert, filtert die guten Signale weg.

Es gibt hier also keine kostenlose Lösung, sondern eine Abwägung. Sie ist als Test
festgehalten, damit sie nicht stillschweigend verschwindet.

## Der größte Hebel auf die Kette ist, welchen Tag sie wiederholt

Die ersten elf Sitzungen liefen auf dem 30. Juli — einem FOMC-Tag mit **2,23 %**
Tagesspanne gegen typische 1,57 %. Das stand bisher als Vorbehalt da. Jetzt ist es
gemessen:

```bash
python -m metals paper --volatility --price 4086.21 --equity 1600
```

| Tagesspanne | Median | Mittel | Tage im Plus |
|---:|---:|---:|---:|
| 0,6 % | +0,25 % | +0,25 % | 60 % |
| 0,9 % | +0,63 % | +0,42 % | 62 % |
| 1,2 % | +1,07 % | +1,07 % | 80 % |
| 1,6 % | +0,71 % | +0,79 % | 62 % |
| 2,0 % | +1,10 % | +1,41 % | 68 % |
| 2,6 % | +2,03 % | +2,25 % | 75 % |
| 3,2 % | **+4,37 %** | +4,15 % | 88 % |

**Die Spanne wächst um das 5,3-fache, der Median um das 17,5-fache.**

Das ist die entscheidende Beobachtung, und sie ist schärfer als „der Simulator ist zu
leicht": Der Ertrag wächst **schneller** als die Volatilität. Das ist die Signatur einer
Strategie, die **Spanne erntet** — sie kauft am Rand der Tagesspanne und verkauft in
Richtung Mitte. In einem Generator, der innerhalb des Tages zur Mitte zurückkehrt, ist
das ein zuverlässiges Geschäft. Echtes Gold kehrt nicht auf Bestellung zurück; an einem
Trendtag läuft es durch und der Stop greift.

Praktische Folge für jede Zahl auf dieser Seite: **Welchen Tag die Kette wiederholt, ist
keine Nebensache, sondern der größte einzelne Hebel auf das Ergebnis.** Die Sitzungen 37
bis 39 liefen auf einem ruhigen Tag (1,01 %) und gingen alle drei ins Minus — dieselbe
Strategie, dieselben Regeln, nur ein anderer Tag.

## Die aufgezeichnete Kette ist eine glückliche

Die Kette ist **ein** Pfad. Wie viel davon sind die Regeln, wie viel die konkrete
Marktfolge? Das lässt sich direkt messen: dieselben Sitzungen, dieselbe Kalibrierung,
dieselbe Reihenfolge — nur andere Märkte.

```bash
python -m metals paper --replay --runs 25
```

Nach 46 Sitzungen, 25-mal nachgespielt:

| | |
|---|---:|
| **Tatsächlich** | **1.666,34 €** |
| Median der Wiederholungen | **1.293,76 €** |
| schlechteste | 575,24 € |
| beste | 1.888,10 € |
| Läufe unter dem Startkapital | 0 % |

**Der aufgezeichnete Lauf liegt auf dem 92. Perzentil.** Er gehört also zu den besten 8 %
dessen, was diese Regeln an diesen Tagen produzieren. Der typische Ausgang wäre rund
**1.294 €** gewesen, der schlechteste **575 €** — bei identischen Regeln, identischen Tagen,
identischer Reihenfolge.

Das ist keine Korrektur nach unten aus Bescheidenheit, sondern eine Messung: Wer die
Kurve ansieht, sieht einen überdurchschnittlichen Zufallspfad und hält ihn für das
Verfahren. **Rund ein Drittel des Endstands ist Glück in der Reihenfolge.**

Warum das gerade beim Zinseszins so stark durchschlägt: Ein schlechter Tag früh verkleinert
jede Position danach. Zwei Ketten mit derselben Trefferquote können deshalb weit
auseinanderlaufen, je nachdem *wann* die Verluste kamen. Genau das misst dieser Test und
eine Verteilung unabhängiger Einzeltage nicht.

Die letzte Zeile gehört auch dazu: **kein einziger von 25 Läufen endete unter 400 €.** Auf
diesem Simulator verliert die Strategie praktisch nie — was erneut mehr über den Simulator
sagt als über die Strategie.

## Was eine Siegesserie wert ist: nichts

Nach drei Sitzungen stand die Kette bei 400 → 544 €, alle drei im Plus. Bevor daraus
irgendein Schluss wird, die Gegenprobe — 60 **unabhängige** Handelstage, jeder wieder ab
400 €:

```bash
python -m metals paper --distribution --price 4114.23 --high 4120.16 --low 4028.77
```

| | |
|---|---:|
| Median | **+7,74 %** |
| Mittelwert | +8,35 % |
| Streuung | 10,69 Punkte |
| beste 5 % | +26,18 % |
| schlechteste 5 % | −6,30 % |
| schlechtester Tag | **−19,32 %** |
| Tage im Plus | **78 %** |

Bei 78 % Gewinntagen haben **drei Gewinntage in Folge eine Wahrscheinlichkeit von 48 %**.
Die Serie ist also der Normalfall, kein Signal. Genau dafür gibt es diese Rechnung.

### Und die Zahl selbst ist das eigentliche Warnsignal

Ein Median von +7,74 % pro Tag verdoppelt ein Konto in **neun Tagen**. Das tut niemand.
Aus 400 € wären in einem Monat über 3.000 €, in einem Jahr eine Zahl mit acht Stellen.

Die richtige Schlussfolgerung daraus ist **nicht**, dass der Bot eine Geldmaschine ist,
sondern dass **der Simulator zu leicht ist**. Er wurde mit Struktur gebaut — Volatilitäts-
cluster, Rundzahlen-Magnetismus, Liquiditätsjagden — und die Strategie findet genau diese
Struktur. Der Misch-Test bestätigt das von der anderen Seite: zerstört man die Reihenfolge
der Kerzen, bleiben nur 26 % der Kante übrig. Die Strategie liest also wirklich den Chart —
nur eben einen Chart, der leichter zu lesen ist als der echte.

Was diese Verteilung belastbar sagt, ist deshalb die **Streuung**, nicht der Ertrag: dass
ein Tag zwischen −19 % und +26 % liegen kann, wenn 0,01 Lot auf 400 € 1,4 % bis 18 % je
Trade riskiert. Das ist die Erfahrung, auf die man sich einstellen muss — der Ertrag
entscheidet sich erst am echten Backtest.

### Der Gegenbeweis kam in Sitzung 4

Sitzung 2: **+16,5 % Rendite** bei **+0,064 R** Erwartungswert — Konto gewann, Regeln liefen
mittelmäßig.
Sitzung 4: **−2,5 % Rendite** bei **+0,050 R** Erwartungswert — Konto verlor, Regeln liefen
gut.

Zweimal derselbe Defekt, einmal in jede Richtung. Erwartungswert und Geld können nur dann
verschiedene Vorzeichen haben, wenn die Einsätze unterschiedlich groß sind. Bei gleich
großen Einsätzen ist positiver Erwartungswert gleich positives Geld — dann ist es
dieselbe Aussage.

Die Sitzung meldet das jetzt ausdrücklich, und die Bilanz zählt, wie oft es passiert ist.

## Die Kursquelle ist das schwächste Glied

Eine einzige Abfrage lieferte drei Preise:

| Quelle | Kurs | was es ist |
|---|---:|---|
| investing.com | 4.114,79 $ | Live-CFD-Quote mit Bid/Ask |
| JM Bullion | 4.047,47 $ | Händler für physisches Gold, Zeitstempel Stunden alt |
| MQL5 | 4.011,13 $ | ausdrücklich als „previous data" markiert |

**2,58 % Unterschied** zwischen der höchsten und der niedrigsten. Wer sich hier
stillschweigend eine aussucht, schreibt möglicherweise einen veralteten Kurs ins Journal,
ohne dass die Wahl später noch nachvollziehbar wäre.

`paper.check_quotes` prüft das — und benutzt dafür `sources.prices.cross_check`, also die
Regel, die im Projekt schon existiert, statt einer zweiten Definition davon:

```python
>>> check_quotes({"investing.com": 4114.79, "jmbullion": 4047.47, "mql5": 4011.13})
(False, 'sources disagree by 2.58% (...). ... usually means one feed is stale ...')
```

Für den Papier-Lauf wird die **CFD-Quote** genommen, weil sie das ist, was ein CFD-Konto
tatsächlich bezahlt — und die Uneinigkeit landet im `price_source`-Feld, damit sie im
Journal sichtbar bleibt.

## Eine Vereinfachung, die geprüft wurde — und ein Bug, den sie aufdeckte

Jede Sitzung ist ein **eigenständiger Tag**. Eine Position, die bei Bar 1.440 noch offen
ist, wird zum letzten Kurs geschlossen — die nächste Sitzung erzeugt einen frischen Markt
und setzt sie nicht fort. Das Konto läuft weiter, die Position nicht.

Beim Nachmessen fiel ein Fehler auf: Diese künstlich geschlossenen Trades wurden als Trade
gezählt und in die Trefferquote aufgenommen, **landeten aber nicht in `r_multiples`**. Der
Erwartungswert war damit ein Mittel über eine Teilmenge, ausgegeben, als deckte er alles ab.
Behoben; ein Test prüft jetzt `len(r_multiples) == trades`.

Die korrigierte Messung über 60 Tage:

| Ausstiegsart | Anteil | Erwartungswert |
|---|---:|---:|
| regulär (Ziel, Stop, Zeitstop) | 93,3 % | +0,094 R |
| Tagesende, künstlich geschlossen | 6,7 % | **+0,038 R** |
| zusammen | | +0,090 R |

Die künstlichen Ausstiege sind also **deutlich schlechter** als die regulären — nicht
gleichwertig, wie eine frühere Fassung dieses Abschnitts behauptet hat. Diese Zahlen waren
falsch, weil sie mit dem Bug gemessen wurden: Sie verglichen die letzten regulär
geschlossenen Trades mit sich selbst.

Weil es nur 6,7 % der Trades sind, bleibt die Wirkung aufs Ganze klein (+0,094 → +0,090 R,
also −4 %). Ein Test hält den Anteil unter 25 %: Würde ein Viertel der Trades von der Uhr
statt von den Regeln beendet, würde die Sitzung die Serienlänge messen und nicht die
Strategie.

## Was 100 Trades belegen — und was nicht

```bash
python -m metals paper --evidence
```

Nach elf Sitzungen: Konto **+87 %**. Und die Trades dazu:

| | | |
|---|---:|---|
| Trefferquote | 57,0 % | 95%-Band 47 bis 66 % |
| Erwartungswert | +0,131 R | **95%-Band −0,043 bis +0,305 R** |
| Streuung | 0,888 R | |

**Das Band schließt die Null ein.** Beide Aussagen stimmen gleichzeitig: Das Konto ist um
87 % gestiegen, und die 100 Trades belegen keinen Vorteil. Sie schließen ihn auch nicht aus
— die Stichprobe reicht schlicht nicht.

Für einen Nachweis **dieser** Kantengröße bräuchte es rund 155 Trades — also fast geschafft.
Nur ist genau das die Falle: Die Zahl folgt aus dem **beobachteten** Mittelwert, und der ist
nach oben verzerrt. Ein Lauf, der gut lief, lässt den Nachweis fast fertig aussehen.

Rechnet man stattdessen mit einem nüchternen Vorteil von **+0,10 R** — dem Referenzwert, den
`metals.journal` aus demselben Grund verwendet —, sind es **309 Trades**, also etwa 22
weitere Sitzungen statt vier. Und das gälte dann für den Simulator, nicht für echtes Gold.

Die Auswertung benutzt `metals.journal` — dieselbe Statistik, mit der das Journal des EA
gelesen wird. Ein eigener Maßstab für den Papier-Lauf hieße, die Probe milder zu bewerten
als den Ernstfall.

## Welchen Tag die Kette wiederholt hat — die wichtigste Einschränkung

Alle bisherigen Sitzungen wurden auf den **30. Juli** kalibriert, und das war ein
**FOMC-Tag** mit einer Tagesspanne von 2,23 %.

Wie typisch ist das? Aus der beobachteten Wochenspanne abgeleitet, nicht geraten:
143,97 $ über fünf Handelstage bei rund 4.103 $. Für einen Random Walk skaliert die
Spanne über n Tage mit √n, also ist ein Tag 143,97/√5 = **64,39 $ = 1,57 %**.

Der 30. Juli lag damit beim **1,42-fachen** eines normalen Tages. Gemessen, 25 Läufe je
Einstellung:

| Tagesspanne | Median je Sitzung | Tage im Plus |
|---|---:|---:|
| 91,39 $ (30.07., FOMC) | **+9,35 %** | 72 % |
| 64,39 $ (typisch, abgeleitet) | +7,39 % | 80 % |
| 32,19 $ (halb so volatil) | +1,41 % | 68 % |

Die Kette ist also um rund **ein Viertel zu optimistisch** kalibriert — nicht dramatisch,
aber systematisch, weil derselbe wide Tag zwölf Mal wiederholt wurde. Bei halber
Volatilität bricht das Ergebnis dagegen deutlich ein: Die Strategie lebt von großen
Tagesspannen, weil sie ihre Ziele daraus ableitet.

Jede Sitzung warnt jetzt, wenn ihre Spanne mehr als 35 % vom typischen Wert abweicht — in
beide Richtungen. Eine Sitzung, die einen Ausnahmetag beschreibt, soll nicht wie der
Normalfall aussehen.

**Und selbst bei typischer Volatilität bleibt +7,39 % pro Tag absurd.** Das führt zurück
auf denselben Punkt wie oben: Nicht die Kalibrierung ist das Hauptproblem, sondern dass der
Simulator die Struktur enthält, die die Strategie sucht.

## Als das Band die Null verließ — und warum das noch kein Befund ist

Bei 155 Trades stand da zum ersten Mal:

```
Erwartungswert    +0.176 R   95%-Band +0.035 bis +0.316 R
```

Das Band liegt über der Null. Verlockend — und genau hier ist Vorsicht am wichtigsten,
nicht am wenigsten.

**Ich hatte die Auswertung schon bei 100, 116, 134 und 155 Trades angesehen.** Wer eine
wachsende Stichprobe wiederholt prüft und glaubt, sobald sie gut aussieht, hat kein
95-%-Band mehr. Bei 18 Gelegenheiten liegt die Chance, dass irgendwann eines zufällig über
der Null steht, bei bis zu **60 %** — nicht bei 5 %.

Das ist dieselbe Rechnung, mit der `metals/journal.py` vor Aufschlüsselungen nach Setup und
Session warnt (`multiple_comparison_risk`), nur angewandt auf die Zeitachse statt auf
Kategorien.

**Das Gegenmittel ist Vorfestlegung.** Die Zahl steht bereits fest: **307 Trades** für einen
nüchternen Vorteil von +0,10 R, also noch rund 18 Sitzungen. Erst dann ist ein Urteil eines.
Die Auswertung sagt das jetzt an genau der Stelle, an der die Nachricht gut ist.

## Der Weg zu echten Daten — jetzt für beide Strategien

Bis eben konnte nur die **Scalping-Engine (S1–S6)** eine heruntergeladene Datei lesen. Wer
mit `XAU_5m_data.csv` am PC ankam, hätte also eine Strategie backtesten können, nach der er
nie gefragt hat — und die Tagesspanne-Strategie, um die es hier geht, gar nicht.

Das geht jetzt:

```bash
python -m metals dayrange --file XAU_5m_data.csv --tz broker_gmt3 \
    --equity 1000 --risk 1
```

Zwei Dinge nimmt der Befehl dabei ernst:

- **`--tz` ist Pflicht, ohne Vorgabe.** Eine falsche Zeitzone verschiebt jede Session-Regel,
  und an den Zahlen fällt es nicht auf. Kaggle und MetaTrader-Exporte liefern Brokerzeit
  (`broker_gmt3` im Sommer, `broker_gmt2` im Winter), Dukascopy und Twelve Data liefern UTC.
- **Bar-gezählte Parameter werden skaliert.** 1.440 Bars sind auf M1 ein Tag und auf M5 eine
  Woche. Ohne Umrechnung würde aus „die Tagesspanne" stillschweigend „die Wochenspanne".
  Der Befehl sagt an, wenn er teilt.

Der Bericht für einen einzelnen Lauf ist bewusst von dem für viele Märkte getrennt: Eine
echte Historie ist **eine** Stichprobe und wird auch als eine ausgewiesen — mit 95 %-Band
und der Angabe, wie viele Trades ein Nachweis bräuchte.

## Sind 174 Trades wirklich 174 Beobachtungen?

Jedes Band in dieser Auswertung behandelt die Trades als unabhängige Ziehungen. Trades
derselben Sitzung teilen aber denselben Markt — wenn sie sich dadurch ähneln, ist die
effektive Stichprobe kleiner als die Anzahl und das Band zu schmal.

Also gemessen statt angenommen, per einfacher Varianzanalyse über 20 Sitzungen:

| | |
|---|---:|
| Streuung **zwischen** Sitzungen | 0,4016 |
| Streuung **innerhalb** einer Sitzung | 0,8487 |
| Intraklassenkorrelation | **0,00** |
| Design-Effekt | **1,00** |

Die Streuung zwischen Sitzungen ist sogar **kleiner** als die innerhalb — Sitzungen sind
also nicht voneinander unterscheidbar. Effektive Stichprobe: 174 von 174. Das Band darf so
stehen bleiben.

Der Grund ist derselbe Mechanismus wie bei Behauptung C3: **R-Vielfache sind durch ihren
eigenen Stop normiert**, also kürzt sich die Volatilität eines Tages weitgehend heraus. Was
den Session-Filter nutzlos machte, macht hier die Stichprobe sauber.

Die Auswertung prüft das jetzt bei jedem Aufruf und warnt, falls der Effekt je über 1,2
steigt.

## Das Journal lässt sich nachrechnen

```bash
python -m metals paper --verify
```

Jede Zeile speichert alles, was die Sitzung verbraucht hat: Goldkurs, Tagesspanne, Kosten,
Sperrzeiten, Startkapital. Damit lässt sich die ganze Kette neu abspielen und gegen das
prüfen, was sie behauptet — drei Dinge auf einmal:

1. Jede Sitzung beginnt dort, wo die vorige endete.
2. Der Endstand folgt aus den Eingaben.
3. Die Tradezahl stimmt.

Stand: **25 Sitzungen, keine Abweichung.**

Das ist hier wichtiger als anderswo, denn **das Journal wurde zweimal nachträglich ergänzt** —
einmal um die Spanne des Risikos je Trade, einmal nach dem `r_multiples`-Bug. Genau so eine
Ergänzung ist die Operation, die Geschichte still in etwas umschreiben kann, das aus seinen
Eingaben nicht mehr folgt. Ein Journal, das niemand nachrechnen kann, ist eine Behauptung.

## Warum die Schlagzeile größer ist als die Leistung

Das Lot steht fest bei 0,01, und der Kurs ist über die ganze Kette derselbe. Also **kann**
der Gewinn einer Sitzung in Euro gar nicht davon abhängen, wie viel auf dem Konto liegt. Was
sich ändert, ist nur der Nenner.

Gemessen, erste neun Sitzungen gegen die letzten neun:

| | erste 9 | letzte 9 | Faktor | erwartet |
|---|---:|---:|---:|---:|
| Konto | 538 € | 1.114 € | ×2,07 | — |
| Bewegung in Euro | 47,64 € | 42,82 € | **×0,90** | ×1,00 |
| Bewegung in Prozent | 9,22 % | 3,86 % | **×0,42** | ×0,48 |

Genau die Signatur eines festen Lots. Der absolute Betrag bleibt flach, die Prozentzahl fällt
im Kehrwert des Kontostands.

**Daraus folgt, wie die Gesamtzahl zu lesen ist:** Der größte Teil einer aufaddierten
Prozentrendite stammt aus den Sitzungen, in denen das Konto am kleinsten war — nicht daraus,
dass die Strategie besser geworden wäre. Dieselben Euro auf dem heutigen Kontostand wären
weniger als die Hälfte der Prozentzahl gewesen.

Ein Test prüft das in beide Richtungen. Er würde anschlagen, wenn die Positionsgröße
irgendwann anfinge, mit dem Konto mitzuwachsen — und er hält gleichzeitig die Rechnung fest,
die die Schlagzeile relativiert.

## Der gemeldete Rückgang war zu freundlich

Die Bilanz meldete lange „größter Rückgang vom Hoch: 8,0 %". Das ist von **Sitzungsende zu
Sitzungsende** gerechnet und sieht damit nichts von dem, was innerhalb eines Tages passiert.

Der Gleitwert des Kontos wurde ohnehin jedes Bar berechnet — für die Stop-out-Prüfung — und
danach weggeworfen. Jetzt wird er festgehalten:

| | |
|---|---:|
| Rückgang Schluss zu Schluss | 8,0 % |
| Rückgang **innerhalb einer Sitzung** | **23,1 %** |

Fast das Dreifache. Und der Unterschied ist nicht nur Darstellung: **Ein Margin Call reagiert
auf den Gleitwert, nicht auf den Schlusskurs.** Wer bei 8 % Rückgang ruhig bleibt, hat unter
Umständen 23 % ausgehalten, ohne es zu wissen.

Der aussagekräftigste Fall ist eine Sitzung, die **im Plus endet und unterwegs tief im Minus
stand** — etwa +5,72 % Schlussergebnis bei 7,12 % Rückgang zwischendurch. Genau diese
Sitzungen macht eine Schluss-zu-Schluss-Rechnung unsichtbar, und genau sie entscheiden, ob
jemand die Strategie durchhält.

Jede Sitzung meldet ihren Wert jetzt einzeln, die Bilanz beide nebeneinander mit Etikett.

## Der Lauf lehnt jetzt zwei Arten von Sitzung ab

Aus der Herkunftsrechnung folgten zwei Schranken, und beide sind im Kommando, nicht nur im
Text.

**1. Ein Handelstag, der schon zehn oder mehr Sitzungen trägt**

```
UEBERSAMPELT: Dieser Handelstag (4,028.77-4,120.16, 2.22 % Spanne) traegt
schon 20 Sitzungen. Eine weitere vergroessert die Schieflage, statt etwas
zu messen.
```

Der Schlüssel ist das **Hoch/Tief-Paar**, nicht die Spanne in Prozent. Das war ein Fehler:
Derselbe Tag, bei einem anderen Spotkurs abgefragt, ergab einen anderen Prozentwert und wäre
durchgerutscht. Genauso wurden drei verschiedene angesetzte Bilder zu einem verschmolzen.

**2. Eine Sitzung auf einer hergeleiteten Tagesspanne**

```
ANGESETZTE SPANNE: Diese Sitzung wuerde auf einer hergeleiteten Tagesspanne
laufen, nicht auf einer beobachteten. 56 % des bisherigen Kettengewinns
stehen bereits auf solchen Zeilen.
```

Beides mit `--force` überschreibbar, aber dann bewusst.

### Und der Status wird protokolliert, nicht geraten

`range_observed` steht jetzt in jeder Zeile. Vorher wurde „angesetzt" aus der Zahl
**erschlossen** (`|Spanne − 1,57 %| < 0,02`). Das ist in zwei Fällen falsch:

- Ein echter Handelstag, dessen Spanne zufällig typisch ist, würde als angesetzt geführt.
- Würde die typische Spanne je neu berechnet, änderten **alle** historischen Zeilen
  rückwirkend ihre Bedeutung.

Die 54 Sitzungen von vorher haben das Feld nicht und werden weiter über die alte Heuristik
gelesen — sie als beobachtet zu zählen, würde genau den Befund löschen, den sie erzeugt haben.

## Was das Journal festhält

| Feld | Warum es drinsteht |
|---|---|
| `gold_price`, `day_high`, `day_low` | Damit später nachvollziehbar ist, auf welche Marktlage sich ein Ergebnis bezieht |
| `price_source` | Woher der Kurs kam. Eine Zahl ohne Herkunft ist keine Zahl |
| `start_equity_eur`, `end_equity_eur` | Die Kette. Der Endstand einer Sitzung ist der Startstand der nächsten |
| `forced_risk_pct` | Das erzwungene Risiko je Trade im Mittel — siehe oben |
| `risk_pct_min`, `risk_pct_max` | Die Spanne der Einsätze. Wichtiger als der Mittelwert |
| `trades`, `wins`, `losses`, `exits` | Damit eine gute Sitzung von einer glücklichen unterschieden werden kann |
| `expectancy_r` | Der Erwartungswert je Trade, unabhängig von der Kontogröße |
| `could_not_trade` | Wenn die Margin nicht reichte. Eine Sitzung ohne Trade ist ein Ergebnis, kein Fehler |
| `stopped_out` | Broker-Stop-out |
| `intraday_drawdown_pct` | Größter Rückgang vom Hoch **innerhalb** der Sitzung. Der Schluss-zu-Schluss-Wert unterschätzt ihn um fast das Dreifache |
| `r_multiples` | Jeder Trade einzeln in R. Aus einem Sitzungsmittel lässt sich kein Konfidenzintervall zurückrechnen |
| `slippage_fraction` | Welches Kostenmodell galt. Sitzungen 1–9 liefen mit 0,0, ab 10 mit der Backtest-Konvention 0,5 |
| `news_times_utc` | Für welche Veröffentlichungen die Sitzung stillhielt. Leer heißt: R4 war aus |

Jede Sitzung handelt auf einem Markt mit einem Seed, den keine frühere benutzt hat. Die
Seeds für die Volatilitätskalibrierung sind davon getrennt — kein Markt wird auf denselben
Daten gemessen, mit denen er eingestellt wurde.

## Wie das zu lesen ist

Prozentzahlen auf einem kleinen Konto sind groß. **+7,5 % auf 400 € sind 30 €.** Dieselben
30 € wären auf 10.000 € ein Plus von 0,3 %. Der Bot war nicht besser, das Konto war
kleiner — dieselbe Rechnung wie in [KONTOGROESSE.md](./KONTOGROESSE.md), und sie gilt hier
bei jeder einzelnen Zeile.

Unter zwanzig Sitzungen sagt die Zusammenfassung ausdrücklich, dass es eine Anekdote ist.
Das ist keine Bescheidenheitsfloskel: bei sieben Trades pro Tag braucht ein Nachweis eines
0,1-R-Vorteils rund 385 Trades, also etwa 55 Sitzungen — und das nur, wenn die Daten echt
wären, was sie hier nicht sind.
