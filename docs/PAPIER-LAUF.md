# Papier-Lauf: 400 € Startkapital, fortlaufend

Eine Kette von Sitzungen auf einem Konto, das mitläuft. Jede Sitzung ist ein Handelstag.
Das Konto startet bei dem Stand, mit dem die vorige Sitzung geendet hat — Gewinn wie
Verlust werden mitgenommen.

```bash
python -m metals paper --price 4102.83 --high 4120.16 --low 4028.77 \
    --source "WebSearch 30.07.2026"
python -m metals paper --summary
```

Das Journal liegt in `training/paper-ledger.jsonl`, eine Zeile je Sitzung.

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
