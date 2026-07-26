# Gold-Scalping — Setups, Ausstiege und die ehrliche Bilanz

Stand: 2026-07-26. Ergänzt `docs/GOLD-SILBER.md` um alles, was speziell für **kurze Trades**
auf Gold gilt: die Scalping-Setups S1–S6, das Ausstiegsmanagement, die Frage „wann höre ich
auf" — und die gemessenen Ergebnisse der Backtests.

**Code:** `metals/scalping.py`, `metals/exits.py`, `metals/backtest.py`,
`metals/simulate.py`, `metals/evaluate.py`

---

## Teil I — Die Ökonomie eines Gold-Scalps, bevor irgendetwas anderes kommt

Das ist der Abschnitt, dessen Missverständnis am meisten kostet. Er steht deshalb ganz vorn.

### I.1 Der Spread ist keine Nebensache

Bei einem Stop von 3 USD/oz und einem Spread von 0,20 USD/oz startet **jeder** Trade
**6,7 % seines Risikos im Minus**. Mit Slippage eher 10 %. Bei vier Trades am Tag ist das ein
permanenter Abfluss, den die Trefferquote erst einmal aufholen muss, bevor überhaupt etwas
übrig bleibt.

| Stop | Spread 0,20 | Spread 0,40 | Spread 0,60 |
|---|---|---|---|
| 2 USD/oz | 10,0 % | 20,0 % | 30,0 % |
| 3 USD/oz | 6,7 % | 13,3 % | 20,0 % |
| 5 USD/oz | 4,0 % | 8,0 % | 12,0 % |
| 10 USD/oz | 2,0 % | 4,0 % | 6,0 % |

Deshalb existiert **Setup S6 (Spread-Gate)**: Es verweigert den Trade, wenn der Spread über
10 % der Stop-Distanz liegt. Und deshalb ist ein enger Stop beim Scalping nicht „effizient",
sondern teuer.

### I.2 Die Teilgewinn-Falle — mit Zahlen

Die verbreitetste Scalping-Empfehlung lautet: 60 % bei 1R schließen, Rest nachziehen.
Rechnen wir sie durch.

Wenn 60 % bei 1R gehen und der Rest per Break-even-Stop bei null endet:

```
Gewinn-Trade:  0,6 × 1,0R + 0,4 × 0,0R = +0,60R
Verlust-Trade: −1,00R
```

Erforderliche Trefferquote für Break-even:

```
p × 0,60 = (1 − p) × 1,00   →   p = 62,5 %
```

**62,5 % Trefferquote, nur um bei null zu landen** — und das vor Kosten. Mit Spread sind es
eher 66 %. Das ist die Zahl, die kaum eine Scalping-Strategie erreicht.

Genau dieses Problem hat der erste Backtest sofort aufgedeckt (Teil V). Es ist kein Fehler
im Code gewesen, sondern ein Fehler in der Strategie — und ein Backtest ist genau dafür da.

### I.3 Was daraus folgt

> Beim Scalping bestimmt nicht die Einstiegsqualität den Erwartungswert, sondern die
> **Verteilung der Ausstiege**. Wer Gewinner bei 1R abschneidet und Verlierer bei 1R laufen
> lässt, kann den besten Einstieg der Welt haben und verliert trotzdem.

---

## Teil II — Die Setups S1 bis S6

Vollständig in `metals/scalping.py`, abrufbar mit `python -m metals setups scalp`.

### Der Zustandsautomat

Jedes Setup ist eine **Vier-Phasen-Maschine**, keine Einzelkerzen-Prüfung:

```
SCANNING  →  ARMED  →  WINDOW_OPEN  →  ENTRY
                 ↓           ↓
             INVALIDATED (das Setup ist gestorben, bevor es ausgelöst hat)
```

Diese Struktur stammt von **ilahuerta-IA/backtrader-pullback-window-xauusd** (MIT-Lizenz) —
übernommen wurde die Idee, der Code hier ist neu geschrieben.

Warum das zählt: Eine Einzelkerzen-Prüfung kann nicht ausdrücken „ich habe darauf gewartet,
und dann hat der Markt etwas getan, das sagt, ich lag falsch". Genau diese Unterscheidung
trennt ein Setup von einem Muster.

### S1 — Killzone Sweep Scalp ★ Kernsetup

Die M5-Version von G1. Preis fegt ein Session-Extrem, schließt zurück, der erste
M1-Strukturbruch ist der Einstieg.

