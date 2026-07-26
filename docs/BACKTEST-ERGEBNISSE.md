# Backtest-Ergebnisse — was gemessen wurde und was es bedeutet

Stand: 2026-07-26. Auswertung von **100 unabhängigen Marktläufen × 17 Konfigurationen**,
insgesamt **rund 60.000 Trades** — zehn im ersten Raster (Abschnitt 1), sieben zur Prüfung
der daraus abgeleiteten Verbesserungen (Abschnitt 6b).

Reproduzierbar mit:

```bash
python -m metals backtest --bars 3000 --seed 42        # ein Lauf, Detailreport
python -c "from metals import evaluate; from metals.backtest import BacktestConfig; \
           ev = evaluate.evaluate(BacktestConfig(), runs=100); print(evaluate.report(ev))"
```

---

## 0. Zuerst: Woher die Daten kommen

Die Build-Umgebung dieses Projekts hat **keinen Netzzugang** — die Organisations-Policy
beantwortet jeden Verbindungsversuch zu externen Hosts mit 403. Historische Golddaten konnten
hier nicht geladen werden.

Gemessen wurde deshalb auf einem **Marktsimulator** (`metals/simulate.py`), der Golds
dokumentierte statistische Eigenschaften nachbildet: Volatilitäts-Cluster, fette Ränder
(Excess-Kurtosis > 1, im Test geprüft), Session-Volatilitätsprofil, Magnetismus runder
Zahlen, Liquiditäts-Sweeps.

> **Das ist keine Erfolgswahrscheinlichkeit für echtes Gold.** Was es ist, steht in
> Abschnitt 5 — und die Grenze ist wichtiger als die Zahlen selbst.

Für echte Zahlen im interaktiven Chat:

```bash
python -m metals backtest --source live --bars 5000
```

---

## 1. Das Gesamtergebnis

| Konfiguration | Trades | Treffer% | Erwartungswert | Verlierende Läufe | Median R |
|---|---:|---:|---:|---:|---:|
| A Basis: 60 % bei 1R | 4.192 | 47,0 | **−0,182R** | 94 % | −7,8 |
| B 33 % bei 1R | 4.192 | 47,0 | −0,213R | 95 % | −9,2 |
| C erstes Ziel bei 1,5R | 4.184 | 40,9 | −0,209R | 94 % | −8,7 |
| D kein Teilgewinn, ein 2R-Ziel | 4.196 | 30,2 | −0,248R | 94 % | −10,0 |
| E weiteres Trailing (2,0 × ATR) | 4.192 | 46,5 | −0,186R | 92 % | −7,8 |
| F längerer Zeitstop (120 Min) | 4.106 | 48,7 | −0,203R | 96 % | −8,4 |
| G 33 % bei 1,5R + weites Trailing | 4.066 | 39,0 | −0,279R | 96 % | −11,2 |
| H höhere Konfidenzschwelle (0,60) | 3.431 | 46,3 | −0,168R | 88 % | −5,5 |
| **I nur Overlap-Session** | 2.595 | 47,9 | **−0,140R** | 81 % | −3,5 |
| **J Spread = 0 (Kostenprobe)** | 4.225 | 48,8 | **−0,065R** | 74 % | −2,7 |

**Keine einzige Konfiguration ist positiv.** Auch nicht die ohne jede Handelskosten.

---

## 2. Die entscheidende Zeile ist J

Variante J handelt mit **Spread null und Slippage null** — ein Markt, den es nicht gibt.
Selbst dort:

```
Erwartungswert   −0,065R
95%-Konfidenzintervall  [−0,069R, −0,062R]
Verlierende Läufe  74 %
```

Das Intervall liegt **vollständig unter null**. Das heißt:

> **Die Kosten sind nicht das Problem. Sie machen es schlimmer** (−0,065 → −0,182, also gut
> zwei Drittel des Verlusts) **— aber die Signale selbst tragen in diesen Daten keine Kante.**

Wäre der Spread die Ursache, müsste J bei etwa null liegen. Tut es nicht.

---

## 3. Was die Trades tatsächlich gemacht haben

Gepoolt über 12 Märkte, Basiskonfiguration:

```
Gewinner   Ø MAE −0,49R    Ø MFE +1,47R
Verlierer  Ø MFE +0,47R

Ausstiege: Zeitstop 40 %  |  Stop 37 %  |  Trailing 20 %  |  Ziel 4 %
```

Drei Dinge stehen darin:

**1. Nur 4 % erreichen das Runner-Ziel.** Das 2,5R-Ziel ist innerhalb von 45 Minuten
praktisch unerreichbar. Ein Ziel, das in 96 % der Fälle nicht angelaufen wird, ist kein Ziel,
sondern Dekoration.

**2. 40 % enden im Zeitstop.** Die Setups lösen sich nicht innerhalb ihres eigenen Horizonts
auf. Entweder ist der Zeitstop zu kurz — Variante F mit 120 Minuten hat es aber
**verschlechtert** (−0,203 statt −0,182) — oder es sind schlicht keine Scalping-Setups. Die
zweite Erklärung passt besser zu den Daten.

**3. Verlierer stehen im Schnitt +0,47R im Plus, bevor sie scheitern.** Fast ein halbes R
Buchgewinn, das komplett zurückgegeben wird. Das ist die größte einzelne
Verbesserungsmöglichkeit — und genau die, die Variante B (kleinerer Teilgewinn) *falsch
herum* angeht.

Und Gewinner laufen im Schnitt nur 0,49R gegen einen, bevor sie funktionieren. **Der Stop ist
weiter, als er sein müsste.** Der Report weist genau darauf jetzt automatisch hin.

---

## 4. Was funktioniert hat und was nicht

### Verbessert hat

| Maßnahme | Effekt |
|---|---|
| **Nur Overlap-Session handeln** (I) | −0,182 → **−0,140**, verlierende Läufe 94 % → 81 % |
| **Höhere Konfidenzschwelle** (H) | −0,182 → **−0,168**, verlierende Läufe 94 % → 88 % |
| Weiteres Trailing (E) | −0,182 → −0,186 (praktisch unverändert) |

Das Muster ist eindeutig: **Weniger handeln ist besser.** Von 4.192 auf 2.595 Trades
reduzieren verbessert jede Kennzahl. Das ist kein Zufall — es ist das, was passiert, wenn
eine Strategie keine Kante hat: Weniger Handel heißt weniger Verlust.

### Verschlechtert hat

| Maßnahme | Effekt | Warum |
|---|---|---|
| **Kein Teilgewinn, ein 2R-Ziel** (D) | −0,248, Trefferquote fällt auf 30 % | Ohne Teilgewinn wird aus jedem Beinahe-Gewinner ein Vollverlust |
| **33 % bei 1,5R + weites Trailing** (G) | −0,279, schlechteste Variante | Zwei Änderungen, die einzeln plausibel sind, wirken gegeneinander |
| Kleinerer Teilgewinn (B) | −0,213 | Weniger früh sichern heißt mehr Rückgabe |
| Längerer Zeitstop (F) | −0,203 | Mehr Zeit im Markt ohne Kante ist mehr Risiko, nicht mehr Chance |

---

## 5. Was diese Zahlen belegen — und was ausdrücklich nicht

### Belegt

✅ **Die Mechanik funktioniert.** Signale feuern, R-Vielfache und Kosten werden korrekt
gerechnet, Ausstiege verhalten sich wie spezifiziert, kein Lookahead (per Präfix-Test
verifiziert).

✅ **Zwei echte Konstruktionsfehler wurden gefunden und behoben** (Abschnitt 6), und zwei daraus abgeleitete Verbesserungen wurden geprüft und übernommen (Abschnitt 6b).

✅ **Die Teilgewinn-Arithmetik.** 60 % bei 1R zu schließen und den Rest per
Break-even-Stop abzusichern ergibt +0,60R im Gewinnfall gegen −1,00R im Verlustfall — also
**62,5 % erforderliche Trefferquote nur für Break-even**, vor Kosten. Das ist Rechnung, kein
Marktphänomen: **Es gilt auf echten Daten genauso.**

✅ **Die asiatische Session ist für Scalping unbrauchbar.** Konsistent über alle Läufe.
Standardmäßig jetzt ausgeschlossen.

### Nicht belegt

❌ **Keine Aussage über die echte Trefferquote auf Gold.**

