# Kann der Bot aus Fehlern lernen?

Kurz: **Er merkt sich alles. Er stellt sich nicht selbst um.** Das ist keine fehlende
Funktion, sondern eine Entscheidung — und der Rest dieses Dokuments ist die Begründung
dafür, samt der Zahlen, an denen sie hängt.

---

## Die drei Sachen, die „lernen" heißen könnte

| Was gemeint sein kann | Kann das System das? |
|---|---|
| **Aufzeichnen**, was passiert ist — jedes Signal, jede Ablehnung, jeder Ausgang in R | **Ja.** Seit dieser Version, automatisch, in eine CSV |
| **Auswerten**, welche Setups und Sessions wirklich getragen haben | **Ja** — `python -m metals journal`, mit ehrlichen Unsicherheitsbändern |
| **Sich selbst umstellen**, Setups nachgewichten, Parameter nachziehen | **Nein. Bewusst nicht.** |

Die ersten beiden sind der eigentliche Lernvorgang. Der dritte ist der, den man sich
darunter vorstellt — und der bei diesen Datenmengen zuverlässig schadet.

---

## Warum sich der Bot nicht selbst nachjustiert

### Der Grund in einem Satz

Bei den Stichprobengrößen, um die es hier geht, ist Nachjustieren nicht Lernen, sondern
**Rauschen anpassen** — und ein System, das Rauschen anpasst, fühlt sich beim Besserwerden
genauso an wie eins, das wirklich besser wird.

### Der Grund in Zahlen

Der EA teilt in drei Setups (S2, S4, S5) und vier Session-Qualitäten. Dazu Richtung und
Ausstiegsart. Wer die Auswertung aufklappt, sieht schnell **zehn bis zwölf Schubladen**.

Angenommen, **keine einzige** davon hat einen echten Vorteil — alle sind exakt Nullnummern.
Wie hoch ist die Chance, dass trotzdem mindestens eine gut aussieht?

| Schubladen | Chance, dass mindestens eine zufällig gut aussieht |
|---|---|
| 3 | 14 % |
| 4 | 19 % |
| 9 | 37 % |
| 12 | **46 %** |
| 20 | 64 % |

Bei zwölf Auswertungen ist es fast ein Münzwurf, ob eine davon überzeugend aussieht, **ohne
dass irgendetwas daran echt ist.** Ein Automatismus, der die beste Schublade hochgewichtet
und die schlechteste abschaltet, verfolgt genau dieses Zufallsmuster — und weil er es nach
jedem Tag neu tut, verfolgt er jeden Tag ein anderes.

Deshalb: Die Maschine sammelt und rechnet. Was daraus folgt, entscheidet ein Mensch, und die
Änderung kostet einen Commit — dieselbe Hürde, die in diesem Projekt für jedes Risikolimit
gilt.

---

## Was das Journal aufzeichnet

Der EA schreibt nach `MQL5/Files/GoldScalpAssistant.csv`, ab dem ersten Setup, **auch im
Advisor-Modus**. Zwei Arten von Zeilen:

**`signal`** — ein Setup wurde erkannt. Mit Einstieg, Stop, beiden Zielen, ATR, Spread,
Session, Größe. Und: ob es gehandelt wurde, und wenn nicht, **warum nicht**.

**`close`** — eine Position wurde geschlossen. Mit dem Ergebnis in **R** (Geld verdient
geteilt durch Geld riskiert), dem Ausstiegsgrund und der Haltedauer.

Die abgelehnten Signale sind dabei die interessantere Hälfte. Sie zeigen, welches Filter
tatsächlich arbeitet — und ob eines davon alles blockiert. Ein Journal, in dem 40-mal
*„position size below the broker minimum"* steht, sagt: Das Konto ist zu klein für dieses
Instrument. Keine Signaländerung der Welt behebt das.

Lesen:

```bash
python -m metals journal --file GoldScalpAssistant.csv
```

---

## Die Zahl, die alles entscheidet

Ein Handelssystem hat Streuung. Bei M5-Scalping mit Teilausstiegen liegt die
Standardabweichung der Einzelergebnisse grob bei **1 R**. Die Frage „hat das System einen
Vorteil?" heißt statistisch: Ist der Mittelwert von null unterscheidbar?

Dafür braucht man:

| Echter Vorteil pro Trade | Nötige Trades | Bei 4 Trades/Tag |
|---|---|---|
| 0,50 R | 16 | 4 Tage |
| 0,30 R | 43 | 11 Tage |
| 0,20 R | 97 | 24 Tage |
| **0,10 R** | **385** | **96 Handelstage** |
| 0,05 R | 1 537 | 384 Handelstage |

Ein Vorteil von 0,1 R pro Trade wäre für einen Intraday-Scalper nach Kosten schon
**gut**. Der Nachweis dafür dauert rund **fünf Monate**.

Und der Bedarf wächst **quadratisch**: halber Vorteil, vierfacher Aufwand.

### Warum „gestern lief es super" nichts heißt

Acht Gewinner aus acht Trades. Ein sehr guter Abend. Was folgt daraus über die Trefferquote?