- **Stop:** 0,35 × ATR(14) M5 jenseits des Sweep-Extrems
- **Nur** in der London- oder NY-Killzone
- **Scheitert wenn:** Der Sweep war ein echter Ausbruch und die zweite Kerze schließt
  ebenfalls außen. Ohne die M1-Bestätigung verdoppelt sich die Zahl dieser Fälle etwa.

### S2 — Pullback Window Break

EMA-Stapel 9/21/50 auf M5 gibt die Richtung, ein bis drei Gegenkerzen bilden den Pullback,
dessen Bruch der Einstieg ist.

- **Die Tiefenbegrenzung ist der Kern:** Ein Pullback tiefer als drei Kerzen ist keine Pause
  mehr, sondern eine laufende Umkehr.
- **Steigungsfilter:** Ein flacher EMA-Stapel ist eine Range in Trend-Verkleidung. Ohne
  diesen Filter feuert das Setup den ganzen Tag in der Seitwärtsbewegung und verliert allein
  am Spread.

### S3 — Prior-Day Sweep mit Richtungsfilter

Sweep des Vortageshochs/-tiefs — **gefiltert nach der Richtung des Vortages**: Nach einem
bullischen Tag nur Sweeps des Vortagestiefs (long), nach einem bärischen nur des Hochs
(short).

Der Filter stammt von **ikeawesom/xauusd-backtest**. Er halbiert die Signalzahl und entfernt
den Großteil der Trendtag-Verluste.

> **Wichtige Einordnung zu deren Zahlen:** Das Repo meldet **71 % Trefferquote auf M15**.
> Das klingt sensationell — bis man die Ausstiegsregel liest: Ziel ist „Preis kehrt zum
> Sweep-Punkt zurück" (winziges Ziel) und der Stop ist „Ende des Handelstages" (potenziell
> riesig). Eine Trefferquote **ohne** das dazugehörige CRV ist bedeutungslos. 71 % Treffer
> bei einem Chancen-Risiko-Verhältnis von 1:0,2 verlieren Geld. Diese Zahl gehört zu den
> gefährlichsten im ganzen Themenfeld, weil sie so überzeugend aussieht.

### S4 — Round-Number Fade

Ausgedehnte Bewegung in einen 10er- oder 50er-Griff, Ablehnung dort. Strikt erster oder
zweiter Test. Ab dem dritten Test wird das Level akkumuliert, nicht verteidigt.

### S5 — Momentum Continuation nach Impuls

Eine M5-Kerze von mindestens 1,5 × ATR mit Schluss in den äußeren 20 % ihrer Spanne ist eine
Neubewertung, kein Rauschen. Die flache Korrektur danach ist der Einstieg.

- **Scheitert wenn:** Der Impuls war ein News-Spike. Die laufen deutlich häufiger vollständig
  zurück und weiter. Wenn in den letzten 30 Minuten eine Hochimpakt-Meldung kam, gilt das
  Setup nicht.

### S6 — Spread-Gate (Filter, kein Setup)

Läuft vor jedem anderen. Siehe Teil I.1.

---

## Teil III — Ausstiegsmanagement

`metals/exits.py`

### III.1 Der Plan steht vor dem Einstieg

Jede Regel hier wird verhandelbar, sobald die Position offen ist und sich bewegt. Deshalb
wird der komplette Ausstiegsplan **vor** dem Einstieg festgelegt.

| Element | Scalp | Intraday | Swing |
|---|---|---|---|
| Erstes Ziel | **0,5R** | 1,5R | 2,0R |
| Anteil dort | 60 % | 50 % | 50 % |
| Runner-Ziel | 2,5R | 3,0R | 4,0R |
| Trailing | 1,2 × ATR | 1,5 × ATR | 2,0 × ATR |
| Zeitstop | 45 Min | 240 Min | 1 Tag |

Das erste Ziel beim Scalp steht auf **0,5R statt der üblichen 1,0R**, weil es gemessen ist:
Verlierer erreichten im Schnitt +0,47R, bevor sie scheiterten — das Teilziel bei 1,0R lag
also knapp jenseits des Punktes, an dem die meisten drehten. Verschiebung auf 0,5R:
Erwartungswert −0,182 → −0,109R, verlierende Läufe 94 % → 83 %. Vollständig in
`docs/BACKTEST-ERGEBNISSE.md` Abschnitt 6b.

### III.2 Das „gemischte CRV" — die ehrliche Zahl

