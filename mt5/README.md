# GoldScalpAssistant — Bot direkt in MetaTrader 5

Der Assistent als Expert Advisor. Gleiche Setups, gleiche Risikoregeln wie das
Python-Paket in `metals/` — damit das, was du testest, und das, was läuft, dasselbe System
sind und nicht zwei ähnliche.

---

## ⚠️ Bevor du irgendetwas installierst

**Diese Strategie hat keinen nachgewiesenen positiven Erwartungswert.** Sie wurde über
100 simulierte Märkte in 17 Konfigurationen geprüft — jede einzelne war negativ,
einschließlich einer ohne jeden Spread. Diese Prüfung konnte die Kernwette der Setups
strukturell nicht testen (siehe `docs/BACKTEST-ERGEBNISSE.md`), das Ergebnis ist also
**unentschieden, nicht vernichtend**. Aber „unentschieden" ist nicht „profitabel".

**Was der EA nachweislich leistet:** korrekte Positionsgrößen, Stops die normales Rauschen
überleben, ein Tagesverlustlimit das wirklich stoppt, und die Weigerung, in den Fenstern zu
handeln, in denen Golds Spread die Kante auffrisst.

**Deshalb:**
1. **Nur Demokonto.** Kein echtes Geld, bis du eigene Zahlen über mindestens 30 Trades hast.
2. **Starte im Advisor-Modus** (Standard). Der EA zeichnet, rechnet und meldet — platziert
   aber keine Order. So kannst du seine Einschätzung mit deiner eigenen vergleichen, bevor
   er etwas ausgeben darf.
3. **Auto-Modus erst danach**, und auch dann nur auf Demo.

---

## Geht das auf dem Handy?

**Nein.** Die MT5-App für iOS und Android hat keine EA-Engine — das gilt für jeden Expert
Advisor, auch für gekaufte aus dem MQL5-Markt. Warum das so ist und welche Wege es
stattdessen gibt: **[MOBILE-SETUP.md](./MOBILE-SETUP.md)**.

Wenn du bereits einen VPS hast und ihn heute einrichten willst — Schritt für Schritt,
Windows *und* Linux: **[VPS-SETUP.md](./VPS-SETUP.md)**.

## Installation

### 1. Eine Datei kopieren

In MT5: **Datei → Datenverzeichnis öffnen**. Dann:

```
MQL5/Experts/GoldScalpAssistant.mq5        ← aus mt5/Experts/
```

Das ist alles. Der EA ist **eine einzige, in sich geschlossene Datei** — kein
Include-Ordner, nichts anzulegen. Das ist Absicht: Installation über eine
Fernwartungsverbindung ist umständlich genug ohne Verzeichnisbäume.

### 2. Kompilieren

In MT5 **F4** drücken (MetaEditor öffnet sich) → `GoldScalpAssistant.mq5` öffnen → **F7**.

Es sollte „0 errors, 0 warnings" erscheinen. Danach ist der EA im Navigator unter
**Expert Advisors** sichtbar.

### 3. Auf den Chart ziehen

- Chart öffnen: **XAUUSD**, Zeitrahmen **M5**
- EA aus dem Navigator auf den Chart ziehen
- Reiter **Allgemein**: Haken bei *Algo-Trading erlauben*
- **OK**

Oben links erscheint das Panel. Steht dort `[ADVISOR]`, ist alles richtig.

### 4. Algo-Trading global freischalten

Der Knopf **Algo-Trading** in der Symbolleiste muss grün sein. Ist er rot, passiert nichts —
auch im Advisor-Modus werden dann keine Meldungen erzeugt.

---

## Einstellungen

Was **nicht** einstellbar ist: Risiko pro Trade, Tagesverlustlimit, Mindest-CRV, maximale
Trades pro Tag. Die stehen als `#define`-Konstanten oben in der EA-Datei. Ein Risikolimit, das man um 15:30
an einem schlechten Tag im Einstellungsdialog ändern kann, ist kein Limit.

