# Micro-Scalping: „Gewinn sofort mitnehmen, neu aufmachen"

Die Strategie, die der Nutzer beschrieben hat, wörtlich:

> Der Bot analysiert den Chart, macht ein oder mehrere 0,1-Trades je nachdem wie viel auf
> dem Konto ist, sobald er sieht es ist im Plus schließt er es wieder und macht einen neuen
> auf. So mache ich eigentlich fast immer plus, weil es nur kurz rein kurz raus ist.

Dieses Dokument nimmt sie ernst: implementiert in `metals/microscalp.py`, gemessen über
hunderte unabhängige Märkte, mit Parametersuche. Kein Gegenargument — eine Messung.

---

## Warum sie sich von innen richtig anfühlt

**Sie funktioniert die meiste Zeit. Das ist keine Täuschung.**

Die Trefferquote liegt gemessen bei **99,6 %**. Fast jeder Trade schließt im Plus — und zwar
notwendigerweise, denn ein Trade wird ja nur dann geschlossen, wenn er im Plus *ist*. Die
Rückmeldung, die man beim Handeln bekommt, ist deshalb fast durchgehend positiv.

Was diese Anordnung tut, ist die Verluste aus der Trefferquote heraus- und an zwei Stellen
hineinzuschieben, wo man sie nicht sieht:

**1. In den Schwanz.** Eine Position, die nicht zurückkommt, wird nie geschlossen. Sie ist
deshalb kein „Verlust" in der Statistik — sie ist eine offene Position. Unsichtbar bleibt
sie bis zum Margin Call, und dann ist sie der einzige Trade, der zählte.

**2. In die Margin.** Mehrere 0,1-Lot-Positionen auf einem kleinen Konto binden fast die
gesamte freie Margin. Der Stop-out des Brokers kommt dann lange vor der eigenen
Einschätzung. `metals/microscalp.py` modelliert das ausdrücklich, weil es der Mechanismus
ist, der das Konto tatsächlich beendet.

---

## Was die Messung zeigt

Simulator: 1-Minuten-Kerzen mit Golds dokumentierten Eigenschaften (Volatilitäts-Cluster,
fette Ränder, Session-Profil). Geprüft: Lag-1-Autokorrelation der 1m-Renditen **−0,012** —
also praktisch ein Random Walk, keine künstliche Mean-Reversion, die das Ergebnis
schönrechnen würde.

Konfiguration wie beschrieben: 0,1 Lot, bis zu 3 Positionen, Gewinnmitnahme 0,10 USD/oz über
Einstieg, **kein Stop**, Spread 0,30 USD/oz. Kontogroesse variiert — sie stellte sich
als die entscheidende Variable heraus.

### Zuerst die Korrektur, die alles verschoben hat

Die erste Messreihe lief mit **Hebel 1:100 auf einem 1.000er-Konto** und ergab ein
vernichtendes Bild: Median −78 %, 85 % Broker-Stop-out. Diese Konfiguration ist für
EU-Kleinanleger aber **gar nicht zulässig**.

Gold ist nach den ESMA-Regeln, die die Mitgliedstaaten übernommen haben, für Privatkunden
auf **1:20** begrenzt. Damit gilt:

| Hebel | Margin je 0,1 Lot Gold | drei Positionen |
|---|---:|---:|
| 1:500 (offshore) | 90 | 270 |
| 1:100 | 450 | 1.350 |
| **1:20 (EU-Privatkunde)** | **2.250** | **6.750** |

**Auf einem 1.000er-Konto lässt sich unter EU-Recht keine einzige 0,1-Lot-Position
eröffnen.** Das ist keine Strategiefrage, sondern eine Kontogröße — und es kommt vor jeder
anderen Überlegung.

Bei richtigem Hebel und ausreichendem Konto sieht dieselbe Strategie völlig anders aus:

