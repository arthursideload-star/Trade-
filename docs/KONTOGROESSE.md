# Der Bot mit 100, 200 und 400 € — die Messung

Gemessen am 29.07.2026 mit `metals/claims.py`, 20 unabhängige Marktläufe je Kontogröße,
je 15.000 Bars. Strategie: die Tagesspanne-Taktik, die du vorgegeben hast — Bewegung
vorhersagen, bei der Hälfte schließen, Stop auf der Gegenseite.

Reproduzierbar mit:

```bash
python -m metals claims --measure
python -m metals dayrange --equity 432 --risk 1
```

## Die eine Zahl, aus der alles folgt

Die kleinste Position, die ein Broker auf Gold zulässt, ist **0,01 Lot = eine Unze**.
Der typische Stop dieser Strategie liegt bei **30,77 $/oz**.

Also riskiert die kleinste überhaupt handelbare Position rund **31 $** — und daran ändert
die Kontogröße nichts. Was sich ändert, ist nur, **welcher Anteil deines Kontos das ist**:

| Konto | erzwungenes Risiko je Trade | Verluste in Folge bis Null |
|---:|---:|---:|
| 100 € | **28,5 %** | 3,5 |
| 200 € | **14,2 %** | 7,0 |
| 400 € | **7,1 %** | 14,0 |
| 1.000 € | 2,8 % | 35,1 |
| 2.000 € | 1,4 % | 70 |
| **2.849 €** | **1,0 %** ← hier greift die Regel | 100 |

Die 1-%-Regel (R1) ist nicht Vorsicht, sondern die Grenze, ab der eine Pechsträhne kein
Totalverlust ist. Bei 400 € ist der Bot zu **7,1 % je Trade** gezwungen, nicht weil die
Strategie das will, sondern weil es keine kleinere Goldposition gibt.

## Was passiert, wenn man die Regel einhält

Der Bot lehnt dann die Trades ab, die nicht hineinpassen:

| Konto | Trades je Markt | Anteil der Signale, die er nutzen darf |
|---:|---:|---:|
| 100 € | 0 | 0 % |
| 200 € | 0 | 0 % |
| 400 € | 0,8 | 0,09 % |
| 1.000 € | 2,9 | 0,32 % |
| 2.000 € | 13,3 | 1,9 % |
| 3.000 € | 38,1 | 11,6 % |
| 5.000 € | 52,2 | 72,9 % |
| 10.000 € | 53,3 | 100 % |

Bei 100 € und 200 € handelt er **überhaupt nicht**. Bei 400 € nimmt er weniger als jedes
tausendste Signal — das ist kein laufender Bot, das ist ein ausgeschalteter.

**Achtung bei genau dieser Tabelle:** Wer nur die 400-€-Zeile ansieht, findet dort
gelegentlich „ein Trade, 100 % Trefferquote". Das ist die Trefferquote auf dem einen
Trade, den das Konto sich leisten konnte. Der Bericht zeigt deshalb seit dem Audit die
abgelehnten Signale **vor** der Trefferquote.

## Was passiert, wenn man die Regel bricht

Das ist, was ein kleines Konto tatsächlich tut: 0,01 Lot handeln, weil der Broker es
erlaubt. Gleiche Märkte, gleiche Signale:

| Konto | Trades | Rendite im Median | schlechtester Markt | Konto leer |
|---:|---:|---:|---:|---:|
| 100 € | 0 | — | — | — |
| 200 € | 26 | **−7,9 %** | −24,7 % | 0 von 20 |
| 400 € | 53 | **+44,7 %** | −13,2 % | 0 von 20 |
| 1.000 € | 53 | +17,9 % | −5,3 % | 0 von 20 |
| 2.000 € | 53 | +8,9 % | −2,6 % | 0 von 20 |
| 5.000 € | 53 | +3,6 % | −1,1 % | 0 von 20 |
| 10.000 € | 53 | +1,8 % | −0,5 % | 0 von 20 |

### Lies diese Tabelle bitte genau

**+44,7 % bei 400 € sieht nach dem Fund des Jahrhunderts aus. Es ist dieselbe Handelsfolge
wie die +1,8 % bei 10.000 €.** Exakt dieselben 53 Trades, exakt derselbe Dollarbetrag
Gewinn — nur durch eine kleinere Zahl geteilt. Die Strategie war beim kleinen Konto nicht
besser. Das Konto war kleiner.

