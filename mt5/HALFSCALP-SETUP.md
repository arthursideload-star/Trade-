# Die Halbziel-Taktik in MetaTrader installieren

Der zweite EA: **`GoldHalfScalp.mq5`**. Viele kurze Trades, jeder bei der Hälfte des
projizierten Ziels geschlossen. Gemessen **alle 8,5 Minuten ein Trade** in den guten
Fenstern.

Das ist ein **anderer EA** als `GoldScalpAssistant`. Er kommt in denselben Ordner, hat
eine eigene Magic Number und ein eigenes Journal. Beide gleichzeitig laufen zu lassen geht,
ist aber für den Anfang eine schlechte Idee — dann weißt du nicht, welcher was verursacht.

---

## Vorher lesen: was hier bekannt ist und was nicht

**Die gemessene Kante stammt aus dem Simulator.** Schaltet man dort den Rundzahl-Magneten
ab, verschwindet sie (+0,033 → −0,013 R, Band über der Null hinweg). Der Magnet steht im
Simulator, *weil jemand geglaubt hat, dass Gold sich so verhält* — das wieder
herauszumessen beweist über echtes Gold nichts. Befunde A34 und A35.

**Die Taktik genau wie zuerst beschrieben verliert.** Dem Impuls folgen, Ziel = ein
gemessener Zug: 85 Verlusttage von 85. Der EA fährt **nicht** diese Fassung, sondern die
gegengerichtete mit doppelt gestecktem Ziel.

**Deshalb verweigert der EA den Start auf einem Echtgeld-Konto.** Das ist kein Versehen und
keine Bevormundung — es gibt schlicht keinen Beleg, der Echtgeld rechtfertigen würde. Es
gibt einen Schalter dafür, und wenn du ihn umlegst, weißt du wenigstens, dass du es
getan hast.

---

## Schritt 1 — Demokonto prüfen

In MetaTrader oben links steht dein Konto. Es muss **Demo** sein. Ist es das nicht, legst du
über **Datei → Konto eröffnen** ein Demokonto an.

**Mindestens 2 000 USD Guthaben.** Nicht aus Vorsicht, sondern aus Arithmetik: Der EA
riskiert 0,25 % je Trade. Bei 1 000 USD sind das 2,50 USD, und ein typischer Stop von
2–3 USD je Unze passt dann nicht mehr in die kleinste handelbare Position. Der EA sagt das
dann auch ins Log — aber dann handelt er eben nicht.

## Schritt 2 — Datei kopieren

1. In MetaTrader: **Datei → Datenverzeichnis öffnen**
2. Dort in den Ordner `MQL5` → `Experts`
3. `GoldHalfScalp.mq5` aus dem Git-Ordner `mt5/Experts/` hineinkopieren

Prüfen, dass sie vollständig ist:

```bash
wc -l GoldHalfScalp.mq5
```

Es muss **1042** dastehen. Steht dort weniger, ist die Datei abgeschnitten — nochmal
kopieren.

> Unter Windows hängt der Editor gern `.txt` an. Die Datei muss auf `.mq5` enden. Notfalls
> im Explorer unter *Ansicht → Dateinamenerweiterungen* einblenden und umbenennen.

## Schritt 3 — Kompilieren

1. **MetaEditor** öffnen (F4 in MetaTrader)
2. Links im Navigator `GoldHalfScalp.mq5` doppelklicken
3. **F7** drücken

> **F7, nicht F5.** F5 startet den Debugger und öffnet einen *fremden* Chart — meistens
> EURUSD H1. Das ist genau der Fehler, der beim ersten EA einen Abend gekostet hat. Kommt
> versehentlich ein EURUSD-Fenster hoch: **Umschalt+F5**, Fenster schließen, dann F7.

Unten muss **`0 errors, 0 warnings`** stehen.

## Schritt 4 — Auf den Chart ziehen

1. In MetaTrader einen **XAUUSD**-Chart öffnen
2. Zeitrahmen auf **M1** stellen
3. Oben in der Symbolleiste muss **Algo-Trading grün** sein
4. Im Navigator unter *Expert Advisors* `GoldHalfScalp` auf den Chart ziehen
5. Im Dialog Reiter **Allgemein**: Haken bei *Algo-Trading erlauben*
6. **OK**

Ist alles richtig, steht oben links am Chart:

```
GoldHalfScalp  aktiv  |  Session: PRIME  |  Trades heute: 0/200  |  flach
```

Und im Reiter **Experten** unten:

```
GoldHalfScalp ready. reversion, risk 0.25% per trade, target = 2.0x the
trigger bar, banked at 50%, stop at 100%, give up after 10 min.
journal: GoldHalfScalp.csv in MQL5/Files (File -> Open Data Folder).
```

---

## Was du dann sehen solltest