| Konto | Dauer | Treffer | Median | Stop-out | halbiert |
|---:|---:|---:|---:|---:|---:|
| 5.000 | 2.000 Bars | 99,6 % | +17,8 % | 0 % | 0 % |
| 5.000 | 40.000 Bars | 99,9 % | +97,7 % | **35 %** | 10 % |
| 20.000 | 40.000 Bars | 100,0 % | +28,8 % | 0 % | 0 % |
| 100.000 | 40.000 Bars | 100,0 % | +5,8 % | 0 % | 0 % |

**Nicht die Strategie war ruinös, sondern die Positionsgröße im Verhältnis zum Konto.**
0,1 Lot sind auf 100.000 eine Randnotiz, auf 5.000 eine Wette und auf 1.000 unmöglich.

Und die Kehrseite steht in derselben Tabelle: Je größer das Konto, desto kleiner der
Prozentertrag — von +97,7 % auf +5,8 %. Wer die Rendite hochhalten will, muss die Position
relativ zum Konto vergrößern, und genau das bringt den Stop-out zurück. Das ist kein
Detail, sondern der Kern: **Ertrag und Ruinrisiko sind hier dieselbe Stellschraube.**

---

## Die Parametersuche — und warum ihr Sieger nicht zählt

120 Konfigurationen (Gewinnziel × Stop × Richtung × Anzahl Positionen), je 25 Märkte über
8.000 Bars. **37 von 120 hatten einen positiven Median.** Die besten sahen so aus:

| Ziel | Stop | Richtung | Pos | Treffer | Median | Stop-out |
|---:|---:|---|---:|---:|---:|---:|
| 1,0 | keiner | fade | 3 | 99,4 % | **+1120 %** | 28 % |
| 1,0 | 10 | fade | 3 | 92,0 % | +1077 % | 0 % |
| 0,05 | keiner | follow | 3 | 99,6 % | **−78 %** | 88 % |

**Diese +1120 % sind kein Ergebnis, sondern eine Warnung.** Drei Prüfungen, warum:

**1. Horizont-Test — bestanden.** Anders als die Ausgangskonfiguration wächst diese mit der
Zeit (+365 % bei 2.000 Bars → +3.132 % bei 50.000). Kein aufgeschobener Verlust.

**2. Misch-Test — durchgefallen.** Wenn man die Reihenfolge der Kerzen mischt (gleiche
Verteilung, gleiche Kerzenform, zerstörte Autokorrelation), fällt das Ergebnis von +1120 %
auf +424 %. **Rund die Hälfte der „Kante" ist die schwache Mean-Reversion des Simulators**
(Lag-1-Autokorrelation −0,005). Echtes Gold hat auf Minutenbasis nach Kosten keine
ausnutzbare Mean-Reversion — sonst hätten Hochfrequenzhäuser sie längst wegarbitriert.

**3. Spread-Test — bestanden.** Das Ergebnis fällt monoton mit dem Spread und kippt bei 3,0
USD/oz ins Minus. Die Kosten werden also korrekt belastet, das Modell ist an dieser Stelle
sauber.

Was nach dem Misch-Test übrig bleibt, ist kein Handelsvorteil, sondern ein
**Buchhaltungseffekt**: Gewinne werden laufend realisiert, Verluste bleiben in maximal drei
offenen Positionen unrealisiert und werden erst am Ende bewertet. In einem endlichen Fenster
sieht das aus wie eine steigende Kurve. Genau so entstehen die Monate, in denen ein
Grid-System „funktioniert".

> **Merksatz aus dieser Suche:** Wenn eine Parametersuche über 120 Varianten einen Sieger mit
> +1120 % ausspuckt, ist die erste Frage nicht „wie setze ich das ein", sondern „was stimmt
> an meiner Messung nicht". In diesem Fall: die Hälfte war der Simulator, der Rest die
> Buchführung.

---

## Warum kein Stop das Entscheidende ist

