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

## Was das Journal festhält

| Feld | Warum es drinsteht |
|---|---|
| `gold_price`, `day_high`, `day_low` | Damit später nachvollziehbar ist, auf welche Marktlage sich ein Ergebnis bezieht |
| `price_source` | Woher der Kurs kam. Eine Zahl ohne Herkunft ist keine Zahl |
| `start_equity_eur`, `end_equity_eur` | Die Kette. Der Endstand einer Sitzung ist der Startstand der nächsten |
| `forced_risk_pct` | Das erzwungene Risiko je Trade — siehe oben |
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