❌ **Der Test kann Sweep-Umkehr-Setups gar nicht bewerten.** Das ist die wichtigste
Einschränkung und sie verdient einen eigenen Absatz:

> Der Simulator erzeugt Liquiditäts-Sweeps — aber er erzeugt sie **zufällig**, nicht
> kausal. In einem echten Markt greift der Preis durch ein Level, *weil* dort Stop-Orders
> liegen, und bewegt sich danach in die Gegenrichtung, *weil* er sich die dafür nötige
> Liquidität geholt hat. Genau diese Kausalität hat der Simulator nicht. Setups S1 und S3
> wetten exakt darauf — und wetten hier auf einen Mechanismus, den es in diesen Daten nicht
> gibt.
>
> Ein Sweep-Reversal-Setup auf einem Generator ohne Sweep-Reversal-Mechanik muss ungefähr
> die Transaktionskosten verlieren. **Genau das misst J.** Das Ergebnis ist damit weder eine
> Widerlegung der Strategie noch eine Bestätigung — es ist ein Test, der diese Frage
> strukturell nicht beantworten kann.

❌ **Keine Grundlage für Positionsgrößen oder für eine Entscheidung, echtes Geld einzusetzen.**

---

## 6. Zwei Fehler, die der Backtest gefunden hat

Der eigentliche Ertrag dieses Durchlaufs.

### Fehler 1 — Trailing auf der Füllkerze *(Code-Bug, behoben)*

Der Trailing-Stop zog schon auf **derselben** Kerze nach, auf der das erste Ziel gefüllt
wurde, berechnet aus dem Hoch genau dieser Kerze. Der Runner-Stop landete rund **0,4R über
dem Einstieg** und wurde beim nächsten Rücksetzer mitgenommen.

**Wirkung:** Jeder Runner wurde zu einem Kleingewinn — was den gesamten Grund, einen Runner
zu halten, zunichtemacht.

Behoben: Getrailt wird erst ab der Folgekerze. Regressionstest vorhanden.

### Fehler 2 — Der Mindest-Stop wurde versprochen, aber nie angewendet *(Code-Bug, behoben)*