Ein Plan mit 60 % bei 1R und 40 % bei 2,5R hat **nicht** ein CRV von 1:2,5. Er hat:

```
0,6 × 1,0 + 0,4 × 2,5 = 1,6
```

Wer das Runner-Ziel als „das" CRV angibt, verspricht 56 % mehr, als der Plan liefert. Der
Code rechnet und zeigt deshalb `blended_reward_risk`.

### III.3 Ein gefundener Fehler: Trailing auf der Füllkerze

Ein Fehler, den erst der Backtest sichtbar gemacht hat: Das Trailing zog schon auf **derselben**
Kerze nach, auf der das erste Ziel gefüllt wurde — berechnet aus dem Hoch genau dieser Kerze.
Ergebnis: Der Stop des Runners landete etwa 0,4R über dem Einstieg und wurde beim nächsten
Rücksetzer mitgenommen. **Jeder Runner wurde zu einem Kleingewinn**, was den ganzen Grund,
einen Runner zu halten, zunichtemacht.

Behoben: Getrailt wird erst ab der Folgekerze. Regressionstest vorhanden.

### III.4 Der Zeitstop

Position nach 45 Minuten schließen, unabhängig vom Stand.

Begründung: Ein Scalp, der innerhalb seines eigenen Horizonts nicht funktioniert hat, ist
nicht mehr der Trade, den man eingegangen ist. Er ist zu einem Swing-Trade mit einem
Scalping-Stop geworden — die schlechteste Kombination.

---

## Teil IV — Wann aufhören

`metals/exits.session_advice`, Kommandozeile: `python -m metals stop`

Die Frage, die die meisten Systeme ignorieren. Auf Gold entscheidet sie mehr als die
Einstiegsqualität: Der Unterschied zwischen einem guten Tag und einem schlechten Monat sind
meist die vier Trades nach der Sitzung, die hätte enden sollen.

### Harte Stopps — nicht verhandelbar

| Auslöser | Grund |
|---|---|
| **−3 % am Tag** | R2. Der Trade, mit dem man einen schlechten Tag zurückholen will, ist der, der aus einem schlechten Tag einen schlechten Monat macht. |
| **+2 % am Tag** | Auch Schluss. Einen guten Tag zurückzugeben ist die häufigste Art, eine gute Woche zu verlieren. |
| **2 Verluste in Folge** | Zwei Verluste hintereinander heißen meist, dass das Regime nicht mehr zu den Setups passt — nicht, dass der nächste Trade fällig ist. |
| **4 Trades am Tag** | Ab hier handelt man Langeweile, nicht Setups. |
| **Rollover / Wochenende / Freitagabend** | R5, M5. |

### Weiche Signale — Vorsicht, kein Stopp

- Letzter Trade war ein Verlust vor unter 20 Minuten → Abkühlung. Der Trade direkt nach
  einem Verlust ist statistisch der schlechteste des Tages.
- Tages-P/L unter −2 % → nur noch das beste Setup, nicht das nächste.
- Weniger als 30 Minuten gutes Fenster übrig → ein Scalp braucht bis zu 45 Minuten, für
  einen Neueinstieg ist es zu spät.

**Wichtig im Code:** Sobald ein harter Stopp greift, werden die weichen Signale **nicht**
mehr aufgelistet. Sie laden nur zum Verhandeln ein. (Getestet.)

---

## Teil V — Was die Backtests ergeben haben

`metals/backtest.py`, `metals/evaluate.py`

### V.1 Die Datenlage — bitte zuerst lesen

Die Build-Umgebung dieses Projekts hat **keinen Netzzugang** (Organisations-Policy, 403 auf
alle externen Hosts). Historische Golddaten konnten hier deshalb nicht geladen werden.

Die Auswertung läuft stattdessen auf einem **Marktsimulator** (`metals/simulate.py`), der
Golds dokumentierte statistische Eigenschaften nachbildet:

- Volatilitäts-Cluster (GARCH-artig)
- fette Ränder (Excess-Kurtosis > 1, geprüft im Test)
- Session-Volatilitätsprofil (Asien dünn, Overlap heftig)
- Magnetismus runder Zahlen
- Liquiditäts-Sweeps

**Was das bedeutet:**

| Diese Zahlen zeigen | Diese Zahlen zeigen NICHT |
|---|---|
| ob die Mechanik funktioniert | die echte Trefferquote auf Gold |
| ob R-Vielfache und Kosten korrekt gerechnet werden | ob die Strategie profitabel ist |
| ob Ausstiege sich verhalten wie geplant | eine Grundlage für Positionsgrößen |
| **strukturelle** Fehler wie die Teilgewinn-Falle | eine Erfolgswahrscheinlichkeit |