| Einstellung | Standard | Bedeutung |
|---|---|---|
| **Run mode** | Advisor | `Advisor` = nur Signale. `Auto` = handelt selbst. |
| Magic number | 20260726 | Nur ändern, wenn mehrere EAs auf demselben Konto laufen |
| Trade prime windows only | ja | Nur London-Killzone, NY-Killzone, Overlap |
| Alerts | ja | Pop-up bei einem Signal |
| Dashboard | ja | Panel oben links |
| S2 / S4 / S5 | alle an | Welche Setups laufen |
| First target in R | **0.5** | Gemessen besser als die übliche 1.0 — siehe unten |
| Percent closed at first target | 60 % | |
| Runner target in R | 2.5 | |
| Trail in ATR | 1.2 | |
| Time stop (Minuten) | 45 | Schließt unabhängig vom Stand |
| ATR period | 14 | |
| News blackout (Minuten) | 30 | Um 08:30, 10:00 und 14:00 New Yorker Zeit |

### Warum das erste Ziel bei 0,5R und nicht bei 1,0R

Das ist kein Geschmack, sondern gemessen. In den Backtests erreichten **Verlust-Trades im
Schnitt +0,47R**, bevor sie scheiterten — das übliche Teilziel bei 1,0R lag also knapp
jenseits des Punktes, an dem die meisten drehten. Die Verschiebung auf 0,5R verbesserte den
Erwartungswert von −0,182R auf −0,109R und senkte den Anteil verlierender Märkte von 94 %
auf 75 %.

Gegenprobe: den Teilgewinn **kleiner** zu machen (40 % statt 60 %) verschlechterte das
Ergebnis. Es geht also um die **Lage** des ersten Ziels relativ zum Umkehrpunkt der
Verlierer, nicht um „früher raus ist besser".

---

## Die Setups

| ID | Name | Idee |
|---|---|---|
| **S2** | Pullback Window Break | EMA-Stapel 9/21/50 gibt die Richtung, 1–3 Gegenkerzen bilden den Pullback, dessen Bruch ist der Einstieg. Tiefer als drei Kerzen ist keine Pause mehr, sondern eine laufende Umkehr. |
| **S4** | Round Number Fade | Ausgedehnte Bewegung in einen 10er-Griff, Ablehnung dort. Nur erster oder zweiter Test. |
| **S5** | Momentum Continuation | Kerze ≥ 1,5 × ATR mit Schluss in den äußeren 20 % ihrer Spanne ist eine Neubewertung. Die flache Korrektur danach ist der Einstieg. |

S5 gehört zur selben Familie wie die bekannten Volatilitäts-Expansions-Scalper
(Goldfinch und Verwandte): Sie handeln die Trägheit nach einer plötzlichen
Preisbeschleunigung.

`python -m metals setups scalp` zeigt den vollständigen Katalog inklusive der Zustands-
automaten und — wichtiger — **wie jedes Setup scheitert**.

---

## Die Risikoregeln, die der EA erzwingt

| Regel | Was passiert |
|---|---|
| **1 % pro Trade** | Größe wird aus Stop-Distanz und dem **Tickwert deines Brokers** gerechnet |
| **−3 % am Tag** | Schluss bis zur nächsten Session |
| **+2 % am Tag** | **Auch Schluss.** Einen guten Tag zurückzugeben ist die häufigste Art, eine gute Woche zu verlieren |
| **2 Verluste in Folge** | Schluss. Das Regime passt nicht mehr zu den Setups |
| **4 Trades am Tag** | Schluss. Ab da wird Langeweile gehandelt |
| **20 Min Abkühlung nach Verlust** | Der Trade direkt nach einem Verlust ist statistisch der schlechteste |
| **Stop ≥ 0,8 × ATR** | Enger ist Rauschen. Wird notfalls aufgeweitet — das verkleinert die Position, und das ist richtig so |
| **Stop 0,35 × ATR jenseits des Levels** | Nie darauf. Gold greift durch Levels, um die Stops zu holen |
| **Spread > 15 % des ATR** | Kein Einstieg |
| **Spread > 10 % der Stop-Distanz** | Kein Einstieg |
| **Rollover / Wochenende / Freitagabend** | Kein Einstieg, offene Position wird freitags 19:00 UTC geschlossen |
| **News-Fenster ±30 Min** | Kein Einstieg |
| **Kein Martingale, kein Grid** | Größe steigt nie nach einem Verlust |

### Ein Detail, das in Python nicht möglich war

Die Positionsgröße wird hier über `SYMBOL_TRADE_TICK_VALUE` deines Brokers gerechnet. Das
Python-Paket muss 100 Unzen pro Lot annehmen und ausdrücklich davor warnen — MT5 weiß den
echten Wert. **An dieser einen Stelle ist die MT5-Version strikt besser.**

---