Das korrekte 95%-Intervall (Wilson) für 8 aus 8 ist **67,6 % bis 100 %**. Die Untergrenze
liegt bei 68 % — mit anderen Worten: Nach einem perfekten Abend ist eine Trefferquote von
70 % genauso verträglich mit den Daten wie eine von 95 %. Und eine Trefferquote sagt
ohnehin noch nichts über Gewinn, weil sie nichts über die Größe der Gewinne und Verluste
sagt.

Aus den eigenen Backtests dieses Projekts: Eine Variante mit **63 % Trefferquote** hat
trotzdem Geld verloren. Wer die nach vier Trades gesehen hätte, hätte sie für großartig
gehalten.

---

## Was man mit 30 Trades trotzdem schon weiß

Nicht alles braucht hunderte Trades. Ein paar Dinge zeigen sich sofort, und das Journal
prüft genau die:

**Haben die Stops gehalten?** Ein Verlust größer als 1 R ist kein Pech, sondern ein
Prozessfehler — Slippage, ein Gap, ein verschobener Stop. Das Journal listet jeden davon
namentlich. Bei acht Trades ist diese Aussage schon belastbar, weil sie nicht vom Zufall des
Marktes abhängt, sondern von der Mechanik.

**Blockiert ein Filter alles?** Sichtbar ab wenigen Tagen.

**Woran sterben die Trades?** Viele `time_stop` heißen: Der Zeithorizont passt nicht zum
Setup. Viele `stop` direkt nach Einstieg heißen: zu früh eingestiegen. Das sind
Strukturbefunde, keine Erwartungswert-Aussagen — und sie brauchen deshalb weniger Daten.

**Das ist der Teil, der bei diesem Projekt bereits belegt ist:** Regeldisziplin. Korrekte
Größen, haltbare Stops, ein Tageslimit das greift. Das ist wertvoll. Es ist nicht dasselbe
wie eine Kante.

---

## Der Weg, der tatsächlich zu Verbesserung führt

1. **Advisor-Modus laufen lassen.** Er meldet, handelt aber nicht. Das Journal wird zum
   reinen Signalprotokoll.
2. **Selbst mitentscheiden.** Zu jedem Signal notieren, was du getan hättest. Wo du und der
   EA übereinstimmen, ist das ein Argument. Wo nicht, eine Frage.
3. **Nach ein paar Wochen auswerten.** `python -m metals journal`. Nicht die Tabellen nach
   dem besten Setup absuchen — auf die Bänder schauen und darauf, ob sie null einschließen.
4. **Eine Änderung nach der anderen**, jede mit Begründung in
   [ENTSCHEIDUNGEN.md](./ENTSCHEIDUNGEN.md). Wer drei Dinge gleichzeitig ändert, weiß
   hinterher nicht, welches gewirkt hat — und hat die Stichprobe für beide verbraucht.

Der Teil, der wirklich lernt, ist dabei nicht der Code. Es ist der Mensch, der das Journal
liest. Der Code sorgt nur dafür, dass es etwas zu lesen gibt und dass die Zahlen nicht mehr
behaupten, als sie tragen.

---

## Und die Frage nach echtem Geld

Zwei getrennte Hürden. Beide gelten.

### Hürde 1 — Kontogröße. Das ist Arithmetik.

Die kleinste Position bei Gold (0,01 Lot) ist **eine Feinunze**. Ein Stop von 3 USD/oz
kostet damit 3 USD. Bei 55 € sind das **5,5 %** des Kontos. Erlaubt ist 1 % (Regel R1).

```bash
python -m metals minimum XAUUSD --equity 55
```

Für Gold nach den Regeln braucht es **rund 300 USD**. Darunter lehnt der EA jeden Trade ab —
nicht aus Vorsicht, sondern weil die Rechnung nicht aufgeht. Das lässt sich nicht durch ein
besseres Setup lösen und nicht durch einen engeren Stop, weil Regel M1 den Stop bei 1,0 × ATR
bodenverankert: Alles darunter wird von normalem Rauschen abgeräumt, bevor die Idee sich
entscheidet.

### Hürde 2 — Nachweis. Das ist Statistik.

Die Strategie hat **keinen nachgewiesenen positiven Erwartungswert**. 17 Konfigurationen über
100 simulierte Märkte, jede negativ, auch die ohne Spread. Das widerlegt sie nicht — der Test
konnte ihre Kernwette strukturell nicht prüfen, siehe
[BACKTEST-ERGEBNISSE.md](./BACKTEST-ERGEBNISSE.md) — aber „nicht widerlegt" ist nicht
„funktioniert".

Und nach einem Abend Demo hat man 2–4 Trades. Aus 2–4 Trades folgt nichts.

### Die ehrliche Reihenfolge

- **Jetzt:** Demokonto mit 1 000 USD, Advisor-Modus, Journal läuft mit.
- **Nach 2–4 Wochen:** `python -m metals journal`. Auf die Disziplin-Sektion schauen, nicht
  auf die Bilanz.
- **Wenn die Stops gehalten haben:** Auto-Modus, weiterhin **Demo**.
- **Echtes Geld:** wenn über Monate eigene Zahlen vorliegen, die etwas anderes sagen als der
  bisherige Backtest — und das Konto groß genug ist, dass 1 % Risiko eine handelbare Position
  ergibt.

Ein Bot, den man über Nacht auf echtes Geld stellt, lehrt nichts. Er sammelt nur Statistik,
und die Kosten dafür trägt man selbst.