Ohne Stop ist der Verlust je Position **unbegrenzt**, bis der Broker eingreift. Der Gewinn
ist auf 0,10 USD/oz gedeckelt. Das Verhältnis von Gewinn zu Risiko ist damit nicht 1:1 oder
1:2, sondern **1:offen**.

Gold bewegt sich pro Stunde typisch 4,5 USD/oz, pro Tag 28 USD/oz. Bei 0,1 Lot (10 Unzen)
sind 28 USD/oz Gegenbewegung ein Verlust von **280 USD** — für einen Gewinn, der 1 USD
betragen hätte. Man braucht **280 Gewinne**, um einen einzigen solchen Tagesverlauf
auszugleichen; bei 99,6 % Trefferquote kommt der Verlierer im Schnitt alle 250 Trades.

Auf einem 100.000er-Konto sind diese 280 USD 0,28 % und damit verkraftbar. Auf 5.000 sind
sie 5,6 %, und dann entscheidet die Reihenfolge der Verlierer über das Konto. **Dieselbe
Strategie, dieselben Regeln, zwei völlig verschiedene Wetten** — der Unterschied ist
ausschließlich die Kontogröße.

---

## Recherche: was dazu bekannt ist

**Scalping-Literatur ist sich beim Stop einig.** Die durchgesehenen Quellen betonen
übereinstimmend, dass ein harter Stop bei Scalping nicht optional ist — mentale Stops seien
wegen der Geschwindigkeit unbrauchbar, professionelle Scalper hängen den Stop sofort bei
Einstieg an. Eine Quelle formuliert die Kernrechnung so: Sobald die Trefferquote von 55 %
auf 45 % fällt *oder ein Stop verpasst wird*, bricht die Mathematik zusammen.

**Die Verwandtschaft zu Martingale und Grid.** Was hier beschrieben ist, ist kein Martingale
(die Positionsgröße wächst nicht nach Verlusten), teilt aber dessen entscheidende
Eigenschaft: das Risiko wird aus vielen kleinen Gewinnen heraus in seltene, große Verluste
verschoben. Die durchgesehenen Darstellungen beschreiben das als „Konzentration des Risikos
in seltenen, aber unvermeidlichen Verlustserien" — bei endlichem Kapital ist die
Ruin-Wahrscheinlichkeit ungleich null.

Ein Unterschied ist wichtig und spricht **für** die beschriebene Variante: Bei festen 0,1
Lot ist das Risiko im Voraus berechenbar, anders als bei Martingale, wo es theoretisch
unbegrenzt ist. Der Nachteil bleibt der fehlende Stop.

---

## Gold vs. Euro — ein eigener Punkt

Die Strategie war für **XAU/EUR** gedacht. Das ist nicht dasselbe Instrument wie XAU/USD,
und für Scalping ist der Unterschied größer, als er aussieht:

**XAUEUR ist ein abgeleitetes Paar.** Es entsteht aus XAUUSD, umgerechnet über EURUSD in
Echtzeit. Wer XAUEUR handelt, hält damit **zwei Positionen gleichzeitig**: eine auf Gold und
eine auf den Euro-Dollar-Kurs. Für eine Strategie, die auf winzige Bewegungen setzt, ist das
zusätzliches Rauschen ohne zusätzlichen Grund.

**Der Spread ist breiter.** XAUUSD trägt über 95 % des weltweiten Spot-Gold-Volumens; XAUEUR
ist deutlich dünner und die Spreads entsprechend weiter. Bei einer Gewinnmitnahme von 0,10
USD/oz ist der Spread nicht ein Kostenfaktor unter mehreren — er ist der dominierende. Ein
um 0,10 breiterer Spread halbiert hier den Ertrag pro Trade.

**Empfehlung:** Wenn diese Strategie getestet wird, dann auf **XAUUSD**. Wer das Konto in
Euro führt, rechnet am Ende um — das ist eine Umrechnung, keine zweite Wette.

