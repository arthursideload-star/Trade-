# Die Regeln

Sie stehen **im Code**, nicht in einer Einstellung. Eine zu ändern kostet einen Commit —
das ist Absicht, damit sie nicht im Eifer des Gefechts verschoben wird.

Vollständig und immer aktuell: `python -m metals rules`

## Die harten Grenzen

| | Regel |
|---|---|
| **R1** | Nie mehr als **1 %** des Kontos je Trade riskieren |
| **R2** | Bei **−3 %** am Tag ist Schluss bis zur nächsten Sitzung |
| **R2b** | Bei **+2 %** am Tag auch — [[Warum R2b nur für Menschen gilt]] |
| **R3** | Mindestens 1:2 Chance/Risiko, gemessen bis zum ersten Ziel |
| **R4** | Kein Einstieg 30 Minuten um eine hochwirksame Veröffentlichung |
| **R5** | Kein Einstieg bei Rollover, tiefer Asienzeit, Freitagabend |
| **R6** | Größe **nie** nach einem Verlust erhöhen. Kein Martingale, kein Grid |
| **R6b** | Höchstens 2 Positionen gleichzeitig |
| **R7** | Jeder Trade hat eine definierte Invalidierung, **bevor** er eröffnet wird |
| **R8** | Der Stop kommt aus der Struktur, die Größe folgt dem Stop. Nie umgekehrt |
| **M1** | Stop nie enger als 1,0× ATR(14) |
| **M2** | Stops liegen 0,25× ATR **jenseits** des Levels, nie darauf |
| **M3** | Kein Einstieg, wenn der Spread über 15 % des ATR liegt |
| **M4** | Gold und Silber teilen sich **ein** Risikobudget von 1,5 % |
| **M5** | Freitag 19:00 UTC flat. Ein Stop schützt nicht gegen ein Wochenend-Gap |
| **M6** | Stops nicht auf runden Zahlen parken |

## Die drei, bei denen die meisten scheitern

**R1 auf einem kleinen Konto.** 0,01 Lot ist die kleinste Goldposition, die es gibt — eine
Unze. Bei einem typischen Stop von 30 $ riskiert sie auf 400 € rund **7 %**. Der Bot handelt
trotzdem, aber er **schreibt das erzwungene Risiko in jede Zeile**. Wer die Rendite ohne
diese Zahl liest, liest die Hälfte.

**R4 und R5 sind kein Zaudern, sondern Rechnen.**
[[Was der Spread zum falschen Zeitpunkt kostet]]

**R7 ist die einzige, die nie verhandelbar ist.** Ohne Invalidierung ist es keine Idee,
sondern eine Hoffnung.

## Was passiert, wenn du eine brichst

Nichts. Der Code kann dich nicht daran hindern, in MT5 selbst zu klicken.

Deshalb gehört ein Regelbruch in die Tagesnotiz — und ein Regelbruch, der **gewonnen** hat,
ganz besonders. Er ist der gefährlichste Eintrag im ganzen Journal, weil er schlechtes
Verhalten belohnt.

Siehe auch: [[Die Hauptstrategie]] · [[START HIER]]