| Wann | Was |
|---|---|
| In **PRIME/good**-Fenstern | Etwa **alle 8–9 Minuten** ein Trade, im Schnitt 6 Minuten gehalten |
| Panel zeigt `AVOID` | Rollover (21–23 UTC), Wochenende, Freitagabend. Richtig so |
| Panel zeigt `marginal` | Asiatische Stunden. Der EA handelt dort nicht — kostete gemessen 0,018 R je Trade |
| Nach ein paar Stunden | `GoldHalfScalp.csv` in `MQL5/Files` füllt sich |

**Wenn eine ganze Stunde in einem PRIME-Fenster nichts passiert, stimmt etwas nicht.** Dann
in den Reiter *Experten* schauen — der EA schreibt jedes Mal hin, warum er einen Trade
gelassen hat.

Die drei häufigsten Gründe stehen dort im Klartext:

| Meldung | Bedeutung |
|---|---|
| `refused: half-target ... does not clear ...` | Dein Spread ist zu hoch für diesen Zeithorizont. Das ist ein echtes Ergebnis, kein Fehler |
| `cannot size: position rounds to ...` | Konto zu klein. 2 000 USD Demo nehmen |
| `AVOID window (...)` | Falsche Tageszeit |

---

## Nach dem ersten Tag

```bash
python -m metals journal --file GoldHalfScalp.csv
```

Das rechnet Trefferquote, Erwartungswert **und Konfidenzbänder**. Die Bänder sind der
Punkt: bei kleiner Stichprobe sagt die Auswertung ehrlich, dass sie nichts belegt — und
dann belegt sie nichts, egal wie überzeugend die Summe aussieht.

Und in den Tresor:

```bash
python -m metals vault --journal GoldHalfScalp.csv
```

Jeder Trade bekommt eine eigene Notiz zum Kommentieren. Deine Notizen überleben jeden
weiteren Export.

### Worauf zu achten ist

**Nicht auf die Trefferquote.** Die wird hoch sein — um die 65 %. Das ist bei dieser Taktik
gerade *kein* gutes Zeichen für sich genommen, weil sie durch das Frühschließen erkauft
ist. Die Zahl, die zählt, steht daneben: **wie hoch die Trefferquote sein müsste**, damit
das Verhältnis von Gewinn zu Verlust aufgeht.

**Auf die Kosten.** `metals journal` zeigt, was der Spread gefressen hat. Im Simulator waren
das bei der ersten Fassung 100 % des Ergebnisses.

**Auf die Zahl der Trades.** Bleibt sie weit unter 8 pro Stunde in guten Fenstern, ist dein
Spread höher als die 0,20 $/oz, mit denen gerechnet wurde — dann greift das Kostengatter
öfter, und das ist die richtige Reaktion.

---

## Die Grenzen, die im Code stehen

Diese Zahlen sind **keine** Eingabefelder. Sie zu ändern verlangt eine Änderung am Code und
damit einen Commit — das ist Absicht, ein Regler im Eigenschaften-Dialog lässt sich nachts
um zwei verstellen und hinterlässt keine Spur.

| Grenze | Wert | Warum |
|---|---|---|
| Risiko je Trade | **0,25 %** | Der andere EA nimmt 1 %, macht aber 4 Trades am Tag. Dieser macht ~100 |
| Tagesverlust | **5 %** | Dann ist der Tag vorbei, egal was die Signale sagen |
| Trades je Tag | **200** | Eine Decke, kein Ziel. Ein normaler Tag liegt bei ~100 |
| Stop mindestens | **0,8 × ATR** | Ein Stop im Rauschen macht aus einer guten Idee eine schlechte |
| Kostengatter | **1,5 ×** Round-Trip | Ein Trade, der seinen Spread nicht verdient, hat eine negative Kante |

---

## Wenn du ihn wieder abschalten willst

Rechtsklick auf den Chart → **Expert Advisors → Entfernen**. Oder den Algo-Trading-Knopf
in der Symbolleiste ausschalten — das stoppt beide EAs sofort.

**Offene Positionen bleiben offen.** Der EA hängt Stop und Ziel beim Öffnen an die Order, es
liegt also beides beim Broker und wirkt weiter. Der **Zeitstop** dagegen ist das Einzige,
was der EA selbst erledigt — läuft er nicht mehr, schließt nichts mehr nach zehn Minuten.

## Zwei Dinge, die du nicht tun solltest

**Nicht nebenher XAUUSD von Hand handeln.** Auf einem Netting-Konto gibt es je Symbol nur
*eine* Position — deine und die des EA würden verrechnet, und dann stimmt weder sein Stop
noch seine Buchführung. Gib ihm ein Konto für sich.

**Den Terminal-Neustart musst du nicht fürchten.** Der EA liest beim Start die Trades des
laufenden Tages aus der Historie zurück: Tagesverlustgrenze und Trade-Decke zählen weiter,
statt bei null anzufangen. Eine Grenze, die ein Neustart löscht, wäre keine — und auf einem
VPS sind Neustarts normal.

Siehe auch: `docs/REPO-AUDIT.md` (A34, A35) · `obsidian/01-Strategie/Die Halbziel-Taktik.md`