## Neustart-Festigkeit

Der EA wird bei **jedem** Zeitrahmenwechsel, jeder Parameteränderung, jedem
Terminal-Neustart und jeder VPS-Migration neu geladen. Ohne Vorkehrung passiert dabei
zweierlei, und beides wiegt im Auto-Modus schwer:

- Eine **offene Position wäre unverwaltet** — kein Teilgewinn, kein Break-even, kein
  Trailing, kein Zeitstop. Nur der ursprüngliche Stop schützt sie noch, also das Schlechteste
  aus beiden Welten.
- Die **Tageszähler stünden auf null**, das Trade-Limit und das Verlustlimit ließen sich
  also durch einen Neustart umgehen.

Beides wird beim Start aus den Aufzeichnungen des Terminals rekonstruiert:

- `RebuildDayState()` zählt die heutigen Deals mit unserer Magic-Nummer und stellt
  Trade-Zahl, Verlustserie und Tages-P/L wieder her.
- `AdoptExistingPosition()` übernimmt eine bestehende Position und setzt die Verwaltung
  fort. Ob der Teilgewinn schon genommen wurde, liest der EA daran ab, ob der Stop bereits
  auf Einstand steht — im Zweifel gilt „schon genommen", damit er nie doppelt verkauft.

**Eine Ausnahme ohne Verhandlung:** Findet der EA beim Start eine Position **ohne Stop**,
schließt er sie. Eine Position ohne definierte Invalidierung ist kein Trade, sondern eine
offene Rechnung (Regel R7) — das gilt auch für eine, die er nicht selbst eröffnet hat.

## Das Journal

Der EA schreibt jedes erkannte Setup und jeden geschlossenen Trade nach
`MQL5/Files/GoldScalpAssistant.csv` — ab dem ersten Signal, **auch im Advisor-Modus**, ohne
Einstellung. Ein Protokoll, das man abschalten kann, wird abgeschaltet, und dann fehlt genau
die Woche, um die es später geht.

Zwei Zeilenarten:

| `kind` | Wann | Enthält |
|---|---|---|
| `signal` | Ein Setup wurde erkannt | Einstieg, Stop, T1, T2, ATR, Spread, Session, Größe — und ob es gehandelt wurde, sonst **warum nicht** |
| `close` | Eine Position wurde geschlossen | Ergebnis in **R**, Ausstiegsgrund, Haltedauer |

Ausgewertet wird in Python, nicht im EA:

```bash
python -m metals journal --file GoldScalpAssistant.csv
```

**Der EA liest diese Datei nie zurück.** Er justiert sich nicht selbst nach — das ist eine
Entscheidung, keine fehlende Funktion, und `tests/test_mt5_parity.py` erzwingt sie: Der EA
darf `FileWriteString` benutzen und keine der `FileRead*`-Funktionen. Ein Rückkanal würde
also einen roten Test hinterlassen.

Die Begründung mit den Zahlen steht in **[../docs/LERNEN.md](../docs/LERNEN.md)**. Kurzform:
Bei 10–12 Auswertungsschubladen liegt die Chance, dass mindestens eine rein zufällig gut
aussieht, bei rund 46 %. Ein Automatismus, der die beste hochgewichtet, verfolgt genau dieses
Rauschen.

**Der R-Multiplikator** ist verdientes Geld geteilt durch riskiertes Geld, mit dem beim
Einstieg festgehaltenen Risikobetrag als Nenner. Nicht über die Preisdistanz: Sobald der
Teilgewinn genommen und der Stop auf Einstand gezogen ist, entspricht die Preisdistanz nicht
mehr dem tatsächlich getragenen Risiko.

## Was der EA anders macht als ein Backtest

Drei Dinge, die es im Strategietester nicht gibt und die live sofort auftreten:

**1. Mindest-Stop-Abstand des Brokers.** `SYMBOL_TRADE_STOPS_LEVEL` ist der kleinste
Abstand, den Stop oder Limit vom Preis haben dürfen. Bei Gold sind das oft 10–50 Punkte =
0,10–0,50 USD/oz. Ein Scalping-Stop darunter wird vom Server **abgelehnt**. Der EA weitet
den Stop entsprechend und protokolliert das.

**2. Teilgewinn kann unmöglich sein.** Wenn 60 % oder der Rest unter die Mindest-Lotgröße
fallen, geht kein Teilverkauf. Der EA schließt dann vollständig am ersten Ziel und sagt
warum — besser ein kleiner Gewinn als eine abgelehnte Order, während der Preis wegläuft.