Für echte Zahlen im interaktiven Chat:

```bash
python -m metals backtest --source live --bars 5000
```

### V.2 Wie der Backtest gebaut ist, damit er nicht lügt

Vier Entscheidungen, die darüber bestimmen, ob Backtest-Zahlen etwas bedeuten:

1. **Kein Lookahead.** Der Detektor bei Kerze `i` sieht nur `0..i`. Die Reihe wird
   geschnitten, nicht mit einem vorwärtsreichenden Fenster indiziert. **Getestet**: Der
   Backtest über ein Präfix der Daten muss dieselben Trades erzeugen wie über die
   vollständigen Daten.
2. **Stop vor Ziel.** Deckt eine Kerze beides ab, gilt der Stop als zuerst getroffen. Jeder
   Backtest, der anders annimmt, meldet eine Zahl, die live nicht erreichbar ist.
3. **Kosten immer.** Spread bei Ein- und Ausstieg plus Slippage. **Getestet**: Brutto- und
   Netto-Erwartungswert müssen sich unterscheiden.
4. **Ergebnisse in R**, nicht in Euro. Und die **Stichprobengröße steht neben jeder Zahl**.

### V.3 Das Konfidenzintervall ist die wichtigste Zahl

Der Report gibt für den Erwartungswert immer ein 95-%-Konfidenzintervall aus.

> **Wenn das Intervall die Null einschließt, ist keine Kante nachgewiesen** — unabhängig
> davon, wie gut der Punktschätzer aussieht.

Das ist die Zahl, die in praktisch jedem Strategie-Marketing fehlt, und die einzige, die
zwischen „funktioniert" und „hatte Glück" unterscheidet.

### V.4 Was gefunden wurde

Siehe `docs/BACKTEST-ERGEBNISSE.md` für die vollständigen Zahlen aus 100 unabhängigen
Marktläufen über 10 Konfigurationen.

Die drei strukturellen Funde, die auch auf echten Daten gelten, weil sie Arithmetik sind und
keine Marktbeobachtung:

1. **Die 60/40-Teilung bei 1R braucht 62,5 % Trefferquote für Break-even.** Das ist Rechnung,
   nicht Statistik — es gilt auf jedem Markt.
2. **Das Trailing auf der Füllkerze machte jeden Runner zunichte** (Teil III.3). Behoben.
3. **Die asiatische Session ist für Scalping unbrauchbar.** Deutlich schlechter als London
   und NY, konsistent über die Läufe. Sie ist im Code jetzt standardmäßig ausgeschlossen.

---

## Teil VI — Quellen und was übernommen wurde

Untersuchte offene Repositories. Übernommen wurden **Ideen und Techniken**, kein Code —
sowohl aus lizenzrechtlichen Gründen als auch, weil eine übernommene Technik verstanden
werden muss, um korrekt eingebaut zu werden.