---

## Die Grenze dieser ganzen Messung

Alles oben lief auf dem **Simulator**, nicht auf echtem Gold. Der Misch-Test hat gezeigt,
dass ungefähr die Hälfte jeder gefundenen Kante an einer Eigenschaft des Simulators hängt,
die echtes Gold nach Kosten nicht hat.

**Damit ist keine dieser Zahlen eine Aussage über echtes Gold.** Sie sind Aussagen darüber,
wie sich die Strategie *mechanisch* verhält: dass die Trefferquote stimmt, dass Margin und
Stop-out die Grenzen setzen, dass Ertrag und Ruinrisiko dieselbe Stellschraube sind.

Der Test, der die offene Frage beantwortet, ist der auf **heruntergeladener echter
M5-Historie** — siehe [DATENQUELLEN.md](./DATENQUELLEN.md) und
[../mt5/PC-SETUP.md](../mt5/PC-SETUP.md), Tag 1.

---

## Was daraus folgt

Die Strategie ist nicht „falsch". Sie ist eine Wette mit einer sehr hohen Trefferquote und
einem sehr schiefen Ergebnis. Wer sie fährt, sollte wissen, welche der beiden Zahlen für ihn
gilt — und der Median gilt für die meisten.

Zwei Änderungen machen aus ihr etwas, das messbar bleibt, ohne ihren Charakter zu zerstören:

1. **Ein Stop, irgendeiner.** Auch ein weiter Stop macht den Verlust je Trade endlich und
   damit den Erwartungswert überhaupt erst berechenbar.
2. **Eine Position statt mehrerer**, solange das Konto klein ist. Der Stop-out kommt sonst
   aus der Margin, nicht aus dem Markt.

Was beide Änderungen bewirken, steht in der Parametersuche unten — gemessen, nicht behauptet.

---

## Selbst nachrechnen

```bash
# Ein Markt, ausführlich
python -m metals microscalp --bars 8000

# Viele Märkte, die Verteilung
python -m metals microscalp --markets 100 --bars 8000

# Ohne Stop gegen mit Stop
python -m metals microscalp --markets 100 --stop 3.0

# Die vollständige Parametersuche
python -m metals microscalp --train
```

---

## Quellen

**Zur Scalping-Praxis und zum Stop:**
- [Opofinance — High Win Rate Scalping Strategy](https://blog.opofinance.com/en/high-win-rate-scalping-strategy/)
- [TradeZella — 4 Scalping Strategies With Exact Entry and Exit Rules](https://www.tradezella.com/blog/scalping-strategies)
- [TradingSim — Scalp Trading Strategies](https://www.tradingsim.com/blog/scalp-trading-active-investing-strategy)

**Zu Martingale und Grid:**
- [Capital.com — Martingale Trading Strategy: Explanation, Risks](https://capital.com/en-eu/learn/trading-strategies/martingale-trading)
- [AlphaEx Capital — Grid Trading Forex: The Honest Trend-vs-Range Maths](https://www.alphaexcapital.com/forex/forex-trading-strategies/grid-scalping)
- [SteadyPips — Grid Trading vs Martingale](https://steadypips.net/posts/grid-trading-vs-martingale/)

**Zu XAUEUR gegen XAUUSD:**
- [TradingBeasts — XAU/USD vs XAU/EUR: Key Gold Pair Differences](https://tradingbeasts.com/xauusd-vs-xaueur-difference/)
- [Pro-Scalper — XAUUSD vs XAUEUR: Should You Trade Gold in Euros?](https://www.pro-scalper.com/gold-market/xauusd-vs-xaueur)

Sämtlich Broker- und Bildungsseiten, keine begutachtete Forschung — als Hinweise gelesen,
nicht als Belege. Die Zahlen in diesem Dokument stammen aus der eigenen Simulation und sind
mit den Befehlen oben reproduzierbar.