`MIN_SCALP_STOP_ATR = 0.8` war definiert, im Docstring beschrieben („floored so it never sits
inside the noise band") — und **nirgends angewendet**. Stops konnten beliebig eng liegen und
wurden von normalem Rauschen mitgenommen.

Behoben: `_scalp_stop` weitet den Stop jetzt, statt einen unhaltbaren zu akzeptieren. Drei
Tests.

### Und ein Strategiefehler, kein Code-Fehler

Die Teilgewinn-Falle (Abschnitt 5). Kein Bug — eine Strategie, die arithmetisch nicht
aufgehen kann, wenn die Trefferquote unter 62,5 % liegt. Sie lag bei 47 %.

---

## 6b. Die abgeleiteten Verbesserungen — und ob sie gewirkt haben

Aus den Excursions folgten zwei konkrete Änderungen. Beide wurden über weitere
**100 Läufe × 7 Konfigurationen** geprüft, statt sie nur zu empfehlen.

| Konfiguration | Trades | Treffer% | Erwartungswert | Verlierende Läufe |
|---|---:|---:|---:|---:|
| A Basis (Referenz) | 4.192 | 47,0 | −0,182R | 94 % |
| I nur Overlap | 2.595 | 47,9 | −0,140R | 81 % |
| K **Teilgewinn bei 0,5R** | 4.210 | — | −0,167R | 93 % |
| L 0,5R, nur 40 % raus | 4.210 | — | −0,197R | 93 % |
| **M K + nur Overlap** | 2.699 | — | **−0,109R** | 83 % |
| **N M + Konfidenz 0,60** | 1.993 | — | −0,112R | **75 %** |
| O N + Runner 4R | 1.991 | **63,2** | −0,111R | 78 % |

**Beide Ableitungen haben gewirkt:**

- Teilgewinn von 1,0R auf **0,5R**: −0,182 → −0,167 allein, in Kombination mit dem
  Session-Filter −0,109. **Verbesserung um 40 %** gegenüber der Basis.
- Konfidenzschwelle **0,60**: Trades von 2.699 auf 1.993, verlierende Läufe von 83 % auf
  **75 %** — der beste Wert der ganzen Untersuchung.

**Beide sind jetzt die Standardwerte** (`metals/exits.py`, `metals/backtest.py`), mit der
Begründung im Code.

Variante L zeigt die Gegenprobe: den Teilgewinn **kleiner** zu machen (40 % statt 60 %)
verschlechtert das Ergebnis. Es ist also nicht „früher raus ist immer besser", sondern
speziell die Lage des ersten Ziels relativ zu dem Punkt, an dem Verlierer drehen.

### Die lehrreichste Zeile der ganzen Tabelle

Variante **O** hat eine **Trefferquote von 63,2 %** — und einen **negativen**
Erwartungswert von −0,111R.

> Fast zwei von drei Trades gewinnen, und die Strategie verliert trotzdem Geld. Wer eine
> Strategie nach der Trefferquote auswählt, wählt genau diese aus.

Das ist derselbe Mechanismus wie bei der zitierten „71 %"-Zahl aus dem PDH/PDL-Repo
(`docs/GOLD-SCALPING.md`, Teil II).

---

## 7. Was als Nächstes zu tun ist

In dieser Reihenfolge:

**1. Auf echten Daten messen.** Alles andere ist Spekulation, bis das passiert ist. Im
interaktiven Chat, wo Netzzugang besteht:

```bash
export TWELVEDATA_API_KEY="..."
python -m metals backtest --source live --bars 5000
```

**2. ~~Teilgewinn früher setzen~~ — erledigt und geprüft** (Abschnitt 6b). Von 1,0R auf 0,5R,
in Kombination mit dem Session-Filter −0,182 → −0,109. Ist jetzt Standard.

**3. ~~Selektiver handeln~~ — erledigt und geprüft.** Konfidenzschwelle 0,60, nur die
liquiden Sessions. Verlierende Läufe 94 % → 75 %. Ist jetzt Standard.

**4. Den Stop enger setzen — offen.** Gewinner laufen im Schnitt nur 0,49R gegen einen. Ein
Stop bei 0,7R statt 1,0R würde bei den meisten Gewinnern nichts ändern und jeden Verlust um
30 % verkleinern. Bewusst **nicht** umgesetzt: Es kollidiert direkt mit Fehler 2
(Mindest-Stop 0,8 × ATR), und diesen Zielkonflikt auf simulierten Daten aufzulösen wäre eine
Optimierung auf Rauschen. Gehört auf echte Daten.

**5. Erst danach die Setup-Konfidenzen kalibrieren.** Aktuell sind sie begründete Schätzungen.
Erst 30+ echte Trades pro Setup machen daraus Messwerte.

---

## 8. Die ehrliche Antwort auf „welche Erfolgschance hat der Bot"

**In diesem Test: keine nachgewiesene Kante.** Erwartungswert negativ in allen siebzehn
geprüften Konfigurationen, das Konfidenzintervall in allen Fällen vollständig unter null.
Die beste Variante kam auf −0,109R — eine Verbesserung um 40 % gegenüber der
Ausgangskonfiguration, aber eben eine Verbesserung von schlecht auf weniger schlecht.

**Was das wert ist:** Der Test kann die Kernwette der Setups (Sweep-Umkehr) strukturell nicht
prüfen, weil der Simulator den Mechanismus nicht enthält. Er hat aber zwei echte Bugs und
einen echten Strategiefehler gefunden, die auf echten Daten genauso gewirkt hätten — und
zwar bevor Geld im Spiel war.

**Was daraus nicht folgt:** Dass die Strategie auf echtem Gold verliert. Das ist offen und
wird erst durch Punkt 1 oben beantwortet.

**Was daraus sehr wohl folgt:** Dass niemand — auch nicht auf der Demo — davon ausgehen
sollte, dass dieses System aktuell Geld verdient. Der belegte Nutzen liegt derzeit in der
Regeldisziplin: Positionsgrößen, die stimmen, Stops, die halten, ein Tageslimit, das greift,
und eine Nachrichtensperre, die geschlossen versagt. Das ist wertvoll und es ist nicht
dasselbe wie eine Kante.

> Ein Backtest, der eine Strategie bestätigt, ist angenehm. Einer, der zwei Bugs und einen
> Rechenfehler findet, ist nützlich. Dieser war der zweite.
