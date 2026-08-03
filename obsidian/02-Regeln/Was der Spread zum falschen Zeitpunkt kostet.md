# Was der Spread zum falschen Zeitpunkt kostet

R4 („kein Einstieg um Nachrichten") und R5 („kein Einstieg bei Rollover") klingen nach
Vorsicht. Sie sind **Subtraktion**.

Ein Gold-Scalp riskiert auf seinem Stop etwa **3 $/oz**. Was der Einstieg kostet:

| Wann | Spread | Anteil am 3-$-Stop |
|---|---:|---:|
| London/NY-Überlappung | 0,10–0,25 $/oz | 3–8 % |
| Standardkonto, liquide Zeit | 0,20–0,40 $/oz | 7–13 % |
| **Rollover (~22:00 Serverzeit)** | **~5 $/oz** | **167 %** |
| **Sekunden um NFP / CPI / FOMC** | **~8–15 $/oz** | **270–500 %** |

Bei den unteren beiden Zeilen kostet **allein der Einstieg mehr, als der ganze Trade
riskiert**. Es gibt keinen Einstiegskurs, der das rettet — die Position ist im Minus, bevor
der Markt sich überhaupt bewegt hat.

## Warum kein Backtest das je zeigen konnte

Der Simulator berechnet **einen** Spread für den ganzen Tag. Eine Regel, die die eigene
Messmaschine strukturell nicht begründen kann, hat trotzdem eine Begründung — sie steht nur
nicht in einer Kurve, sondern in dieser Tabelle.

Deshalb liegen die Zahlen in `metals/specs.py` und nicht in einem Fließtext.

## Was du praktisch tust

**Lies den Spread aus MT5 ab, bevor du sizt.** Jede Sitzung neu, nicht aus dem Gedächtnis.
Er entscheidet in einer Tagessitzung über das *Vorzeichen* des Erwartungswerts —
gemessen am 31.07.2026 (`docs/REPO-AUDIT.md`, A19): **+0,1141 R** bei 0,34 $/oz gegen
**−0,0647 R** bei 1,04 $/oz.

Deshalb ist `--spread` im ganzen Projekt **Pflicht** und wird nirgends vorbelegt.

**Quellenart:** Broker-Vergleiche und Broker-Schulungsseiten. Keine akademische Quelle,
keine Messung deines Kontos. Größenordnung, nicht Präzision — dein Broker kann anders sein,
und genau deshalb liest du ab.

Siehe auch: [[START HIER]] · `docs/REPO-AUDIT.md`, A24