**3. Brokerzeit ist nicht UTC.** MT5-Server laufen meist auf GMT+2/+3 und haben eine eigene
Sommerzeit. Der EA rechnet über `TimeGMT()` konsequent in UTC und konvertiert nur an der
Kante. Wer das nicht tut, handelt die London-Setups drei Stunden zu früh.

---

## Im Strategietester

**Wichtig — sonst sind die Ergebnisse wertlos:**

- Modellierung: **„Jeder Tick basierend auf realen Ticks"**. Alles andere erzeugt bei
  Scalping *Phantom-Trades*, die live nie zustande kämen. Das ist die dokumentierte
  Hauptschwäche von Tick-Scalping-Backtests.
- Spread: **„Aktuell" ist gefährlich.** Setz einen realistischen festen Spread, mindestens
  20 Punkte, besser 30 — dein echter Gold-Spread ist zu Nachrichtenzeiten ein Vielfaches
  des Durchschnitts.
- Zeitraum: mindestens 6 Monate, besser 2 Jahre.
- Modus: **Advisor-Modus platziert keine Order** — für den Tester auf `Auto` stellen.

Die Session-Grenzen im Tester sind **Näherungen**: Der Tester kennt die historischen
Sommerzeit-Umstellungen deines Brokers nicht.

---

## Wenn der EA nichts tut

Das ist der Normalfall. Schau ins Panel und ins Journal:

| Panel zeigt | Bedeutung |
|---|---|
| `AVOID` | Rollover, Wochenende, Markt geschlossen — richtig so |
| `marginal` | Asien-Session; bei „prime only" wird nicht gehandelt |
| `STOPPED: ...` | Eine harte Regel greift. Der Grund steht dabei |
| `PRIME` und trotzdem nichts | Kein Setup. Die meisten Kerzen sind keine Gelegenheit |

Im **Experten**-Reiter (unten in MT5) steht bei jeder abgelehnten Gelegenheit der Grund im
Klartext — einmal pro Grund, nicht pro Kerze.

---

## Daten aus MT5 für den Python-Backtest exportieren

Dein Broker hat die Daten, die deinen echten Fills am nächsten kommen:

1. **Extras → Optionen → Charts**: „Max. Balken im Chart" auf `Unbegrenzt`
2. XAUUSD M5 öffnen, mit **Pos1** ganz nach links scrollen (lädt die Historie)
3. **Extras → Verlaufsdaten** → XAUUSD → M5 → **Exportieren**

Dann im Projekt:

```bash
python -m metals backtest --source file --file xauusd_m5.csv --tz broker_gmt3
```

**Die Zeitzone musst du angeben** — es gibt bewusst keinen Standardwert. Falsch geraten
verschiebt jede Session-Regel, ohne dass man es an den Zahlen sieht. Der Lader prüft
gegen, indem er nachrechnet, ob die volatilsten Stunden dort liegen, wo sie bei Gold liegen
müssen (12:00–17:00 UTC), und warnt, wenn nicht.

Welchen Offset dein Broker hat, siehst du in MT5 unter **Marktübersicht** an der
Server-Uhrzeit im Vergleich zu UTC.

---

## Verhältnis zum Python-Teil

| | Python `metals/` | MT5 EA |
|---|---|---|
| Setups | G1–G12 (Swing) + S1–S6 (Scalp) | S2, S4, S5 |
| Makro, News-Feeds, COT, Gold/Silber-Ratio | ja | nein |
| Backtest über viele Märkte | ja | MT5-Tester |
| Positionsgröße über echten Tickwert | nein (nimmt 100 oz an) | **ja** |
| Führt Trades aus | nein | ja (im Auto-Modus) |

**Empfohlener Ablauf:** Python für die Analyse und die Marktlage (`/trade` im Chat), MT5
für Ausführung und Positionsverwaltung. Der EA im Advisor-Modus ist dabei die Gegenprobe:
Wenn er und die Chat-Analyse dasselbe sagen, ist das ein echtes Argument. Wenn nicht, ist
es einer.

---

## Haftung

Keine Anlageberatung, keine Ertragsversprechen. Automatisierter Handel setzt Kapital dem
Marktrisiko aus. Der Code ist Teil eines Lernprojekts und wurde nicht auf echten Konten
validiert.