Und genauso verhält sich die andere Seite: −13,2 % statt −0,5 % im schlechtesten Markt.
Der Hebel wirkt in beide Richtungen, und das ist kein Sprichwort, sondern hier die
buchstäbliche Rechenoperation.

**100 € kann nicht einmal anfangen.** 0,01 Lot Gold bindet bei 1:20 rund 205 $ Margin,
und 100 € sind 108 $. Es geht nicht um gut oder schlecht — die Position passt nicht ins
Konto.

**200 € ist der unangenehmste Fall.** Es reicht gerade für eine Position, die dann fast
die gesamte freie Margin bindet. Der Bot kann nie eine zweite eröffnen und kommt bei jedem
Gegenwind in die Nähe des Broker-Stop-outs. Ergebnis: nur 26 statt 53 Trades, und ein
Median von **−7,9 %**. Das Konto ist groß genug, um zu handeln, und zu klein, um es
durchzuhalten.

### „0 von 20" heißt nicht „geht nicht kaputt"

In keinem der 20 Läufe war ein Konto am Ende leer. Das Wilson-Intervall für 0 von 20 sagt:
die wahre Ruinquote liegt mit 95 % Sicherheit **irgendwo zwischen 0 % und 16,1 %**. Bei
14 aufeinanderfolgenden Verlusten wäre ein 400-€-Konto weg; bei 7 ein 200-€-Konto. Über
53 Trades ist das nicht wahrscheinlich, und 20 Läufe sind zu wenig, um es auszuschließen.
Ich kann dir nicht sagen, dass es sicher ist. Ich kann dir sagen, dass ich es nicht
gemessen habe.

## Was das für deine 400 € heißt

Drei Wege, alle ehrlich benannt:

**1. Demokonto, 5 Tage, nichts einzahlen.** Der Bot läuft mit 10.000 € Demo-Kapital unter
der 1-%-Regel — so, wie er gebaut ist. Nach der Demo-Phase steht im Journal, was er
tatsächlich getan hat, mit Unsicherheitsband. Das kostet dich null Euro und ist der einzige
Weg, der die offene Frage beantwortet, statt sie zu überspringen.

**2. 400 € einzahlen und 0,01 Lot handeln.** Funktioniert technisch. Bedeutet 7,1 % Risiko
je Trade, also das Siebenfache dessen, was die Regel erlaubt. Die Messung zeigt dafür einen
Median von +44,7 % und einen schlechtesten Markt von −13,2 % — auf **simulierten** Daten,
und das ist ein wichtiges Wort.

**3. Warten, bis mehr Kapital da ist.** Ab etwa **2.850 €** passt die kleinste Position in
die 1-%-Regel, und der Bot handelt so, wie er entworfen wurde.

Was ich dir **nicht** sage: welchen davon du nehmen sollst. Was ich dir sage: Der
Unterschied zwischen Weg 2 und Weg 3 ist kein Unterschied in der Strategie. Es ist
derselbe Bot mit demselben Verhalten, einmal mit 7,1 % und einmal mit 1 % Risiko je Trade.

## Der Vorbehalt, der über allem steht

Diese Zahlen stammen aus `metals/simulate.py`, nicht aus echtem Gold. Der Simulator
reproduziert dokumentierte statistische Eigenschaften — Volatilitätscluster, fette Enden,
Sessionprofil, Liquiditätsjagden — aber **nicht die tatsächliche Kursfolge von Gold**.

Was daraus belastbar ist: die **Arithmetik**. Dass 0,01 Lot rund 31 $ riskiert, dass das
bei 400 € 7,1 % sind, dass 100 € die Margin nicht aufbringt, dass dieselbe Handelsfolge
bei kleinerem Konto prozentual größer aussieht — das gilt für jeden Markt und jeden
Broker.

Was daraus **nicht** belastbar ist: der Median von +44,7 %. Der hängt daran, ob die
Strategie auf echtem Gold eine Kante hat, und das ist bis heute **nicht nachgewiesen**.
Der Backtest auf echter Historie steht noch aus und läuft, sobald Python auf deinem PC
ist:

```bash
python -m metals backtest --source file --file XAU_5m_data.csv --tz broker_gmt3
```