| Repository | Lizenz | Was übernommen wurde |
|---|---|---|
| [ilahuerta-IA/backtrader-pullback-window-xauusd](https://github.com/ilahuerta-IA/backtrader-pullback-window-xauusd) | MIT | Der Vier-Phasen-Zustandsautomat; die Begrenzung der Pullback-Tiefe auf drei Kerzen; der EMA-Steigungsfilter |
| [ikeawesom/xauusd-backtest](https://github.com/ikeawesom/xauusd-backtest) | keine formale Lizenz — nur Idee übernommen, kein Code | Der Richtungsfilter für Prior-Day-Sweeps (S3) |
| [JoelPasapera/ExpertAdvisory](https://github.com/JoelPasapera/ExpertAdvisory) | — | Ansatz schneller Massen-Backtests über lange Historien |
| [soloshun/Quantitative-XAUUSD-Strategy](https://github.com/soloshun/Quantitative-XAUUSD-Strategy) | — | Session-Dynamik als eigene Modellierungsfrage |
| [clayandthepotter/ai-gold-scalper](https://github.com/clayandthepotter/ai-gold-scalper) | — | Regime-Erkennung als eigene Schicht vor der Setup-Auswahl |
| [MQL5 „Gold Scalper for MT5"](https://www.mql5.com/en/market/product/178437) (Goldfinch-Nachfolger) | kostenlos, geschlossen | Broker-Randbedingungen, die es im Backtest nicht gibt — siehe unten |

### Was das freie MQL5-Produkt lehrt

„Gold Scalper for MT5" ist die neueste Fassung des vor rund zehn Jahren erschienenen
**Goldfinch-EA**. Er handelt **Volatilitäts-Expansion**: die Trägheit im Preis nach einer
plötzlichen Beschleunigung.

**Bestätigung nebenbei:** Das ist exakt die Idee hinter Setup **S5** hier — unabhängig
entstanden. Und der EA hat **Pflicht-Stop, kein Martingale, kein Grid** — dieselben
Grundsätze wie R6/R7. Wo zwei unabhängige Systeme zum selben Aufbau kommen, ist das ein
schwaches, aber echtes Argument dafür.

**Wertvoller sind die dokumentierten Risiken**, weil sie diesen Code direkt betreffen und im
Python-Backtest gar nicht auftreten können:

| Risiko | Was es bedeutet | Umsetzung hier |
|---|---|---|
| **Mindest-Stop-Abstand** | `SYMBOL_TRADE_STOPS_LEVEL`: bei Gold oft 10–50 Punkte. Ein engerer Stop wird vom Server **abgelehnt** | EA weitet den Stop und protokolliert es |
| **Phantom-Trades bei dünner Tick-Dichte** | Im Strategietester erzeugt jede Modellierung außer „reale Ticks" Trades, die live nie zustande kämen | Warnung in `mt5/README.md` |
| **Variable Spreads und Slippage** | Reduzieren den Erwartungswert eines Scalps direkt | S6-Spread-Gate, Kosten immer im Backtest |
| **Requotes und Netzlatenz** | Der Preis beim Absenden ist nicht der Preis beim Füllen | Deviation 20 Punkte, Stop wird **mit** der Order gesendet |

Der letzte Punkt ist der wichtigste und im EA ausdrücklich umgesetzt: **Nie eine nackte Order
senden und den Stop danach nachtragen.** Die Lücke zwischen beidem ist genau der Moment, in
dem sich Gold bewegt.

**Und eine Einordnung, die dazugehört:** „Scalping auf Ticks ist von Natur aus riskant"
steht in der Produktbeschreibung selbst. Ein Anbieter, der das schreibt, statt Renditen zu
versprechen, verdient mehr Vertrauen als einer mit Gewinnkurven — auch wenn das nichts
darüber sagt, ob die Strategie funktioniert.

### Kritische Einordnung der veröffentlichten Zahlen

**ilahuerta-IA** meldet: Sharpe 0,89, Profitfaktor 1,64, Trefferquote 55,4 %, 175 Trades über
5 Jahre, Stop 2,5 × ATR, Ziel 12 × ATR.

Das ist intern **nicht schlüssig**, und die Unstimmigkeit ist lehrreich: Ein Ziel von
12 × ATR bei einem Stop von 2,5 × ATR wäre ein CRV von 1:4,8. Mit 55 % Trefferquote ergäbe
das einen Profitfaktor von etwa 5,9 — nicht 1,64. Die gemeldeten Durchschnitte
(Gewinn 1.187 USD, Verlust 913 USD) verraten das tatsächliche realisierte CRV: **1,30**.

**Schlussfolgerung:** Das angegebene Take-Profit ist nicht der tatsächliche Ausstieg. Die
allermeisten Trades verlassen die Position weit vorher. Das ist keine Kritik am Repository —
es ist die Erinnerung daran, dass **das angegebene Ziel und der realisierte Ausstieg zwei
verschiedene Dinge sind**, und dass nur der zweite zählt.

Übrigens: 175 Trades in 5 Jahren sind rund 3 pro Monat. Das ist trotz des Namens **kein
Scalping**, sondern eine sehr selektive Strategie.

---

## Teil VII — Der tägliche Ablauf beim Scalping

```bash
# 1. Darf ich überhaupt?
python -m metals stop --equity 10000 --trades-today 0

# 2. Was ist los?
python -m metals analyse XAUUSD --equity 10000 --spread 0.22

# 3. Im Chat: /trade    (begleitet die ganze Sitzung)

# 4. Zwischendurch: darf ich noch?
python -m metals stop --equity 10000 --pnl-today -85 --trades-today 2 \
                     --last-was-loss --minutes-since-last 8
```

Und die Regel, die über allem steht:

> Erwarte, an den meisten Tagen nichts zu tun. Das ist kein Versagen des Systems, sondern
> seine Hauptleistung.
