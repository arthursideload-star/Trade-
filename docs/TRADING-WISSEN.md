# Trading-Wissensbasis

Rechercheergebnis für das Trading-Bot-Projekt.
Stand: 2026-07-25

Dieses Dokument sammelt, was für den Bau des Bots inhaltlich relevant ist: wie im Markt Geld
entsteht, wie man es schnell verliert, was Kerzen und Charts wirklich aussagen, wie man
Gelegenheiten maschinell erkennt und welche Datenquellen angebunden werden sollten.

**Zur Belastbarkeit der Zahlen:** Quellen sind unterschiedlich hart. Ich kennzeichne sie:
- 🎓 **peer-reviewed / akademisch** — belastbar
- 📊 **Regulierungs-/Branchendaten** — belastbar
- 🔶 **Anbieter- oder Blog-Backtest** — plausibel, aber Methodik meist nicht prüfbar, oft
  Marketing-Interesse dahinter. Nicht ungeprüft übernehmen.

---

## Inhaltsverzeichnis

- [Teil I — Wie im Markt überhaupt Geld entsteht](#teil-i--wie-im-markt-überhaupt-geld-entsteht)
- [Teil II — Wie man schnell viel Geld verliert](#teil-ii--wie-man-schnell-viel-geld-verliert)
- [Teil III — Kerzen (Candlesticks) vollständig](#teil-iii--kerzen-candlesticks-vollständig)
- [Teil IV — Charts, Marktstruktur und Chartmuster](#teil-iv--charts-marktstruktur-und-chartmuster)
- [Teil V — Indikatoren](#teil-v--indikatoren)
- [Teil VI — Gute Gelegenheiten erkennen](#teil-vi--gute-gelegenheiten-erkennen)
- [Teil VII — Krypto-spezifische Signale](#teil-vii--krypto-spezifische-signale)
- [Teil VIII — Statistische Validierung](#teil-viii--statistische-validierung)
- [Teil IX — Risiko und Positionsgröße](#teil-ix--risiko-und-positionsgröße)
- [Teil X — Was du verknüpfen solltest](#teil-x--was-du-verknüpfen-solltest)
- [Teil XI — Alpha-Zerfall](#teil-xi--alpha-zerfall-warum-strategien-sterben)
- [Teil XII — Die wichtigsten Erkenntnisse](#teil-xii--die-wichtigsten-erkenntnisse-kompakt)
- [Quellen](#quellen)

---

# Teil I — Wie im Markt überhaupt Geld entsteht

## 1.1 Die vier ehrlichen Quellen von Gewinn

Es gibt nicht viele Möglichkeiten, im Markt systematisch Geld zu verdienen. Jede funktionierende
Strategie lässt sich einer dieser Quellen zuordnen. Wenn du eine Strategie nicht zuordnen kannst,
hast du wahrscheinlich keine Edge, sondern Zufall.

| Quelle | Mechanismus | Wer zahlt dich | Realistisch für einen Solo-Bot? |
|---|---|---|---|
| **Risikoprämie** | Du hältst ein Risiko, das andere loswerden wollen | Der Markt insgesamt | ✅ Ja (z. B. Long-Bias, Basis-Trade) |
| **Liquiditätsprämie** | Du stellst Liquidität, wenn andere sie dringend brauchen | Ungeduldige Marktteilnehmer | ⚠️ Teilweise (Market Making ist hart) |
| **Informationsvorsprung** | Du weißt/verarbeitest etwas schneller oder besser | Die langsamere Gegenseite | ⚠️ Nur in Nischen |
| **Verhaltensanomalie** | Du nutzt systematische Fehler anderer aus | Die Masse der Anleger | ✅ Ja (Momentum, Overreaction) |

**Was keine Quelle ist:** "Ich habe ein Muster gefunden." Ein Muster ohne ökonomische Erklärung,
warum jemand dir dieses Geld gibt, ist in der Regel Kurvenanpassung an die Vergangenheit.

**Praktische Konsequenz für den Bot:** Für jede implementierte Strategie muss in einem Satz
beantwortbar sein: *Wer verliert das Geld, das ich gewinne, und warum macht diese Person das
weiter?* Diese Frage gehört als Kommentar über jede Strategieklasse im Code.

## 1.2 Die Erwartungswert-Formel — das Fundament

```
E = (Trefferquote × Ø-Gewinn) − ((1 − Trefferquote) × Ø-Verlust) − Kosten
```

Nur wenn `E > 0`, verdient das System langfristig. Alles andere ist Nebensache.

**Beispielrechnung, die viele überrascht:**

| Strategie | Trefferquote | Ø-Gewinn | Ø-Verlust | E pro Trade |
|---|---|---|---|---|
| A: "Hohe Trefferquote" | 80 % | 1 R | 5 R | 0,8 − 1,0 = **−0,2 R** ❌ |
| B: "Verliert meistens" | 35 % | 3 R | 1 R | 1,05 − 0,65 = **+0,4 R** ✅ |

Strategie B verliert in zwei von drei Fällen und ist trotzdem deutlich profitabler. Das ist der
Grund, warum Trendfolgesysteme mit 30–40 % Trefferquote funktionieren — und warum
"Trefferquote" als Qualitätsmaß irreführend ist.

**Für den Bot:** Optimiere niemals auf Trefferquote. Optimiere auf Erwartungswert nach Kosten,
und bewerte über Profit Factor (`Summe Gewinne / Summe Verluste`) und Sharpe/Sortino.

## 1.3 Die drei Hebel — und der, der alles zerstört

Der Jahresertrag ergibt sich grob aus:

```
Jahresertrag ≈ E pro Trade × Anzahl Trades pro Jahr × Positionsgröße
```

Drei Stellschrauben:
1. **Erwartungswert erhöhen** — schwer, das ist die eigentliche Arbeit
2. **Frequenz erhöhen** — gefährlich, weil Kosten linear mitwachsen
3. **Positionsgröße erhöhen** — gefährlich, weil Drawdowns überproportional wachsen

**Die Falle bei Hebel 2:** Bei 0,1 % Gebühren pro Runde kostet dich 1 Trade/Tag rund **36 % pro
Jahr** an Gebühren. Eine Strategie mit 0,15 % Edge pro Trade ist bei täglichem Handel gerade so
über Wasser — bei stündlichem Handel garantiert insolvent. Frequenz ist kein freier Hebel.

Genau das zeigt die Forschung: Bajgrowicz und Scaillet testeten 7.846 in Fachzeitschriften
publizierte Handelsregeln über mehr als ein Jahrhundert Marktdaten — nach Einrechnung von
Transaktionskosten verschwand praktisch die gesamte Profitabilität. 🎓

## 1.4 Drawdown-Mathematik — warum Verluste asymmetrisch sind

Der wichtigste Zusammenhang im gesamten Risikomanagement:

| Verlust | Nötiger Gewinn zur Erholung |
|---|---|
| −10 % | +11 % |
| −20 % | +25 % |
| −33 % | +50 % |
| −50 % | **+100 %** |
| −75 % | **+300 %** |
| −90 % | **+900 %** |

Formel: `Erholung = 1/(1−D) − 1`

**Konsequenz:** Kapitalerhalt ist kein defensives Gerede, sondern reine Arithmetik. Ein System,
das 15 % Drawdown nie überschreitet, braucht 17,6 % zur Erholung. Ein System bei 60 % Drawdown
braucht 150 % — das schafft praktisch niemand. Die Drawdown-Begrenzung ist deshalb der einzige
Parameter, den man **nicht** optimieren sollte, sondern hart setzt.

---

# Teil II — Wie man schnell viel Geld verliert

Dieser Teil ist ausführlicher als der über Gewinne — weil hier die konkreten, quantifizierten
Erkenntnisse liegen. Verlustursachen sind viel besser dokumentiert als Gewinnquellen.

## 2.1 Die Ausgangszahlen

| Befund | Quelle |
|---|---|
| **74–89 %** der CFD-Privatanleger verlieren Geld | ESMA-Regulierungsdaten 📊 |
| **70–80 %** der Forex-Privatanleger sind unprofitabel | US CFTC 📊 |
| **97 %** der Daytrader, die länger als 300 Tage durchhalten, verlieren Geld | Studie Fundação Getúlio Vargas (Brasilien) 🎓 |
| Backtest-Sharpe erklärte **unter 3 %** der tatsächlichen Live-Performance | Quantopian-Analyse von 888 realen Algorithmen 🔶 |
| **20–50 %** Performance-Einbruch beim Übergang Backtest → Live ist normal | Branchenerfahrung 🔶 |

Der Quantopian-Befund ist für dieses Projekt der wichtigste: Bei 888 real gehandelten Algorithmen
hatte der Backtest-Sharpe **fast keine** Vorhersagekraft für das Live-Ergebnis. Das heißt nicht,
dass Backtesting nutzlos ist — es heißt, dass ein guter Backtest *keine* Evidenz für eine Edge
ist. Er kann nur eine Strategie ausschließen, nicht bestätigen.

## 2.2 Hebel — der schnellste Weg zur Null

Die Liquidationsformel für eine Long-Position (Isolated Margin):

```
Liquidationspreis ≈ Einstiegspreis × (1 − 1/Hebel + Maintenance-Margin-Rate)
```

| Hebel | Abstand zur Liquidation | Praktische Bedeutung |
|---|---|---|
| 2× | ~50 % | Überlebt fast alles |
| 5× | ~20 % | Überlebt normale Korrekturen |
| 10× | **~9,5 %** | Eine schlechte Tageskerze in Krypto |
| 20× | ~4,75 % | Eine Stunde reicht |
| 50× | ~1,9 % | Normales Rauschen liquidiert dich |
| 100× | ~0,95 % | Statistisch eine Frage von Minuten |

**Drei Verstärker, die zusammen tödlich sind:**

1. **Cross vs. Isolated Margin:** Bei Isolated verlierst du nur die zugeteilte Margin. Bei Cross
   haftet dein **gesamtes Kontoguthaben**. Eine einzige Position kann das ganze Konto nehmen.
2. **Wick-Risiko:** Ein Flash-Wick kann deinen Stop-Loss überspringen und direkt zur Liquidation
   führen, wenn Stop und Liquidationspreis nah beieinander liegen. Dein Stop schützt dich nicht,
   wenn kein Gegenpreis existiert.
3. **Averaging Down:** Nachkaufen in eine verlierende gehebelte Position ist laut mehreren
   Auswertungen die häufigste einzelne Ursache für Totalverluste im Privathandel.

**Regel für den Bot:** Phase 1 ohne Hebel (Spot). Hebel ist kein Weg zu mehr Ertrag, sondern ein
Multiplikator auf einen Erwartungswert — bei negativem Erwartungswert beschleunigt er nur den
Ruin.

## 2.3 Die Kostenkaskade — der stille Killer

Was pro Trade tatsächlich abgeht (Krypto Spot, realistische Werte):

| Kostenblock | Typisch | Anmerkung |
|---|---|---|
| Taker-Gebühr | 0,075–0,10 % | Binance/Bybit Basis-Tier |
| Maker-Gebühr | 0,02–0,075 % | teils Rabatt bei Volumen/Token-Zahlung |
| Spread | 0,01–0,05 % | bei Majors; bei Altcoins deutlich mehr |
| Slippage | 0,02–0,20 % | wächst mit Ordergröße und Volatilität |
| **Summe Roundtrip (Taker)** | **~0,2–0,4 %** | Ein- plus Ausstieg |

**Hochgerechnet:**

| Trades/Jahr | Jährliche Kosten (0,25 % Roundtrip) |
|---|---|
| 50 | 12,5 % |
| 200 | 50 % |
| 500 | 125 % |
| 1.000 | 250 % |

Bei 500 Trades im Jahr musst du **125 % Bruttorendite** erwirtschaften, nur um bei null
herauszukommen. Das ist der Grund, warum hochfrequente Retail-Strategien praktisch immer
verlieren — nicht wegen falscher Signale, sondern wegen Reibung.

**Konsequenzen für den Bot:**
- Post-Only-Limit-Orders wo möglich (Maker statt Taker — halbiert die Gebühr)
- Rebalancing statt Schließen-und-Neukaufen bei Signaländerung
- Mindest-Edge-Schwelle: Ein Signal wird nur gehandelt, wenn der erwartete Gewinn die
  Roundtrip-Kosten um mindestens den Faktor 3 übersteigt
- Slippage wird pro Fill gemessen und fließt ins Backtest-Kostenmodell zurück

## 2.4 Strategien mit eingebautem Totalverlust

Diese Bot-Typen sind populär, weil ihre Equity-Kurve monatelang perfekt aussieht — bis sie es
nicht mehr tut.

**Martingale / DCA-Bots:** Kaufen nach jedem Kursrückgang mehr nach, verkaufen bei kleiner
Erholung mit Gewinn. Gewinnt in 95 % der Fälle einen kleinen Betrag. Das Risiko wächst
exponentiell mit jedem Sicherheitsauftrag — bei einem anhaltenden Abwärtstrend skaliert der Bot
die Position genau in die falsche Richtung. Das eine verlorene Prozent der Fälle kostet mehr als
alle Gewinne zusammen.

**Grid-Bots:** Kaufen und verkaufen in einem festgelegten Preisband. Funktionieren gut, solange
der Preis im Band schwankt. Verlassen des Bandes = unbegrenztes Verlustpotenzial nach oben
(Short-Seite) oder eine große verlustreiche Position (Long-Seite).

**Gemeinsame Struktur:** Beide tauschen viele kleine sichere Gewinne gegen einen seltenen großen
Verlust. Das ist ökonomisch das Verkaufen von Versicherungen ohne Rückversicherung. Solche
Strategien sind nicht per se falsch — aber nur mit hartem Ausstiegskriterium und Kenntnis des
maximalen Verlusts. Ohne das sind sie ein verzögerter Totalverlust.

## 2.5 Psychologie — auch bei einem Bot relevant

Man denkt, ein Bot habe keine Psychologie. Der Bot nicht — **du** schon. Die dokumentierten
Verhaltensmuster verlagern sich vom Trading auf das Bot-Management:

| Klassischer Trading-Fehler | Bot-Äquivalent |
|---|---|
| Verluste laufen lassen | Kill-Switch übersteuern, "es dreht sicher wieder" |
| Gewinne zu früh mitnehmen | Bot abschalten nach gutem Monat, "sichern" |
| Revenge Trading | Nach Drawdown Parameter aggressiver stellen |
| Overtrading | Immer mehr Symbole und Strategien aktivieren |
| Overconfidence | Kapital nach 3 guten Wochen verdoppeln |

Die Forschung ist eindeutig: Trader halten Verlustpositionen deutlich länger als Gewinner — der
Schmerz eines realisierten Verlusts wiegt schwerer als die Freude über einen Gewinn
(Dispositionseffekt). 🎓

**Architektonische Gegenmaßnahme:** Limits gehören in den Code und in ein Git-Repository mit
Commit-Historie, nicht in eine Konfigurationsdatei, die man um 3 Uhr nachts ändern kann. Eine
Änderung an Risikoparametern soll einen Commit und einen Deploy erfordern — die Reibung ist
Absicht.

## 2.6 Technische Todesursachen

**Knight Capital, 1. August 2012: 440 Mio. USD Verlust in 45 Minuten.** Ursache: Bei einem
Deployment auf acht Produktionsserver wurde einer nicht aktualisiert. Auf diesem Server startete
ein altes, eigentlich stillgelegtes Modul ("Power Peg") und feuerte Fehlorders in den Markt. Das
Unternehmen war danach faktisch erledigt.

Die Lehren gelten 1:1 für einen Ein-Personen-Bot:

| Lehre | Umsetzung im Projekt |
|---|---|
| Inkonsistentes Deployment tötet | Nur containerisierte Deployments, ein Image, versioniert |
| Alter Code darf nie versehentlich laufen | Feature-Flags entfernen statt deaktivieren; Dead Code löschen |
| Kein automatisches Notaus | Kill-Switch, Order-Rate-Limit, Positions-Obergrenze im Code |
| Keine Trennung Test/Prod | Getrennte API-Keys, getrennte Konten, Testnet-Zwang für Staging |
| Niemand hat es gemerkt | Alerting auf Anomalien — Orderrate, Positionsdrift, PnL-Sprung |

**Weitere klassische Bot-Todesursachen:**
- **Doppelte Orders** nach Netzwerk-Timeout → Lösung: deterministische Client Order IDs
  (Idempotenz)
- **Zustandsverlust beim Neustart** → Bot kennt offene Positionen nicht → Lösung: Abgleich mit
  der Börse vor dem ersten Trade
- **Zeitzonenfehler** → Signale eine Stunde versetzt → Lösung: alles intern UTC
- **API-Rate-Limit-Ban** → Bot ist blind mit offener Position → Lösung: zentrales Token-Bucket
- **Stale Data** → Bot handelt auf eingefrorenem Feed → Lösung: Staleness-Wächter, 30 s ohne
  Tick = kein Handel

## 2.7 Overfitting — der Verlust, der schon vor dem Start feststeht

Das häufigste Scheitern passiert nicht live, sondern im Backtest: Man findet Parameter, die
historisch großartig aussehen und in der Zukunft nichts wert sind.

**Warum es unvermeidlich passiert:** Wer 1.000 Parameterkombinationen testet, findet allein durch
Zufall eine mit Sharpe > 2. Das ist kein Fund, das ist Statistik. Genau dafür wurde die
**Deflated Sharpe Ratio** (Bailey & López de Prado, 2014) entwickelt: Sie korrigiert den
gemessenen Sharpe um die Anzahl der Versuche, um Schiefe und Wölbung der Renditeverteilung und
um die Stichprobenlänge. 🎓

**Praktische Regeln:**
- Anzahl aller getesteten Varianten protokollieren — auch der verworfenen
- Parametersensitivität prüfen: Bricht das Ergebnis bei ±20 % Parameteränderung ein, ist es
  Kurvenanpassung
- Weniger Parameter ist fast immer besser als mehr
- Out-of-Sample-Daten wirklich unangetastet lassen (nicht "nochmal kurz nachschauen")

## 2.8 Liquidationskaskaden — das strukturelle Risiko in Krypto

Eine Liquidation ist die Zwangsschließung einer Position. Eine **Kaskade** ist, wenn diese
Zwangsverkäufe den Preis so weit bewegen, dass sie die nächste Liquidationsstufe auslösen —
selbstverstärkend.

**Aufbau des Risikos, erkennbar an drei Kennzahlen gleichzeitig:**
1. Open Interest auf Rekordniveau (viel Hebel im System)
2. Funding Rate extrem (> 0,1 % pro 8h-Periode gilt als überhitzt)
3. Liquidations-Heatmap zeigt Cluster dicht unter/über dem aktuellen Preis

Wenn alle drei zusammenkommen, reicht eine Preisbewegung von ~1 % gegen die überfüllte Seite,
um erzwungene Verkäufe auszulösen. Ein einzelnes Signal davon ist deutlich schwächer als die
Kombination.

**Für den Bot doppelt relevant:** als Risikofilter (bei extremen Werten Position verkleinern oder
pausieren) und als Signalquelle (Kaskaden erzeugen Überreaktionen, die mean-reverten).

---

# Teil III — Kerzen (Candlesticks) vollständig

## 3.1 Was eine Kerze tatsächlich kodiert

Eine Kerze ist eine verlustbehaftete Kompression: Aus tausenden Einzeltrades in einem Zeitfenster
werden vier Zahlen — Open, High, Low, Close — plus Volumen.

```
        │ ← High (höchster gehandelter Preis)
      ┌─┴─┐
      │   │ ← Body: Open bis Close
      │   │   grün/weiß: Close > Open
      └─┬─┘   rot/schwarz: Close < Open
        │ ← Low (niedrigster gehandelter Preis)
```

**Was die einzelnen Teile aussagen:**

| Element | Bedeutung |
|---|---|
| **Body-Größe** | Netto-Durchsetzungskraft einer Seite. Großer Body = klare Richtung |
| **Oberer Docht** | Preis war oben, wurde aber zurückgewiesen → Verkäufer aktiv |
| **Unterer Docht** | Preis war unten, wurde zurückgewiesen → Käufer aktiv |
| **Body/Range-Verhältnis** | Entscheidungsfreude. Nahe 1 = Trend, nahe 0 = Unschlüssigkeit |
| **Close-Position in der Range** | Die aussagekräftigste Einzelgröße. Close am Hoch = Käufer haben das letzte Wort |

**Was eine Kerze nicht kodiert und was oft übersehen wird:**
- Die **Reihenfolge** innerhalb der Kerze. Eine Kerze mit Docht oben und unten kann erst
  gestiegen, dann gefallen sein — oder umgekehrt. Völlig verschiedene Bedeutungen, identische
  Kerze.
- Das **Volumenprofil** innerhalb der Kerze — wo tatsächlich gehandelt wurde
- Die **Anzahl und Größe der Trades** — 1 großer Trade oder 10.000 kleine sehen gleich aus

**Konsequenz für den Bot:** Wenn du Tick-Daten hast, nutze sie. Auf der 1m-Ebene ist die
Reihenfolge innerhalb der 15m-Kerze rekonstruierbar. Das ist ein Informationsvorteil gegenüber
jedem, der nur die 15m-Kerze anschaut.

## 3.2 Kerzentypen jenseits von Zeit

Die Standard-Zeitkerze (1m, 1h, 1d) ist eine Konvention, keine Naturgesetzmäßigkeit. Sie hat
einen konkreten statistischen Nachteil: In ruhigen Phasen enthält eine 1h-Kerze fast keine
Information, in hektischen Phasen komprimiert sie zu viel. Die Renditeverteilung von Zeitkerzen
ist dadurch stark nicht-normal.

| Kerzentyp | Neue Kerze entsteht bei... | Vorteil |
|---|---|---|
| **Time Bars** | Zeitablauf | Standard, überall verfügbar, einfach |
| **Tick Bars** | N Trades | Aktivitätssynchron |
| **Volume Bars** | N gehandelten Einheiten | Renditen deutlich näher an Normalverteilung |
| **Dollar Bars** | N gehandeltem Volumen in USD | Robust gegen Preisänderungen über Zeit — bester Allrounder für ML |
| **Imbalance Bars** | Ungleichgewicht Käufer/Verkäufer überschreitet Schwelle | Reagiert auf informierte Handelsaktivität |
| **Renko** | Preisbewegung um N | Filtert Zeitrauschen komplett heraus |
| **Heikin Ashi** | geglättete Zeitkerze | Trendsichtbarkeit, aber **verzerrt Preise** — nie für Ein-/Ausstiegspreise verwenden |

**Empfehlung für den Bot:** Zeitkerzen als Basis (für Kompatibilität und Vergleichbarkeit),
zusätzlich **Dollar Bars** als Eingabe für ML-Modelle. Die Forschung zu informationsgetriebenen
Bars in Verbindung mit Triple-Barrier-Labeling und Deep Learning zeigt hier messbare Vorteile
gegenüber reinen Zeitkerzen. 🎓

## 3.3 Einzelkerzen-Muster

| Muster | Form | Klassische Deutung | Reale Aussagekraft |
|---|---|---|---|
| **Doji** | Open ≈ Close, Dochte beidseitig | Unentschlossenheit | Nur relevant nach klarem Trend und an einem Level. Isoliert wertlos |
| **Long-Legged Doji** | Sehr lange Dochte beidseitig | Hohe Unsicherheit | Volatilitätsexpansion — als Vola-Feature nützlicher denn als Richtungssignal |
| **Dragonfly Doji** | Langer unterer Docht, kein oberer | Bullische Umkehr | Zurückweisung tieferer Preise. Braucht Level-Kontext |
| **Gravestone Doji** | Langer oberer Docht, kein unterer | Bärische Umkehr | Spiegelbild, gleiche Einschränkung |
| **Hammer** | Kleiner Body oben, langer unterer Docht (≥ 2× Body) | Bullische Umkehr nach Abwärtstrend | Eines der besser dokumentierten Muster — **nur** am Ende eines Abwärtstrends |
| **Hanging Man** | Formgleich mit Hammer, aber nach Aufwärtstrend | Bärische Warnung | Identische Form, gegenteilige Deutung — zeigt, dass Kontext alles ist |
| **Inverted Hammer** | Kleiner Body unten, langer oberer Docht | Bullische Umkehr nach Abwärtstrend | Schwächer als Hammer |
| **Shooting Star** | Wie Inverted Hammer, nach Aufwärtstrend | Bärische Umkehr | Brauchbar an Widerständen |
| **Marubozu** | Fast kein Docht, großer Body | Volle Dominanz einer Seite | Gutes Momentum-**Feature**, schlechtes Umkehrsignal |
| **Spinning Top** | Kleiner Body, Dochte beidseitig | Gleichgewicht | Kompressions-Indikator |

**Der zentrale Punkt:** Hammer und Hanging Man sind **exakt dieselbe Kerze**. Bullisch oder
bärisch entscheidet allein, was davor passiert ist. Das gilt für praktisch alle Umkehrmuster.
Ein Bot, der Kerzenmuster ohne Trendkontext erkennt, erkennt nichts.

## 3.4 Zwei-Kerzen-Muster

| Muster | Bedingung | Deutung |
|---|---|---|
| **Bullish Engulfing** | Rote Kerze, dann grüne, deren Body die vorige komplett umschließt | Käufer übernehmen. Eines der statistisch stärksten Muster |
| **Bearish Engulfing** | Spiegelbild | Verkäufer übernehmen |
| **Bullish Harami** | Große rote Kerze, dann kleine grüne komplett innerhalb | Verkaufsdruck lässt nach. Schwächer als Engulfing |
| **Bearish Harami** | Spiegelbild | — |
| **Piercing Line** | Rote Kerze, dann grüne, die über 50 % der roten schließt | Bullische Umkehr |
| **Dark Cloud Cover** | Spiegelbild | Bärische Umkehr |
| **Tweezer Bottom/Top** | Zwei Kerzen mit fast identischem Low bzw. High | Level-Bestätigung — eigentlich Support/Resistance, nicht Kerzenmuster |

## 3.5 Drei-Kerzen-Muster

| Muster | Bedingung | Deutung |
|---|---|---|
| **Morning Star** | Große rote, kleine unentschlossene, große grüne | Klassisches Boden-Muster |
| **Evening Star** | Spiegelbild | Klassisches Top-Muster |
| **Three White Soldiers** | Drei aufeinanderfolgende große grüne Kerzen mit höheren Closes | Starkes Momentum. Oft aber bereits zu spät für Einstieg |
| **Three Black Crows** | Spiegelbild | — |
| **Three Inside Up** | Bullish Harami plus Bestätigungskerze | In Backtests wiederholt unter den besten Mustern 🔶 |
| **Three Inside Down** | Spiegelbild | — |
| **Tri-Star** | Drei aufeinanderfolgende Dojis | Sehr selten; hohe "Bestätigungsrate", aber niedriger Erwartungswert |

## 3.6 Was die Statistik wirklich sagt

Hier wird es interessant — und ernüchternd.

**Akademische Basis:** Lo, Mamaysky und Wang (Journal of Finance, 2000) entwickelten eine
algorithmische Mustererkennung mit Kernel-Regression und testeten sie systematisch. Ergebnis:
Einige technische Muster tragen in großen Stichproben **statistisch signifikante
Zusatzinformation**. Die Profitabilität hängt jedoch von Kosten und Umsetzung ab. 🎓 Das ist die
bis heute seriöseste Bestätigung, dass technische Muster nicht reines Rauschen sind — aber auch
keine Goldgrube.

**Was Backtests von Anbietern zeigen:** 🔶

| Befund | Einordnung |
|---|---|
| Isolierte Muster: **50–55 %** Trefferquote | Kaum besser als Münzwurf — das ist die ehrlichste Zahl |
| Mit Trendfilter, Volumenbestätigung und Level-Kontext: **60–70 %** | Der Kontext liefert die Edge, nicht das Muster |
| Von 75 getesteten Mustern: nur **12** mit Profit Factor > 1,5 | 84 % der Muster sind wertlos |
| Bestes Einzelmuster ~12,9 % CAGR über 25 Jahre | Klingt gut, ist aber ein einzelner Datenpunkt aus vielen Versuchen |
| Tri-Star: 83 % "Bestätigungsrate", aber nur 34 % erreichen 2:1 CRV, Erwartungswert 0,032 | Perfektes Beispiel für die Trefferquoten-Falle aus Abschnitt 1.2 |

**Die zwei entscheidenden Schlüsse:**

1. **Das Muster ist nicht die Edge — der Kontext ist die Edge.** Der Sprung von 52 % auf 65 %
   kommt fast vollständig von Trendfilter, Volumen und Preislevel. Das Kerzenmuster ist nur der
   Auslöser für das Timing.
2. **Die Zahlen aus Anbieter-Backtests sind mit Vorsicht zu behandeln.** Wer 75 Muster testet und
   die besten 10 veröffentlicht, betreibt genau die Selektionsverzerrung, die die Deflated
   Sharpe Ratio korrigieren soll. Die "besten 10 von 75" sind größtenteils Zufallsauswahl.

**Für den Bot heißt das konkret:** Kerzenmuster nicht als Signalgeber implementieren, sondern
als **Features unter vielen** in einem Ensemble. Ihr Beitrag wird vom Modell gelernt, nicht von
dir gesetzt.

## 3.7 Kontextregeln — was aus einem Muster ein Signal macht

Ein Kerzenmuster ist nur handelbar, wenn mehrere dieser Bedingungen erfüllt sind:

| Bedingung | Warum |
|---|---|
| **Am Level** | Muster mitten im Nirgendwo bedeuten nichts. An getestetem Support/Resistance, POC, VWAP oder Vortageshoch bedeuten sie etwas |
| **Im richtigen Trendkontext** | Umkehrmuster brauchen einen vorangegangenen Trend zum Umkehren |
| **Mit Volumenbestätigung** | Ein Engulfing bei doppeltem Durchschnittsvolumen ist ein anderes Ereignis als bei halbem |
| **Relative Größe** | Die Kerze muss relativ zur aktuellen ATR groß sein. Ein "großer Body" in einer ruhigen Phase ist ein kleiner Body in einer volatilen |
| **Mit Higher-Timeframe-Ausrichtung** | Ein 15m-Kaufsignal gegen einen intakten 4h-Abwärtstrend hat deutlich schlechtere Statistik |
| **Nach Liquiditätsereignis** | Muster direkt nach einem Stop-Run/Docht durch ein offensichtliches Level sind aussagekräftiger |

## 3.8 Kerzen im Code — Features statt Muster

Der praktische Ansatz: Statt 75 Muster-Detektoren zu programmieren, kodiere die zugrunde liegende
Information als kontinuierliche, normierte Features. Das Modell findet die Muster selbst — und
findet auch die, die keinen Namen haben.

```python
# Kontinuierliche Kerzen-Features (alle ATR- bzw. range-normiert)
body_ratio        = (close - open) / (high - low)      # Richtung + Entschlossenheit
upper_wick_ratio  = (high - max(open, close)) / (high - low)
lower_wick_ratio  = (min(open, close) - low) / (high - low)
close_position    = (close - low) / (high - low)       # 0 = am Tief, 1 = am Hoch
range_vs_atr      = (high - low) / atr_14              # relative Größe
body_vs_atr       = abs(close - open) / atr_14
gap_from_prev     = (open - prev_close) / atr_14
volume_zscore     = (volume - vol_mean_20) / vol_std_20
```

**Warum das besser ist als Muster-Detektoren:**
- Keine willkürlichen Schwellen ("Docht muss 2× Body sein" — warum 2 und nicht 1,8?)
- Kein Informationsverlust durch Binärisierung
- Ein Modell kann Interaktionen finden (langer unterer Docht **und** hohes Volumen **und**
  niedriger RSI), die kein benanntes Muster abbildet
- Weniger Code, weniger Bugs, weniger Overfitting-Oberfläche

Benannte Muster können zusätzlich als Binär-Features mitlaufen (`is_bullish_engulfing`) — als
Ergänzung, nicht als Kern.

---

# Teil IV — Charts, Marktstruktur und Chartmuster

## 4.1 Marktstruktur — das Fundament unter allem

Bevor irgendein Muster zählt, muss der Zustand klar sein. Marktstruktur ist die simpelste und
robusteste Beschreibung:

| Zustand | Definition | Was funktioniert hier |
|---|---|---|
| **Aufwärtstrend** | Höhere Hochs (HH) und höhere Tiefs (HL) | Trendfolge, Rücksetzer kaufen, Breakouts |
| **Abwärtstrend** | Tiefere Hochs (LH) und tiefere Tiefs (LL) | Trendfolge short, Erholungen verkaufen |
| **Range** | Wechselnde Hochs/Tiefs ohne Richtung | Mean Reversion, Ränder handeln |
| **Übergang** | Struktur bricht (BOS/CHoCH) | Nichts — höchste Fehlsignalrate |

**Break of Structure (BOS):** Der Preis überschreitet das letzte relevante Hoch/Tief in
Trendrichtung → Trendfortsetzung bestätigt.
**Change of Character (CHoCH):** Der Preis bricht *gegen* die Trendrichtung → potenzielle
Trendwende.

Diese beiden Konzepte sind aus der Smart-Money-Terminologie, aber inhaltlich identisch mit
Dow-Theorie aus den 1900ern — und beide sind mechanisch sauber programmierbar. Das macht sie zu
den wertvollsten Elementen aus dem gesamten Price-Action-Bereich.

**Implementierung:** Swing-Punkte über Fractals (ein Hoch ist ein Swing-High, wenn N Kerzen
links und rechts niedriger sind), dann Vergleich der Sequenz. Der Parameter N bestimmt die
Empfindlichkeit und sollte an die ATR gekoppelt sein, nicht fix.

## 4.2 Support und Resistance — was wirklich dahintersteckt

Die verbreitete Erklärung ("Erinnerung des Marktes") ist Esoterik. Die tatsächlichen Mechanismen:

1. **Aufgestaute Orders:** An runden Zahlen und Vortageshochs liegen real Limit-Orders und Stops.
   Das ist nicht Psychologie, sondern messbare Liquidität im Orderbuch.
2. **Positionsschmerz:** Wer am Hoch gekauft hat und im Minus liegt, verkauft oft bei Rückkehr
   zum Einstand ("break-even bias"). Erzeugt echten Angebotsdruck an bekannten Levels.
3. **Selbsterfüllung:** Genug Marktteilnehmer schauen auf dieselben Levels → sie handeln dort →
   das Level wirkt. Das ist real, solange genug Leute hinschauen.
4. **Optionen und Liquidationen:** In Krypto liegen Liquidationscluster an vorhersagbaren
   Preisen (abgeleitet aus Hebelstufen). Das sind die härtesten Levels überhaupt, weil dort
   erzwungene Orders liegen.

**Die wichtigsten Levels, nach Belastbarkeit sortiert:**

| Level | Belastbarkeit | Datenquelle |
|---|---|---|
| Liquidationscluster | Sehr hoch (erzwungene Orders) | CoinGlass Heatmap |
| Volume Profile POC | Hoch (dort wurde real gehandelt) | Eigene Berechnung aus Trades |
| Vortages-/Vorwochenhoch/-tief | Hoch (viele Stops) | Eigene Berechnung |
| VWAP (täglich/wöchentlich) | Hoch (institutioneller Referenzpreis) | Eigene Berechnung |
| Runde Zahlen | Mittel | Trivial |
| Fibonacci-Retracements | Niedrig | — |
| Gleitende Durchschnitte als "Support" | Niedrig bis Mittel | — |

## 4.3 Klassische Chartmuster und ihre Statistik

Thomas Bulkowski hat als Einziger systematisch tausende historische Vorkommen ausgewertet
(*Encyclopedia of Chart Patterns*, 63 Muster). 🔶 Seine viel zitierten Zahlen:

| Muster | Genannte Erfolgsquote | Anmerkung |
|---|---|---|
| Head and Shoulders (Top) | ~89 % | Bestbewertetes Umkehrmuster |
| Double Bottom | ~88 % | — |
| Triple Bottom | ~87 % | — |
| Descending Triangle | ~87 % | — |
| Flaggen und Wimpel | oft > 80 % | Fortsetzungsmuster |
| Rectangle Top | ~51 % Ø-Gewinn | Höchster durchschnittlicher Gewinn |

**Wichtige Einordnung — diese Zahlen sind leicht misszuverstehen:**
- "Erfolgsquote" bedeutet bei Bulkowski meist: Der Preis erreicht das gemessene Kursziel, bevor
  ein definierter Stop greift. Das ist **nicht** dieselbe Metrik wie Trefferquote im Trading.
- Bulkowski selbst dokumentiert, dass **Muster heute häufiger scheitern als früher** — ein
  klassischer Fall von Alpha-Zerfall durch Bekanntheit.
- Muster, die aus relativer Stärke gegenüber dem Gesamtmarkt ausbrechen, funktionieren
  signifikant besser als solche aus Schwäche. Das ist praktisch ein Momentum-Filter und
  wahrscheinlich der eigentliche Wirkstoff.
- Die Mustererkennung selbst ist subjektiv — was den Backtest der Nachvollziehbarkeit entzieht.

**Für den Bot:** Klassische Chartmuster sind schwer zuverlässig zu programmieren (Definition von
"Schulter" ist unscharf). Der bessere Weg ist, die zugrunde liegende Eigenschaft zu erfassen:
Ein Head-and-Shoulders ist im Kern *ein gescheiterter höherer Hochversuch nach einem Aufwärtstrend*
— und das ist als Marktstruktur-Logik sauber kodierbar. Muster über Struktur abbilden, nicht über
Geometrie.

## 4.4 Volume Profile — die aussagekräftigste Chartdarstellung

Während ein normaler Chart Preis über **Zeit** zeigt, zeigt das Volume Profile Volumen über
**Preis**. Es beantwortet die eigentlich relevante Frage: Bei welchen Preisen wurde tatsächlich
gehandelt?

| Begriff | Definition | Handelsbedeutung |
|---|---|---|
| **POC** (Point of Control) | Preis mit dem höchsten gehandelten Volumen | Stärkster Magnet und stärkstes Level |
| **Value Area** (VA) | Preisspanne mit ~68 % des Volumens | "Fairer Wertbereich" |
| **VAH / VAL** | Ober-/Untergrenze der Value Area | Zuverlässige Umkehrpunkte in Ranges |
| **HVN** (High Volume Node) | Lokales Volumenmaximum | Akzeptanz → Preis verweilt, wirkt als Support/Resistance |
| **LVN** (Low Volume Node) | Volumen-Tal | Ablehnung → Preis durchquert schnell. Ideale Breakout-Ziele |

**Die wichtigste praktische Regel:** Preis bewegt sich schnell durch LVNs und bleibt an HVNs
hängen. Ein Ausbruch in eine LVN-Zone hat wenig Widerstand und läuft oft bis zum nächsten HVN.
Das gibt sowohl Einstiegs- als auch Zielbestimmung.

**Profiltypen für den Bot:**
- **Session Profile** — pro Tag, für Intraday-Levels
- **Composite Profile** — über die gesamte Range/Konsolidierung, für strukturelle Levels
- **Visible Range Profile** — über das sichtbare Fenster, dynamisch

## 4.5 VWAP — der institutionelle Referenzpreis

VWAP = Volumengewichteter Durchschnittspreis = "was der Markt im Schnitt tatsächlich bezahlt hat".

```
VWAP = Σ(typischer Preis × Volumen) / Σ(Volumen)
```

Anders als ein gleitender Durchschnitt (nur Zeit) gewichtet VWAP nach tatsächlichem
Handelsvolumen. Institutionelle Ausführung wird oft gegen VWAP gemessen — das macht ihn zu einem
Level, an dem real gehandelt wird.

**Nutzung:**
- **Preis über VWAP** = Käufer im Vorteil in dieser Session; darunter Verkäufer
- **VWAP-Bänder** (± 1/2/3 Standardabweichungen) = Mean-Reversion-Zonen
- **Anchored VWAP** — verankert an einem bedeutenden Ereignis (Allzeithoch, Crash-Tief,
  Nachrichtenereignis) statt am Tagesbeginn. Deutlich aussagekräftiger als der Standard-VWAP
  und einer der am meisten unterschätzten Indikatoren überhaupt.

**Kombination VWAP + Volume Profile:** Wo VWAP und POC zusammenfallen, ist das Level
außergewöhnlich stark — zwei unabhängige Volumenmaße zeigen auf denselben Preis.

## 4.6 Wyckoff — der beste Rahmen für Marktphasen

Richard Wyckoff (1930er) beschrieb den Marktzyklus in vier Phasen. Die Systematik ist deshalb
wertvoll, weil sie erklärt, **warum** sich Ranges bilden:

```
Akkumulation → Markup → Distribution → Markdown → (zurück zu Akkumulation)
   (Kauf)      (Anstieg)  (Verkauf)     (Abstieg)
```

**Die drei Wyckoff-Grundgesetze:**
1. **Angebot und Nachfrage** — Preis steigt, wenn Nachfrage das Angebot übersteigt
2. **Ursache und Wirkung** — Die Größe der Akkumulationszone bestimmt die Größe der Folgebewegung
   (breite Basis → große Bewegung)
3. **Aufwand und Ergebnis** — Volumen ist der Aufwand, Preisbewegung das Ergebnis. **Divergenz
   zwischen beiden ist das eigentliche Signal**: hohes Volumen ohne Preisbewegung = jemand
   absorbiert.

Der dritte Punkt ist der praktisch wertvollste und direkt kodierbar:
`effort_result_ratio = |price_change| / volume` — auffällig niedrige Werte an Range-Rändern
deuten auf Absorption durch große Teilnehmer.

**Typische Akkumulations-Ereignisse:** Selling Climax → Automatic Rally → Secondary Test →
**Spring** (Fehlausbruch nach unten, der Stops abräumt) → Sign of Strength → Ausbruch mit
Volumen. Der "Spring" ist praktisch identisch mit dem, was SMC "Liquidity Sweep" nennt.

## 4.7 Smart Money Concepts — was davon haltbar ist

SMC (systematisiert von Michael Huddleston / ICT, populär seit ~2018) hat massive Verbreitung —
und praktisch keine unabhängige empirische Prüfung. Fast alle verfügbaren Quellen sind
Anbieterinhalte mit Verkaufsinteresse. Eine ehrliche Einordnung der Bausteine:

| Konzept | Was es ist | Haltbarkeit | Programmierbar? |
|---|---|---|---|
| **Liquidity Sweep / Stop Hunt** | Docht durch ein offensichtliches Hoch/Tief, dann Umkehr | ✅ Real und messbar — Stops liegen dort tatsächlich | ✅ Gut |
| **Break of Structure (BOS)** | Bruch des letzten Swing-Punkts | ✅ Real, identisch mit Dow-Theorie | ✅ Sehr gut |
| **Change of Character (CHoCH)** | Struktur-Bruch gegen den Trend | ✅ Real | ✅ Sehr gut |
| **Fair Value Gap (FVG)** | 3-Kerzen-Lücke, in der kaum gehandelt wurde | ⚠️ Real messbar; entspricht LVN im Volume Profile | ✅ Gut |
| **Order Block** | Letzte Gegenkerze vor einer starken Bewegung | ⚠️ Definition uneindeutig, viele Varianten | ⚠️ Mehrdeutig |
| **Displacement** | Impulsbewegung mit großen Kerzen | ✅ = Momentum + Volatilitätsexpansion | ✅ Gut |
| **"Institutionen jagen deine Stops"** | Erzählung | ❌ Narrativ, nicht prüfbar | — |

**Fazit:** Die mechanisch definierbaren Teile (Sweep, BOS, CHoCH, FVG, Displacement) sind
brauchbare Features — sie beschreiben reale Marktmikrostruktur unter neuen Namen. Die
Erzählschicht darüber ist nicht überprüfbar und für einen Bot irrelevant. Nimm die Mechanik,
lass die Geschichte.

Selbst SMC-freundliche Quellen räumen ein, dass die Identifikation des "richtigen" Order Blocks
erhebliche Erfahrung erfordert — das ist eine Umschreibung für: nicht objektiv definierbar. Was
nicht objektiv definierbar ist, kann nicht zuverlässig getestet werden.

## 4.8 Multi-Timeframe-Konfluenz

Die einzige Price-Action-Regel mit breiter Zustimmung über alle Schulen hinweg: **Nie auf einem
niedrigen Zeitrahmen einsteigen, ohne den Kontext des höheren geprüft zu haben.**

**Bewährte Drei-Ebenen-Struktur (Faktor 4–6 zwischen den Ebenen):**

| Ebene | Zeitrahmen (Beispiel) | Aufgabe |
|---|---|---|
| **Kontext** | 4h / 1d | Erlaubte Handelsrichtung. Filter, kein Signal |
| **Setup** | 1h / 15m | Wo ist die Gelegenheit? Level, Muster, Struktur |
| **Trigger** | 5m / 1m | Wann genau einsteigen? Ausführungs-Timing |

**Programmiertechnisch entscheidend:** Beim Backtest darf die höhere Ebene nur **abgeschlossene**
Kerzen liefern. Wer den 4h-Trend aus der noch laufenden 4h-Kerze berechnet, handelt mit
Zukunftswissen. Das ist der häufigste versteckte Look-Ahead-Bias in Multi-Timeframe-Systemen und
macht Backtests spektakulär gut aussehen.

---

# Teil V — Indikatoren

## 5.1 Was Indikatoren wirklich sind

Jeder Indikator ist eine Funktion von OHLCV. Kein Indikator enthält Information, die nicht schon
im Preis steckt — er macht sie nur sichtbar. Daraus folgen zwei Dinge:

1. **Indikatoren können nichts vorhersagen**, sie können nur beschreiben, komprimieren oder
   glätten.
2. **Mehr Indikatoren = nicht mehr Information.** RSI, Stochastik, CCI und Williams %R messen
   praktisch dasselbe. Ein Modell mit allen vieren hat nicht vier Signale, sondern ein Signal mit
   vierfachem Rauschen und vierfacher Overfitting-Gefahr.

## 5.2 Die Kategorien und was sie leisten

### Trend

| Indikator | Berechnung | Stärke | Schwäche |
|---|---|---|---|
| **SMA/EMA** | Gleitender Durchschnitt | Einfach, robust | Nachlaufend |
| **EMA-Fächer** (8/21/55/200) | Mehrere EMAs | Trendstärke aus Abstand und Ordnung ablesbar | — |
| **ADX** | Directional Movement | Misst Trend**stärke** unabhängig von der Richtung | Sehr träge |
| **Lineare Regressionssteigung** | Kleinste Quadrate über N | Sauberer als MA, weniger Lag | — |
| **Hurst-Exponent** | Fraktale Analyse | > 0,5 = trendend, < 0,5 = mean-revertierend | Rechenintensiv, instabil bei kurzen Fenstern |
| **Ichimoku** | Mehrteiliges System | Alles-in-einem, gut für Trendfilter | Viele Parameter |

**ADX ist der wichtigste Trendindikator für einen Bot** — nicht als Signal, sondern als Schalter:
Er sagt, welche Strategiefamilie gerade aktiviert werden darf.

### Momentum

| Indikator | Aussage | Praktische Nutzung |
|---|---|---|
| **RSI** | Relative Stärke der Auf- vs. Abbewegungen | ⚠️ **Nicht** als "über 70 = verkaufen" — im Trend bleibt RSI wochenlang über 70. Nutze **Divergenzen** und **RSI-Regime** (bleibt RSI über 40? → Aufwärtstrend intakt) |
| **MACD** | Differenz zweier EMAs + Signallinie | Das **Histogramm** ist aussagekräftiger als die Kreuzungen |
| **Rate of Change** | Prozentuale Änderung über N | Simpelster und oft bester Momentum-Wert |
| **Stochastik** | Position des Close in der N-Range | Nur in Ranges brauchbar |

### Volatilität

| Indikator | Aussage | Nutzung |
|---|---|---|
| **ATR** | Durchschnittliche wahre Handelsspanne | **Der wichtigste Indikator im ganzen System** — für Stops, Positionsgrößen und Normalisierung |
| **Bollinger-Bänder** | MA ± N Standardabweichungen | Bandbreite zeigt Kompression/Expansion |
| **Bollinger Bandwidth** | (Oberes − Unteres) / Mitte | **Squeeze-Erkennung**: historisch niedrige Bandbreite geht Ausbrüchen voraus |
| **Keltner Channels** | MA ± N × ATR | Robuster als Bollinger bei Ausreißern |
| **Realisierte Volatilität** | Std. der Log-Renditen | Basis für Vol-Targeting |
| **Parkinson / Garman-Klass** | Schätzer aus High/Low bzw. OHLC | Effizienter als reine Close-Volatilität |

**ATR ist der Schlüssel zur Vergleichbarkeit.** Ohne ATR-Normierung sind Signale zwischen Assets
und zwischen Zeitperioden nicht vergleichbar. Jedes Feature im Bot sollte ATR-normiert vorliegen.

### Volumen

| Indikator | Aussage |
|---|---|
| **OBV** | Kumuliertes richtungsgewichtetes Volumen — Divergenzen zum Preis sind das Signal |
| **Volume Z-Score** | Wie ungewöhnlich ist das aktuelle Volumen? Besser als Rohvolumen |
| **VWAP-Abweichung** | Abstand zum volumengewichteten Mittel |
| **Delta / Taker Buy-Sell** | Aggressive Käufer minus aggressive Verkäufer — die eigentliche Volumeninformation |
| **CVD** (Cumulative Volume Delta) | Kumuliertes Delta. Divergenz zum Preis = Absorption |

**Delta und CVD sind in Krypto besonders wertvoll**, weil Börsen-APIs die Aggressor-Seite jedes
Trades liefern. Diese Information fehlt in den meisten klassischen Aktien-Feeds. Das ist ein
echter Vorteil des Krypto-Marktes für einen Bot.

## 5.3 Der Indikator-Trugschluss

**Das Problem der Redundanz:** Nimmt man 20 Indikatoren, erklären typischerweise 3–4
Hauptkomponenten über 90 % der Varianz. Man hat also faktisch 3–4 Informationen, aber 20
Parameter zum Überanpassen.

**Gegenmaßnahmen im Bot:**
1. Korrelationsmatrix aller Features berechnen; bei |ρ| > 0,9 einen entfernen
2. Feature Importance (LightGBM/SHAP) nutzen — nur behalten, was messbar beiträgt
3. Pro Kategorie 1–2 Indikatoren, nicht 5
4. Immer fragen: Was misst dieser Indikator, das ein anderer nicht schon misst?

## 5.4 Empfohlenes Minimalset

Ein bewusst kleines, weitgehend redundanzfreies Set als Ausgangsbasis:

| Zweck | Indikator |
|---|---|
| Trendrichtung | EMA 50 vs. EMA 200 (höherer Zeitrahmen) |
| Trendstärke / Regime-Schalter | ADX(14) |
| Momentum | ROC(10), MACD-Histogramm |
| Mean-Reversion-Position | Z-Score des Preises zum VWAP |
| Volatilität (Normierung) | ATR(14) |
| Volatilitäts-Regime | Bollinger Bandwidth Perzentil (250 Perioden) |
| Volumen | Volume Z-Score(20), CVD-Steigung |
| Level | Distanz zu POC, VAH, VAL, Vortageshoch/-tief (in ATR) |
| Struktur | BOS/CHoCH-Flag, Distanz zum letzten Swing (in ATR) |
| Kerze | Die 8 kontinuierlichen Features aus Abschnitt 3.8 |

Rund 25 Features — genug für Ausdrucksstärke, klein genug für Kontrolle.

---

# Teil VI — Gute Gelegenheiten erkennen

## 6.1 Was eine Gelegenheit objektiv ausmacht

Eine gute Gelegenheit ist **nicht** "der Preis wird wahrscheinlich steigen". Sie ist definiert
durch **Asymmetrie**:

```
Gelegenheit = (erwartete Bewegung × Wahrscheinlichkeit) / (Risiko bis zur Invalidierung)
```

Die drei Bestandteile, alle objektiv messbar:

1. **Naher Invalidierungspunkt** — es gibt ein klar definiertes Preisniveau, an dem die Idee
   nachweislich falsch ist, und es ist nah. Das erlaubt einen engen Stop und damit eine größere
   Position bei gleichem Risiko.
2. **Freier Weg zum Ziel** — zwischen Einstieg und Ziel liegt wenig Widerstand (LVN-Zone, keine
   HVNs, kein starkes Level).
3. **Kontext-Rückenwind** — der übergeordnete Trend, das Regime und die Positionierungsdaten
   arbeiten in dieselbe Richtung.

**Wichtiger Punkt:** Die besten Gelegenheiten kommen nicht von der besten Prognose, sondern vom
besten **Verhältnis**. Ein Setup mit 40 % Trefferquote und 5:1-Verhältnis ist wertvoller als 70 %
mit 1:1.

## 6.2 Konfluenz-Scoring statt Regelkette

**Der falsche Ansatz** (und der verbreitetste):
```
WENN RSI < 30 UND Preis über EMA200 UND Bullish Engulfing UND Volumen > Ø → KAUFEN
```
Probleme: Die Bedingungen feuern selten gleichzeitig (wenige Trades → keine statistische
Aussagekraft), jede Bedingung ist ein Overfitting-Parameter, und knappes Verfehlen einer
Bedingung führt zu binärem Nichts.

**Der bessere Ansatz — gewichtete Punktzahl:**
```python
score = 0.0
score += 0.30 * trend_alignment_score      # HTF-Trend, [-1, 1]
score += 0.20 * level_proximity_score       # Nähe zu POC/VWAP/Swing, [0, 1]
score += 0.15 * momentum_score              # ROC, MACD, [-1, 1]
score += 0.15 * volume_confirmation         # Volume Z-Score, [0, 1]
score += 0.10 * candle_pattern_score        # Kerzen-Features, [-1, 1]
score += 0.10 * positioning_score           # Funding, OI, [-1, 1]

# Regime-Gewichtung: dieselben Faktoren zählen je nach Marktzustand anders
score *= regime_multiplier[current_regime]

# Nur handeln, wenn die Punktzahl klar über der Schwelle liegt
if score > threshold:
    size = base_risk * min(score, 1.0)   # Positionsgröße skaliert mit Überzeugung
```

**Vorteile:** kontinuierlich statt binär, Positionsgröße skaliert automatisch mit Signalstärke,
Gewichte sind aus Daten lernbar (statt geraten), einzelne fehlende Bedingung führt zu einem
kleineren Trade statt zu keinem.

## 6.3 Die vier robusten Setup-Familien

Diese vier haben die breiteste empirische Grundlage über Märkte und Jahrzehnte:

### A) Trendfolge-Ausbruch
- **Logik:** Preis verlässt eine Konsolidierung in Richtung des übergeordneten Trends
- **Auslöser:** Donchian-Breakout (Hoch der letzten N Perioden) nach Bollinger-Squeeze
- **Filter:** ADX steigend, HTF-Trend gleichgerichtet, Volumenexpansion
- **Stop:** Unter der Konsolidierung oder 2 × ATR
- **Empirie:** 🎓 Momentum ist die am besten dokumentierte Anomalie überhaupt. Jegadeesh & Titman
  (1993) und über 30 Jahre Folgeforschung bestätigen: Gewinner der letzten 3–12 Monate schlagen
  Verlierer in den folgenden 12 Monaten — robust über Assetklassen und Länder hinweg. Moskowitz
  et al. (2012) zeigen dasselbe für Time-Series-Momentum (absolute statt relative Performance)
- **Schwäche:** Viele Fehlausbrüche in Ranges → deshalb ADX-Filter zwingend

### B) Trendfolge-Rücksetzer
- **Logik:** Im intakten Trend auf einen Rücksetzer zu einem Level warten
- **Auslöser:** Rücksetzer auf EMA/VWAP/POC + Umkehrkerze + CHoCH auf niedrigerem Zeitrahmen
- **Filter:** Trend intakt (kein BOS gegen die Richtung), Rücksetzer < 50 % der Impulsbewegung
- **Stop:** Unter dem Rücksetzer-Tief
- **Vorteil:** Deutlich besseres CRV als Ausbrüche, weil der Einstieg näher am Invalidierungspunkt
  liegt
- **Schwäche:** Man verpasst Trends, die nicht zurücksetzen

### C) Mean Reversion an Extremen
- **Logik:** Nach einer übertriebenen Bewegung Rückkehr zum Mittel
- **Auslöser:** Z-Score zum VWAP > 2,5 + Volumenspitze + Erschöpfungskerze
- **Filter:** **Nur im Range-Regime** (ADX niedrig). Im Trend ist das die schnellste Art zu
  verlieren
- **Stop:** Eng, hinter dem Extrem
- **Krypto-Verstärkung:** Nach einer Liquidationskaskade ist die Überreaktion mechanisch bedingt
  (erzwungene Orders, nicht Meinung) — statistisch die verlässlichste Mean-Reversion-Situation
  im Krypto-Markt
- **Empirie:** 🎓 Cointegration-basierte Paarstrategien sind die meistuntersuchte
  Stat-Arb-Familie; in einer Krypto-Untersuchung waren 31 Paare signifikant kointegriert

### D) Liquidity Sweep / Fehlausbruch
- **Logik:** Preis durchsticht ein offensichtliches Level (räumt Stops ab) und kehrt sofort um
- **Auslöser:** Docht durch Vortageshoch/-tief oder Swing-Punkt, Close zurück innerhalb
- **Filter:** Volumenspitze beim Durchstich, schnelle Rückkehr (innerhalb 1–3 Kerzen)
- **Stop:** Hinter dem Docht — sehr eng, weil der Invalidierungspunkt eindeutig ist
- **Warum es funktioniert:** Stops liegen real an offensichtlichen Levels. Ihr Auslösen erzeugt
  Liquidität, die größere Teilnehmer nutzen. Der Docht ist der messbare Fingerabdruck davon
- **Vorteil:** Bestes CRV aller vier Familien (oft 4:1+), weil der Stop extrem eng sein kann

### Regime-Zuordnung

| Regime | A: Ausbruch | B: Rücksetzer | C: Mean Rev. | D: Sweep |
|---|---|---|---|---|
| Starker Trend | ✅ | ✅✅ | ❌ | ✅ |
| Schwacher Trend | ✅ | ✅ | ⚠️ | ✅ |
| Range | ❌ | ❌ | ✅✅ | ✅✅ |
| Hohe Volatilität | ⚠️ | ⚠️ | ✅ | ✅ |
| Kompression | ✅ (auf Ausbruch warten) | ❌ | ❌ | ⚠️ |

Die Sweep-Familie ist die einzige, die in jedem Regime funktioniert — weil sie nicht auf
Richtungsprognose beruht, sondern auf einem mechanischen Liquiditätsereignis.

## 6.4 Filter, die die meiste Arbeit leisten

Nach aller verfügbaren Evidenz kommt der Großteil des Nutzens nicht von besseren Signalen,
sondern von besseren Filtern:

| Filter | Wirkung |
|---|---|
| **HTF-Trendausrichtung** | Wichtigster Einzelfilter. Halbiert Fehlsignale |
| **Regime-Schalter** | Verhindert, dass eine Strategie im falschen Umfeld läuft |
| **Volatilitäts-Bandbreite** | Kein Handel bei extrem niedriger Vola (kein Bewegungspotenzial) und extrem hoher (Slippage frisst alles) |
| **Liquiditätsfilter** | Nur Symbole mit ausreichendem Volumen und engem Spread |
| **Zeitfilter** | Bestimmte Stunden meiden — Bitcoin zeigt dokumentierte Intraday-Saisonalität |
| **Nachrichten-/Event-Filter** | Kein neuer Einstieg kurz vor bekannten Makro-Terminen (FOMC, CPI) |
| **Korrelationsfilter** | Kein Einstieg, wenn bereits eine hoch korrelierte Position offen ist |
| **Kosten-Schwelle** | Erwarteter Gewinn muss Roundtrip-Kosten um Faktor ≥ 3 übersteigen |

## 6.5 Einstieg, Stop, Ziel

**Stop-Platzierung** — die Reihenfolge ist entscheidend:
1. Erst den **strukturellen** Invalidierungspunkt bestimmen (wo ist die Idee falsch?)
2. Puffer für Rauschen: `Stop = Strukturpunkt ± 0,5 × ATR`
3. **Dann** die Positionsgröße aus dem Stop-Abstand ableiten

Nie umgekehrt. Ein Stop, der aus der gewünschten Positionsgröße abgeleitet wird, hat keine
Bedeutung und wird zufällig getroffen.

**Ausstieg — mehrstufig:**

| Stufe | Regel |
|---|---|
| Harter Stop | Struktureller Punkt, immer als echte Order an der Börse (nicht nur im Bot!) |
| Break-Even | Nach +1 R Stop auf Einstand ziehen |
| Teilgewinn | 30–50 % bei +2 R schließen |
| Trailing | Rest mit ATR-Trailing oder Chandelier Exit laufen lassen |
| Zeit-Stop | Nach N Perioden ohne Fortschritt schließen — totes Kapital ist Opportunitätskosten |

**Warum der Stop als echte Börsenorder liegen muss:** Wenn dein Bot abstürzt, die Verbindung
ausfällt oder der VPS neu startet, ist ein "im Code" gehaltener Stop wirkungslos. Der einzige
Stop, der bei Ausfall schützt, ist der, der bereits bei der Börse liegt.

## 6.6 Was eine Nicht-Gelegenheit ausmacht

Genauso wichtig — der Bot muss diese Zustände aktiv erkennen und pausieren:

- Preis in der Mitte einer Range (kein naher Invalidierungspunkt → schlechtes CRV)
- Widersprüchliche Zeitrahmen (4h auf, 1h ab)
- Volatilität am historischen Extrem (oben: Slippage; unten: keine Bewegung)
- Kurz vor bekannten Makro-Events
- Nach N Verlusttrades in Folge (mögliche Regime-Änderung → prüfen statt weitermachen)
- Datenqualität eingeschränkt (Feed-Lücke, Spread ungewöhnlich weit)

---

# Teil VII — Krypto-spezifische Signale

Das ist der Bereich, in dem ein Krypto-Bot echte Vorteile gegenüber Aktien hat: Es gibt
Datenquellen, die es im klassischen Markt entweder nicht gibt oder nur für sehr viel Geld.

## 7.1 Funding Rate

Perpetual Futures haben kein Ablaufdatum. Damit ihr Preis am Spot-Preis bleibt, zahlen alle 8
Stunden Longs an Shorts (oder umgekehrt) — die Funding Rate.

| Funding Rate | Bedeutung | Handelsimplikation |
|---|---|---|
| Stark positiv (> 0,1 % / 8h) | Longs zahlen viel → überfüllte Long-Seite | Überhitzt. Korrekturrisiko hoch |
| Leicht positiv (0,01 %) | Normalzustand | Neutral |
| Negativ | Shorts zahlen → überfüllte Short-Seite | Short-Squeeze-Potenzial |
| Extrem negativ | Panik/Kapitulation | Historisch oft nahe lokalen Böden |

Der Wert wirkt in zwei Rollen: als **Contrarian-Signal** bei Extremen und als **Kostenfaktor**
(0,1 % alle 8 h = 109 % p.a. — das macht jede Long-Position unhaltbar).

## 7.2 Open Interest

OI = Summe aller offenen Kontrakte = wie viel Hebel im System ist.

**Die vier Kombinationen mit Preis — Standardinterpretation:**

| Preis | OI | Deutung |
|---|---|---|
| ↑ | ↑ | Neues Geld strömt long. Gesunder Trend |
| ↑ | ↓ | Short-Squeeze / Eindeckungen. Weniger nachhaltig |
| ↓ | ↑ | Neue Shorts. Abwärtstrend mit Überzeugung |
| ↓ | ↓ | Long-Liquidationen. Oft Kapitulationsende |

## 7.3 Liquidations-Daten

Das mächtigste krypto-exklusive Werkzeug. Weil Hebelstufen standardisiert sind, lassen sich
Liquidationspreise berechnen — Liquidations-Heatmaps zeigen, wo Cluster erzwungener Orders
liegen.

**Zwei Nutzungen:**
1. **Als Magnet:** Preis bewegt sich auffällig oft zu großen Liquidationsclustern hin. Dort liegt
   Liquidität, die jemand abholen will
2. **Als Mean-Reversion-Auslöser:** Nach einer Kaskade ist der Preis mechanisch übertrieben —
   erzwungene Orders sind preisunabhängig. Das Zurückschnappen danach ist eine der zuverlässigsten
   kurzfristigen Bewegungen im Krypto-Markt

**Warnsignal-Kombination** (alle drei zusammen sind deutlich aussagekräftiger als einzeln):
OI auf Rekordniveau + Funding > 0,1 % + dichte Liquidationscluster nahe am Preis.

## 7.4 Weitere Positionierungsdaten

| Kennzahl | Aussage |
|---|---|
| **Long/Short-Ratio** | Verhältnis der Konten. Top-Trader-Ratio ist aussagekräftiger als das aller Konten |
| **Taker Buy/Sell Volume** | Aggressives Kauf- vs. Verkaufsvolumen — echter Kaufdruck statt passiver Orders |
| **Basis (Futures − Spot)** | Terminaufschlag. Hohe Basis = Optimismus. Direkt handelbar (siehe 7.6) |
| **Options Open Interest / Max Pain** | Wo liegen Optionspositionen. Beeinflusst den Preis zum Verfall |

## 7.5 On-Chain-Daten

Nur in Krypto verfügbar: Man kann buchstäblich in das Kassenbuch schauen.

| Metrik | Aussage | Belastbarkeit |
|---|---|---|
| **Exchange Netflow** | Netto-Zufluss zu Börsen = potenzieller Verkaufsdruck; Abfluss = Akkumulation/Selbstverwahrung | Mittel-Hoch |
| **Stablecoin-Supply auf Börsen** | "Trockenpulver" — Kapital, das kaufbereit wartet | Mittel |
| **Whale-Transfers** | Große Wallets bewegen Bestände zu/von Börsen | Mittel |
| **Dormant Wallet Activation** | Lange inaktive Wallets werden aktiv | Mittel |
| **SOPR / MVRV / NUPL** | Bewertungsmetriken auf Basis realisierter Kosten | Für langfristige Zyklen, nicht für Intraday |
| **Miner-Flows** | Verkaufsdruck von Minern | Niedriger geworden seit ETF-Ära |

**Wichtige Einschränkung:** Eine oft zitierte Auswertung (CryptoQuant, 2025) 🔶 fand, dass
Whale-Einzahlungen an Börsen in 65 % der Fälle einem Kursrückgang von ≥ 3 % innerhalb von 48
Stunden vorausgingen. Solche Zahlen sind mit Vorsicht zu behandeln — sie stammen vom
Datenanbieter selbst und sind meist nicht out-of-sample validiert. On-Chain-Signale sind
außerdem **langsam** (Stunden bis Tage) und passen deshalb zu Swing-, nicht zu Intraday-Systemen.

## 7.6 Basis-Trade — eine eigenständige Ertragsquelle

Das ist keine Prognosestrategie, sondern eine Risikoprämie — und damit strukturell etwas anderes
als alles bisher Beschriebene.

**Mechanik (Cash-and-Carry):**
1. Spot kaufen (z. B. 1 BTC)
2. Gleichzeitig Perpetual Future in gleicher Größe shorten
3. Preisbewegung hebt sich auf (delta-neutral)
4. Ertrag = eingenommene Funding Rate

**Ertragsangaben aus der Praxis:** 15–40 % Netto-APR bei aktiver Auswahl über mehrere Märkte;
für Basis-Trades werden historische Sharpe-Werte um 4,8 genannt. 🔶 Diese Zahlen stammen
überwiegend von Anbietern solcher Produkte — die Größenordnung ist plausibel, die Präzision nicht.

**Die realen Risiken (die in Werbung selten stehen):**
- **Funding-Umkehr:** Wird Funding negativ, zahlst du statt zu kassieren
- **Gegenparteirisiko:** Börseninsolvenz trifft beide Beine gleichzeitig (FTX-Szenario)
- **Liquidationsrisiko der Short-Seite:** Bei starkem Preisanstieg braucht das Short-Bein
  Nachschuss. Ohne ausreichende Margin-Reserve wirst du liquidiert, obwohl die Gesamtposition
  neutral ist — der häufigste Fehler bei dieser Strategie
- **Ausführungsrisiko:** Beide Beine müssen zeitgleich gefüllt werden
- **Steuerliche Komplexität:** In Deutschland sind Funding-Einnahmen und Spot/Future getrennt zu
  behandeln

**Warum das für dieses Projekt interessant ist:** Es ist die einzige besprochene Strategie, deren
Ertrag **nicht** von einer korrekten Marktprognose abhängt. Als Grundlast neben
richtungsabhängigen Strategien ist das eine sinnvolle Diversifikation — mit ausreichend
Margin-Puffer (mindestens 50 % über dem Minimum) und automatischem Ausstieg bei negativem Funding.

## 7.7 Makro-Verknüpfung

Bitcoin ist kein isolierter Markt mehr. Aktuelle Korrelationswerte 🔶:

| Beziehung | Wert | Bedeutung |
|---|---|---|
| BTC ↔ Nasdaq 100 | Korrelation zeitweise > 0,7 | BTC verhält sich als High-Beta-Risikoasset, nicht als Absicherung |
| BTC ↔ DXY (US-Dollar-Index) | Historisch invers, **2026 zeitweise positiv gekippt** | Die Beziehung ist instabil — nicht als feste Regel kodieren |
| BTC ↔ Spot-ETF-Flows | Zunehmend dominant | ETF-Zu-/Abflüsse als eigener Treiber |

**Wichtige Erkenntnis für den Bot:** Diese Korrelationen sind **nicht stabil**. Die
DXY-Beziehung kippte 2026 erstmals seit über einem Jahrzehnt ins Positive. Eine fest kodierte
Makro-Regel ("Dollar stark → Bitcoin schwach") ist deshalb gefährlich. Richtig ist, die
Korrelation **rollierend zu messen** und als Feature zu verwenden, nicht als Regel.

Nutzung als Risikofilter: Bei stark negativer Nasdaq-Eröffnung Positionsgrößen reduzieren, statt
gegen ein risikoaverses Gesamtumfeld zu handeln.

## 7.8 Zeitliche Saisonalität

Bitcoin handelt 24/7, aber nicht gleichmäßig. Dokumentierte Muster 🎓:

- **Volatilitäts- und Volumenmaximum** während der europäischen und US-Börsenzeiten — NYSE-Zeiten
  führen die Krypto-Aktivität an
- Höchste Volatilität um ca. **12:00 EST**
- Schwächste Stunden: **03:00–04:00 UTC**; stärkste Renditen in den Stunden **22:00–23:00**
- **Wochenende:** deutlich geringeres Volumen und geringere Volatilität. Renditemuster
  verschieben sich — an Wochenenden dominiert die Intraday-Rendite, an NYSE-Handelstagen die
  Overnight-Rendite
- **Wochentag:** Montag erhöhte Volatilität; ein dokumentierter "Monday Asia Open"-Effekt

**Praktische Nutzung:** Stunde und Wochentag als zyklische Features (Sinus/Kosinus-kodiert)
aufnehmen. Zusätzlich Positionsgrößen an die erwartete Stundenvolatilität koppeln. Kein
mechanisches Handeln nach Uhrzeit — diese Effekte sind schwach und können verschwinden.

---

# Teil VIII — Statistische Validierung

## 8.1 Der Bias-Katalog

Jeder dieser Fehler macht einen Backtest besser aussehen, als die Realität ist:

| Bias | Was passiert | Erkennungszeichen | Gegenmaßnahme |
|---|---|---|---|
| **Look-Ahead** | Nutzung von Daten, die zum Zeitpunkt nicht verfügbar waren | Unrealistisch glatte Equity-Kurve | Ausführung erst auf nächster Kerze; nur abgeschlossene Kerzen |
| **Survivorship** | Nur heute existierende Assets getestet | Zu gute Ergebnisse bei Altcoins | Delistete Assets einbeziehen |
| **Overfitting** | Parameter an Historie angepasst | Bricht bei ±20 % Parameteränderung ein | Walk-Forward, wenige Parameter |
| **Data Snooping** | Viele Varianten getestet, beste berichtet | Anzahl Versuche nicht dokumentiert | Alle Versuche zählen, Deflated Sharpe |
| **Kostenunterschätzung** | Slippage/Gebühren zu optimistisch | Live deutlich schlechter als Backtest | Kosten aus Live-Fills kalibrieren |
| **Overnight-/Gap-Ignoranz** | Stops greifen im Backtest immer | Zu geringer Max Drawdown | Gap-Simulation, Stop kann übersprungen werden |
| **Regime-Auswahl** | Nur ein Marktumfeld getestet | Nur Bullenmarkt-Daten | Mehrere Zyklen einbeziehen |
| **Liquiditäts-Ignoranz** | Ordergröße überschreitet reales Volumen | Gut bei kleinen Coins | Ordergröße auf % des Kerzenvolumens deckeln |

## 8.2 Walk-Forward-Analyse

Die einzige Optimierungsmethode, die nicht systematisch lügt:

```
|--- Train A ---|- Test A -|
        |--- Train B ---|- Test B -|
                |--- Train C ---|- Test C -|
```

Parameter werden auf dem Trainingsfenster bestimmt, auf dem **folgenden** Testfenster gemessen,
dann wird das Fenster verschoben. Nur die aneinandergehängten Test-Ergebnisse zählen als
Performance.

**Walk-Forward-Effizienz** = Out-of-Sample-Ertrag / In-Sample-Ertrag. Werte unter ~0,5 bedeuten
Overfitting.

## 8.3 Deflated Sharpe Ratio

Wenn du 100 Strategievarianten testest, hat die beste allein durch Zufall einen guten Sharpe. Die
DSR (Bailey & López de Prado, 2014) 🎓 korrigiert um:
- Anzahl der durchgeführten Versuche
- Schiefe und Wölbung der Renditeverteilung (Finanzrenditen sind nicht normalverteilt)
- Länge der Stichprobe

**Praxis:** Zähler für alle getesteten Varianten im Backtest-Framework führen — auch für
verworfene. Diese Zahl geht in die DSR ein. Ohne diesen Zähler ist jede Sharpe-Angabe wertlos.

## 8.4 Realistisches Kostenmodell

```python
def simulate_fill(order, bar, book_state):
    # 1. Basispreis: Eröffnung der NÄCHSTEN Kerze, nie Close der aktuellen
    base = bar.open

    # 2. Spread
    spread_cost = base * spread_bps / 10_000

    # 3. Slippage: wächst mit Ordergröße relativ zum Volumen und mit Volatilität
    participation = order.size / bar.volume
    slippage = base * slippage_coef * sqrt(participation) * (bar.atr / base)

    # 4. Gebühr abhängig vom Ordertyp
    fee = base * (maker_fee if order.post_only else taker_fee)

    # 5. Limit-Orders werden nicht garantiert gefüllt
    if order.post_only and not price_touched(order.limit_price, bar):
        return NotFilled()

    return Fill(price=base + spread_cost + slippage, fee=fee)
```

Die Koeffizienten werden anfangs konservativ geschätzt und später aus gemessenen Live-Fills
kalibriert. Diese Rückkopplung ist der Unterschied zwischen einem Backtest, der etwas aussagt,
und einem, der nichts aussagt.

## 8.5 Die harte Realität

| Befund | Konsequenz |
|---|---|
| Backtest-Sharpe erklärte < 3 % der Live-Performance (888 Algorithmen) 🔶 | Backtest kann ausschließen, nicht bestätigen |
| 20–50 % Performance-Einbruch beim Live-Gang ist normal 🔶 | Sicherheitsmarge einplanen: Eine Strategie muss im Backtest deutlich profitabel sein, nicht knapp |
| 7.846 publizierte Handelsregeln — nach Kosten blieb fast nichts 🎓 | Kosten sind der Hauptfilter, nicht die Signalqualität |

**Deshalb der Shadow-Mode:** Neue Modelle laufen live mit, erzeugen Signale, werden gemessen —
führen aber keine Orders aus. Das ist die einzige Validierung auf echten Daten ohne Kapitalrisiko
und deutlich aussagekräftiger als jeder Backtest.

---

# Teil IX — Risiko und Positionsgröße

## 9.1 R-Multiple — die einzig sinnvolle Recheneinheit

**1 R = der Betrag, den du bei diesem Trade riskierst** (Abstand Einstieg → Stop × Positionsgröße).

Jedes Ergebnis wird in R gemessen: +2 R, −1 R, +0,5 R. Vorteile:
- Vergleichbarkeit über Assets, Kontogrößen und Zeitperioden
- Erwartungswert direkt ablesbar: `E = Σ(R-Ergebnisse) / Anzahl Trades`
- Kontogröße wird irrelevant für die Strategiebewertung

Ein System mit E = +0,2 R und 200 Trades pro Jahr erwirtschaftet 40 R jährlich. Bei 1 % Risiko
pro Trade sind das ~40 % vor Zinseszins.

## 9.2 Positionsgröße — die Formel

```
Positionsgröße = (Konto × Risiko-pro-Trade-%) / (Stop-Abstand in Preiseinheiten)
```

**Beispiel:** Konto 10.000 €, 1 % Risiko = 100 €. Einstieg BTC bei 60.000, Stop bei 58.500
(Abstand 1.500). → Positionsgröße = 100 / 1.500 = 0,0667 BTC (= 4.000 € Positionswert).

Wichtig: Der **Positionswert** (4.000 €) ist nicht das Risiko. Das Risiko sind die 100 €. Diese
Verwechslung ist ein häufiger und teurer Denkfehler.

## 9.3 Volatilitäts-Targeting

Statt fixem Prozentrisiko: Jede Position bekommt denselben **Risikobeitrag**, gemessen in
Volatilität.

```
Positionsgröße = (Konto × Ziel-Vola) / (Asset-Vola × √Positionsanzahl)
```

Effekt: Ein ruhiges Asset bekommt mehr Kapital, ein volatiles weniger — das Portfoliorisiko wird
über die Zeit stabil, statt mit der Marktvolatilität zu schwanken. Das ist der Standard bei
professionellen Managed-Futures-Programmen und einer der wirkungsvollsten einzelnen
Verbesserungen an einem System.

## 9.4 Kelly — nützlich als Obergrenze, gefährlich als Zielgröße

```
f* = (p × b − q) / b
```
mit p = Trefferwahrscheinlichkeit, q = 1−p, b = Ø-Gewinn / Ø-Verlust.

**Warum volles Kelly praktisch nie richtig ist:**
- Es setzt voraus, dass p und b **exakt bekannt** sind und sich nie ändern. Beides ist live falsch
- Volles Kelly erzeugt regelmäßig 30–50 % Drawdowns selbst bei profitablen Systemen
- Bei überschätzter Edge führt volles Kelly zuverlässig zum Ruin

**Fraktionales Kelly:** Halbes Kelly behält rund **75 %** der maximalen Wachstumsrate bei
deutlich reduzierter Varianz — das ist ein hergeleitetes Ergebnis, keine Faustregel. Der
Grenznutzen von mehr Einsatz ist klein, das Grenzrisiko groß.

**Empfehlung:** Kelly nur als **Obergrenze** verwenden, gehandelt wird mit ¼ Kelly oder dem
festen 1 %-Risiko — je nachdem, was kleiner ist.

## 9.5 Risk of Ruin

Die Wahrscheinlichkeit, das Konto unter eine kritische Schwelle zu fahren, hängt von drei Größen
ab: Edge, Risiko pro Trade, Anzahl Trades.

| Risiko pro Trade | Verlustserie bis −50 % | Praktische Einordnung |
|---|---|---|
| 1 % | ~69 Trades in Folge | Praktisch unmöglich |
| 2 % | ~34 Trades | Sehr unwahrscheinlich |
| 5 % | ~14 Trades | Kommt vor |
| 10 % | ~7 Trades | Passiert regelmäßig |
| 25 % | ~3 Trades | Fast sicher irgendwann |

Selbst ein System mit 60 % Trefferquote hat auf 1.000 Trades eine sehr hohe Wahrscheinlichkeit
für eine Serie von 10+ Verlusten. Bei 10 % Risiko pro Trade wäre das Konto halbiert. Deshalb ist
1–2 % kein Vorsichtsmaß, sondern die Bedingung dafür, dass die Statistik überhaupt für dich
arbeiten kann.

## 9.6 Portfolio-Ebene

**Das Korrelationsproblem:** 5 Altcoin-Long-Positionen bei 1 % Risiko sind nicht 5 % Risiko. In
einem Krypto-Ausverkauf laufen alle auf 1,0 Korrelation — es ist faktisch eine Position mit 5 %
Risiko.

**Gegenmaßnahme:**
```python
effective_risk = sum(position_risks) * sqrt(mean_correlation)
# Bei ρ = 1.0 zählt alles voll; bei ρ = 0 nur die Wurzel der Summe
```
Limit auf das **effektive** Risiko setzen, nicht auf das nominale. Rollierende Korrelationsmatrix
über 30/90 Tage berechnen.

**Diversifikation, die wirklich wirkt:** Nicht mehr Symbole, sondern **unkorrelierte
Strategietypen**. Trendfolge und Mean Reversion haben strukturell negative Korrelation — das ist
der stärkste einzelne Hebel für eine ruhige Equity-Kurve, wirksamer als jede weitere Optimierung
einer einzelnen Strategie.

---

# Teil X — Was du verknüpfen solltest

Die zentrale Frage aus deiner Aufgabe. Hier die priorisierte Antwort.

## 10.1 Priorisierung auf einen Blick

| Stufe | Was | Wann | Kosten |
|---|---|---|---|
| **Tier 1 — Pflicht** | Börsen-API, eigene Datenhaltung, Monitoring, Alerting, Steuer-Log | Sofort, Sprint 1–2 | ~0 € |
| **Tier 2 — Hoher Nutzen** | Derivatedaten (Funding/OI/Liquidationen), zweite Börse, Makro-Kalender | Sprint 5, mit Signalmodellen | 0–50 €/Monat |
| **Tier 3 — Später** | On-Chain, Sentiment/News, institutionelle Datenanbieter | Nach Live-Start | 30–800 €/Monat |
| **Tier 4 — Meist unnötig** | Signal-Abos, Copy-Trading, KI-"Prognose"-Dienste | — | — |

## 10.2 Tier 1 — Pflicht

### Börsenanbindung
| Anbindung | Zweck |
|---|---|
| **ccxt** (Python) | Einheitliches Interface zu ~100 Börsen. Börsenwechsel ohne Code-Umbau |
| **Native WebSocket** der Hauptbörse | Niedrige Latenz für Trades, Orderbuch, Kerzen. ccxt ist für REST gut, für Streams ist nativ besser |
| **Testnet der Hauptbörse** | Paper-Trading mit echtem API-Verhalten |

**Börsenwahl:** Binance (höchste Liquidität, beste Doku, umfangreichste Datenendpunkte) oder
Bybit (gute API, etwas einfacher, brauchbares Testnet). Spot-Gebühren beide ~0,10 % Basis, mit
Rabatten deutlich darunter. Rate-Limits unterscheiden sich strukturell: Binance arbeitet mit
einem **gewichtsbasierten** System (jeder Endpunkt kostet Gewichtspunkte, Budget pro Minute),
Bybit mit einem **rollierenden Zeitfenster pro Sekunde und UID**. Dein Rate-Limiter muss zum
jeweiligen Modell passen — ein generischer Limiter führt zu Sperren.

### Eigene Datenhaltung
| Komponente | Zweck |
|---|---|
| **TimescaleDB** | Zeitreihen-Datenbank für Kerzen, Trades, Features |
| **Parquet-Dateien** | Kalte historische Daten, günstig und schnell |
| **S3-kompatibler Speicher** (optional) | Backup off-site |

**Wichtig:** Rohdaten selbst speichern, nicht auf die Börsen-Historie verlassen. Börsen liefern
oft nur begrenzte Historie, ändern Formate und delisten Symbole. Deine eigene Datenbank ist
langfristig dein wertvollster Vermögenswert im Projekt — sie ermöglicht Backtests, die niemand
sonst laufen lassen kann.

### Betrieb und Steuerung
| Anbindung | Zweck |
|---|---|
| **Telegram Bot API** | Alerts und Fernsteuerung vom Handy. Kostenlos, minimaler Aufwand, riesiger Nutzen |
| **Prometheus + Grafana** | Metriken und Dashboards |
| **Sentry** (oder Ähnliches) | Exception-Tracking mit Kontext |
| **Healthchecks.io** | Externe Totmann-Überwachung — meldet, wenn dein Bot **nicht** meldet |

Der letzte Punkt wird oft vergessen: Wenn der ganze VPS ausfällt, kann dein eigenes Alerting dich
nicht warnen. Ein externer Dienst, der einen erwarteten Heartbeat vermisst, ist die einzige
Absicherung gegen den Totalausfall.

### Steuer und Buchhaltung
| Anbindung | Zweck |
|---|---|
| **Eigenes unveränderliches Trade-Log** | Pflicht. UTC-Zeit, Symbol, Menge, Preis, Gebühr, Order-ID |
| **CSV-Export** im Format von CoinTracking/Blockpit | Spart am Jahresende sehr viel Arbeit |

Das Format der etablierten Steuertools von Anfang an zu bedienen, kostet einen halben Tag und
spart später Wochen.

## 10.3 Tier 2 — Hoher Nutzen

### Derivate- und Positionierungsdaten
| Quelle | Liefert | Kosten |
|---|---|---|
| **Börsen-API selbst** | Funding Rate, Open Interest, Long/Short-Ratio, Taker Buy/Sell | Kostenlos |
| **CoinGlass** | Liquidations-Heatmaps, aggregiertes OI über alle Börsen, Funding-Vergleich | Freemium |

Der Großteil dieser Daten kommt **kostenlos aus der Börsen-API selbst** — Binance und Bybit
liefern Funding, OI, Long/Short-Ratio und Taker-Volumen über reguläre Endpunkte. Erst
aggregierte Liquidations-Heatmaps über alle Börsen hinweg brauchen einen Spezialanbieter. Fang
mit den kostenlosen Börsendaten an.

### Zweite Börse als Referenz
Zweck ist nicht Arbitrage, sondern **Datenqualität**: Ein Preis, der auf Börse A um 3 % abweicht
und auf Börse B nicht, ist ein fehlerhafter Tick oder ein lokaler Ausreißer — kein Signal. Diese
Absicherung kostet nichts und verhindert eine Klasse teurer Fehler.

### Makro-Kalender
| Quelle | Zweck |
|---|---|
| **Wirtschaftskalender-API** (z. B. Trading Economics, Finnhub) | FOMC, CPI, NFP — Termine für den Event-Filter |
| **Yahoo Finance / Stooq** (kostenlos) | Nasdaq, DXY, Gold für Korrelations-Features |

## 10.4 Tier 3 — Später, wenn die Basis steht

### On-Chain
| Anbieter | Stärke | Preis |
|---|---|---|
| **Glassnode** | 800+ On-Chain-Metriken, Standard für BTC/ETH-Fundamentaldaten | ab ~30 €/Monat, API teurer |
| **CryptoQuant** | Fokus auf Börsenflüsse und Markt-Timing | ähnlich |
| **Amberdata** | Hybrid CEX + DeFi, institutionell (2026 von Kaiko übernommen) | institutionell |
| **Kaiko** | Tick-Daten ab 2010, L2-Orderbuch ab 2015, BMR-konform | ab ~9.500 $/Jahr |

**Klare Empfehlung:** Kaiko und Amberdata sind institutionelle Produkte und für dieses Projekt
weit überdimensioniert. Glassnode oder CryptoQuant reichen völlig — und erst, wenn die
Basisstrategien nachweislich laufen. On-Chain-Signale sind langsam und ergänzen Swing-Strategien;
sie retten keine Strategie, die ohne sie nicht funktioniert.

### Sentiment und News
| Quelle | Nutzen | Realistische Einschätzung |
|---|---|---|
| **Fear & Greed Index** (alternative.me) | Kostenlos, einfach | Nur bei Extremwerten aussagekräftig. Aggregiert sehr unterschiedliche Signale in eine Zahl — dadurch grob |
| **News-API + LLM-Klassifikation** | Ereignisse in Echtzeit einordnen | Technisch machbar; Vorsicht vor Latenz und Halluzination |
| **Social Sentiment (X/Reddit)** | Stimmungsextreme | Stark verrauscht, manipulationsanfällig, Bot-Anteil hoch |

Forschung vergleicht GPT-4, BERT und FinBERT für Krypto-Sentiment 🎓 — die Modelle
funktionieren technisch, aber die Übersetzung in handelbaren Ertrag ist der schwierige Teil, nicht
die Klassifikation. Als **Risikofilter** ("bei extrem negativen Schlagzeilen Positionsgröße
halbieren") ist das leichter nutzbar als als Einstiegssignal.

## 10.5 Open-Source-Bausteine

Nicht alles selbst bauen. Was sich lohnt anzusehen:

| Projekt | Was es ist | Verwendung für uns |
|---|---|---|
| **Freqtrade** | Vollständiger Krypto-Bot in Python, ~48k GitHub-Sterne, 9 Jahre Entwicklung, gutes Backtesting mit Hyperopt und Walk-Forward | Referenzarchitektur — Backtest-Engine und Strategie-Interface sind sehr lehrreich |
| **NautilusTrader** | Event-getriebene Plattform, Rust-Kern mit Python-API, produktionsnah | Wenn Performance zum Thema wird; Architektur-Vorbild |
| **Hummingbot** | Market-Making-Framework, 140+ Venues | Nur relevant, falls Market Making dazukommt |
| **Backtrader** | Backtesting-Bibliothek | Reifer, aber nicht mehr aktiv weiterentwickelt |
| **ccxt** | Börsen-Abstraktionsschicht | ✅ Direkt verwenden |
| **pandas-ta / TA-Lib** | Indikatorbibliotheken | ✅ Direkt verwenden, spart viele Bugs |

**Entscheidung, die ansteht:** Freqtrade als Basis nehmen oder eigenständig bauen? Freqtrade
liefert Backtesting, Hyperopt, Exchange-Anbindung und Telegram-Steuerung fertig — Wochen an
Arbeit. Der Preis ist, sich an dessen Strategie-Modell zu binden, das für die geplante
Ensemble-/Regime-Architektur eher eng ist. Diese Frage stelle ich dir am Ende explizit.

## 10.6 Was du nicht verknüpfen solltest

| Kategorie | Warum nicht |
|---|---|
| **Bezahlte Signalgruppen / Copy-Trading** | Wenn die Signale funktionierten, würden sie gehandelt statt verkauft |
| **"KI-Prognose"-APIs** | Blackbox ohne prüfbare Methodik. Nicht validierbar = nicht nutzbar |
| **Broker mit Auszahlungsrechten im API-Key** | Unnötiges Totalverlustrisiko |
| **Börsen ohne Testnet** | Keine sichere Testmöglichkeit |
| **Zu viele Datenquellen zu früh** | Jede Quelle ist Ausfallpunkt, Kostenposition und Overfitting-Oberfläche |

## 10.7 Konkrete Empfehlung

**Minimal-Set für den Start (Kosten: ~5–15 €/Monat für den VPS, sonst nichts):**
```
Binance oder Bybit (Spot + Testnet)
  ├─ REST + WebSocket (Kerzen, Trades, Orderbuch)
  ├─ Funding Rate, Open Interest, Long/Short-Ratio  ← kostenlos in der API
  └─ Testnet für Paper-Trading
Zweite Börse (nur Preis-Referenz, kostenlos)
TimescaleDB (eigene Datenhaltung)
Telegram Bot (Alerts + Steuerung)
Healthchecks.io (externe Totmann-Überwachung)
Prometheus + Grafana (Metriken)
Wirtschaftskalender-API (Event-Filter)
```

Damit sind über 80 % des Nutzens abgedeckt. Alles Weitere kommt erst, wenn diese Basis
nachweislich läuft.

---

# Teil XI — Alpha-Zerfall: warum Strategien sterben

## 11.1 Lebensdauer von Edges

Aus Branchenauswertungen 🔶 — die Größenordnungen sind konsistent über verschiedene Quellen:

| Strategietyp | Typische Lebensdauer |
|---|---|
| Hochfrequenz | Tage bis Wochen |
| Momentum-Algorithmen | 3–6 Monate |
| Swing-/Positionssysteme | 6–18 Monate |
| Makro-/fundamental | 1–3 Jahre |

Selbst bei professionellen Quant-Fonds bleiben Strategien selten länger als 12 Monate wirksam.

**Das ist die wichtigste strukturelle Erkenntnis für die Architektur:** Ein Bot, der eine
Strategie ausführt, ist ein Wegwerfprodukt. Ein Bot, der eine **Pipeline zum Finden, Testen,
Aktivieren und Abschalten von Strategien** ist, ist ein dauerhafter Vermögenswert. Die
Architektur muss auf Strategiewechsel ausgelegt sein, nicht auf eine perfekte Strategie.

## 11.2 Die drei Zerfallsursachen

1. **Marktstruktur ändert sich** — Liquidität, Volatilitätsregime, Teilnehmerzusammensetzung.
   Beispiel: Der Bitcoin-Markt nach ETF-Einführung verhält sich messbar anders als davor
2. **Die Edge wird überfüllt** — mehr Teilnehmer auf demselben Signal → schlechtere Einstiege,
   höhere Slippage, das Signal arbitriert sich weg
3. **Die Edge war nie real** — Overfitting, das erst live sichtbar wird. Statistisch der
   häufigste Fall

## 11.3 Erkennung und Gegenmaßnahmen

**Erkennung:**
- Rollierende 30/90-Tage-Performance gegen die Backtest-Erwartung tracken
- Statistischer Test: Unterscheidet sich die Live-Renditeverteilung signifikant von der
  Backtest-Verteilung?
- Automatischer Alarm, wenn der Live-Drawdown den historischen Maximum-Drawdown überschreitet —
  das ist per Definition ein Zustand, den es historisch nie gab
- Trefferquote und Ø-R-Multiple pro Strategie einzeln überwachen

**Gegenmaßnahmen:**
- Regelmäßiges Neutrainieren auf rollierendem Fenster (etwa 3-Monats-Rhythmus — häufigere
  Modell-Updates zeigen in Untersuchungen konsistent bessere Ergebnisse)
- Automatische Herabgewichtung statt sofortiger Abschaltung: Ein Modell mit fallender Leistung
  bekommt weniger Kapital, bevor es ganz abgeschaltet wird
- **Portfolio von Edges** statt einer Strategie — mehrere unkorrelierte Ansätze parallel, damit
  der Ausfall eines einzelnen das System nicht stoppt
- Kontinuierliche Forschungspipeline: Es müssen immer neue Kandidaten im Shadow-Mode laufen

---

# Teil XII — Die wichtigsten Erkenntnisse kompakt

1. **Der Erwartungswert ist alles.** Trefferquote ist ein irreführendes Maß — 35 % Trefferquote
   mit 3:1-Verhältnis schlägt 80 % mit 1:5.
2. **Drawdowns sind asymmetrisch.** −50 % braucht +100 % zur Erholung. Deshalb ist
   Kapitalerhalt Arithmetik, nicht Vorsicht.
3. **Kosten sind der Hauptfilter.** 7.846 publizierte Handelsregeln verloren nach Kosten
   praktisch ihre gesamte Profitabilität. Frequenz ist kein freier Hebel.
4. **Hebel tötet Konten, nicht schlechte Strategien.** 10× Hebel = Liquidation bei 9,5 % — eine
   normale Krypto-Tageskerze.
5. **Kerzenmuster allein haben 50–55 % Trefferquote.** Der Sprung auf 60–70 % kommt vom Kontext,
   nicht vom Muster. Kodiere Kerzen als kontinuierliche Features, nicht als Muster-Detektoren.
6. **Kontext schlägt Signal.** Hammer und Hanging Man sind dieselbe Kerze — nur der vorherige
   Trend entscheidet. Das gilt für fast alle Umkehrmuster.
7. **Der höhere Zeitrahmen filtert, der niedrigere triggert.** Und im Backtest darf der höhere
   Zeitrahmen nur abgeschlossene Kerzen liefern.
8. **Regime-Erkennung entscheidet, welche Strategie laufen darf.** Mean Reversion im Trend ist
   der schnellste bekannte Weg, Geld zu verlieren.
9. **Volume Profile und VWAP sind aussagekräftiger als die meisten Indikatoren**, weil sie
   zeigen, wo tatsächlich gehandelt wurde — nicht, was ein geglätteter Preis macht.
10. **Liquidations-Daten sind der echte Krypto-Vorteil.** Erzwungene Orders sind vorhersagbar,
    weil Hebelstufen standardisiert sind.
11. **Extreme Funding Rates plus hohes OI plus dichte Liquidationscluster** — die Kombination ist
    das verlässlichste Warnsignal im Krypto-Markt. Einzeln sind alle drei schwach.
12. **Ein guter Backtest ist keine Evidenz.** Bei 888 real gehandelten Algorithmen erklärte der
    Backtest-Sharpe unter 3 % der Live-Performance.
13. **Walk-Forward oder nichts.** Einmalige Parameteroptimierung produziert zuverlässig
    wertlose Ergebnisse.
14. **Zähle deine Versuche.** Wer 100 Varianten testet, findet zufällig eine gute. Ohne diesen
    Zähler ist jede Sharpe-Angabe bedeutungslos.
15. **1–2 % Risiko pro Trade ist keine Vorsicht, sondern die Bedingung dafür, dass die Statistik
    für dich arbeitet.** Bei 10 % Risiko halbiert eine 7er-Verlustserie das Konto — und die kommt.
16. **Korrelation frisst Diversifikation.** 5 Altcoin-Longs sind eine Position, keine fünf.
17. **Fraktionales Kelly.** Halbes Kelly behält 75 % des Wachstums bei drastisch weniger Varianz.
18. **Der Stop muss als echte Order an der Börse liegen.** Ein Stop im Bot-Speicher schützt
    nicht, wenn der Bot der Grund für das Problem ist.
19. **Knight Capital verlor 440 Mio. USD in 45 Minuten durch ein inkonsistentes Deployment.**
    Deployment-Disziplin ist Risikomanagement.
20. **Jede Edge stirbt.** 3–18 Monate ist die typische Lebensdauer. Baue eine Pipeline zum Finden
    von Strategien, keine perfekte Strategie.
21. **Der Basis-Trade ist die einzige Ertragsquelle ohne Prognosebedarf** — als Grundlast
    sinnvoll, mit großzügigem Margin-Puffer.
22. **Deine eigene Datenbank ist der wertvollste Vermögenswert des Projekts.** Sie ermöglicht
    Tests, die niemand sonst laufen lassen kann.

---

# Quellen

**Akademisch 🎓**
- [Lo, Mamaysky, Wang — Foundations of Technical Analysis (Journal of Finance, 2000)](https://www.cis.upenn.edu/~mkearns/teaching/cis700/lo.pdf)
- [Bailey & López de Prado — The Deflated Sharpe Ratio](https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf)
- [Jegadeesh & Titman — Cross-Sectional and Time-Series Determinants of Momentum Returns](https://academic.oup.com/rfs/article-abstract/15/1/143/1619967)
- [Momentum: what do we know 30 years after Jegadeesh and Titman (Springer)](https://link.springer.com/article/10.1007/s11408-022-00417-8)
- [Algorithmic crypto trading using information-driven bars, triple barrier labeling and deep learning (Financial Innovation)](https://link.springer.com/article/10.1186/s40854-025-00866-w)
- [Explainable Patterns in Cryptocurrency Microstructure (arXiv)](https://arxiv.org/html/2602.00776v1)
- [Deep learning-based pairs trading: co-integrated cryptocurrency pairs (Frontiers)](https://www.frontiersin.org/journals/applied-mathematics-and-statistics/articles/10.3389/fams.2026.1749337/full)
- [LLMs and NLP Models in Cryptocurrency Sentiment Analysis (MDPI)](https://www.mdpi.com/2504-2289/8/6/63)
- [Overnight/Intraday Seasonality in Bitcoin (Quantpedia)](https://quantpedia.com/strategies/intraday-seasonality-in-bitcoin)
- [Order Flow Imbalance in Market Microstructure](https://www.emergentmind.com/topics/order-flow-imbalance)
- [Deflated Sharpe ratio (Wikipedia, Übersicht)](https://en.wikipedia.org/wiki/Deflated_Sharpe_ratio)

**Regulierung & Branchendaten 📊**
- [Why Most Traders Lose Money – 24 Statistics (ESMA-/CFTC-Zahlen)](https://tradeciety.com/24-statistics-why-most-traders-lose-money)
- [Why Retail Traders Lose Money: What the Data Actually Says](https://10pmtrader.com/why-retail-traders-lose-money/)
- [Knight Capital Case Study (PRMIA)](https://prmia.org/common/Uploaded%20files/eAI/PRMIA%20Case%20study%20-%20Knight%20Trading.pdf)
- [Software Testing Lessons from Knight Capital (CIO)](https://www.cio.com/article/286790/software-testing-lessons-learned-from-knight-capital-fiasco.html)
- [Binance Rate Limits (offizielle Doku)](https://developers.binance.com/docs/binance-spot-api-docs/rest-api/limits)
- [Bybit Rate Limit Rules (offizielle Doku)](https://bybit-exchange.github.io/docs/v5/rate-limit)
- [Krypto Steuer Deutschland 2026 — § 23 EStG, Haltefrist, DAC8 (Blockpit)](https://www.blockpit.io/de-de/steuer-guides/krypto-steuer-deutschland)
- [Krypto Steuern Deutschland 2026 (CoinTracking)](https://cointracking.info/de/steuer-guides/deutschland/krypto-steuern-2026/)

**Anbieter-/Blog-Backtests 🔶**
- [Study and Backtest of All 75 Candlestick Patterns (QuantifiedStrategies)](https://www.quantifiedstrategies.com/the-complete-backtest-of-all-75-candlestick-patterns/)
- [Candlestick Patterns Ranked by Backtest Performance](https://www.quantifiedstrategies.com/candlestick-patterns-ranked-by-backtest/)
- [Bulkowski on the Best Chart Patterns (thepatternsite)](https://thepatternsite.com/BestPatterns.html)
- [Bulkowski's Chart and Event Pattern Rank](https://www.thepatternsite.com/rank.html)
- [What 20 Weeks of Live Trading Revealed About Slippage](https://quanta72.substack.com/p/what-20-weeks-of-live-trading-revealed)
- [Realistic Backtesting: Transaction Costs, Slippage, Walk-Forward](https://www.hyper-quant.tech/research/realistic-backtesting-methodology)
- [Backtesting Series: Transaction Cost Modelling (Bocconi Students Investment Club)](https://bsic.it/backtesting-series-episode-5-transaction-cost-modelling/)
- [Alpha Decay in Trading: Why Strategies Stop Working](https://www.tradingengineeringlab.com/alpha-decay-in-trading-why-strategies-stop-working-over-time/)
- [Signal Decay Analysis: Understanding Alpha Lifecycles](https://microalphas.com/signal-decay-patterns/)
- [Bitcoin Futures Market Microstructure: Liquidation Cascades, Funding Regimes, OI](https://medium.com/@XT_com/bitcoin-futures-market-microstructure-liquidation-cascades-funding-regimes-and-open-interest-978b107b4889)
- [How to interpret crypto derivatives market signals (Gate Wiki)](https://www.gate.com/crypto-wiki/article/how-to-interpret-crypto-derivatives-market-signals-funding-rates-open-interest-and-liquidation-data-explained-20251227)
- [What Is Liquidation Cascade In Crypto Futures Trading (Mudrex)](https://mudrex.com/learn/what-is-liquidation-cascade-in-crypto-futures/)
- [Cash and Carry in Crypto: Delta-Neutral Funding Rate Strategy](https://www.buildix.trade/blog/cash-and-carry-crypto-delta-neutral-funding-rate-strategy-2026)
- [Crypto Funding Rate Arbitrage: Delta-Neutral Guide](https://arbitragescanner.io/blog/crypto-funding-rate-arbitrage-guide)
- [Volume Profile Trading: Complete 2026 Guide (Trading Wyckoff)](https://tradingwyckoff.com/en/volume-profile-2/)
- [Smart Money Concepts: Order Blocks, FVG and Liquidity (Trading Wyckoff)](https://tradingwyckoff.com/en/smart-money-concepts/)
- [Wyckoff Method Theory & Patterns (LiteFinance)](https://www.litefinance.org/blog/for-professionals/wyckoff-method/)
- [Multi-Timeframe Analysis Guide (Tradeciety)](https://tradeciety.com/how-to-perform-a-multiple-time-frame-analysis)
- [Hidden Markov Model Market Regimes (QuantifiedStrategies)](https://www.quantifiedstrategies.com/hidden-markov-model-market-regimes-how-hmm-detects-market-regimes-in-trading-strategies/)
- [Volatility Regime Detection: From Simple Rules to ML](https://volatilitybox.com/research/volatility-regime-detection/)
- [Kelly Criterion Position Sizing](https://astuteinvestorscalculus.com/the-kelly-criterion/)
- [Crypto Pairs Trading: Why Cointegration Beats Correlation (Amberdata)](https://blog.amberdata.io/crypto-pairs-trading-why-cointegration-beats-correlation)
- [Liquidation Price Calculation under Isolated Mode (Bybit Help Center)](https://www.bybit.com/en/help-center/article/Liquidation-Price-Calculation-under-Isolated-Mode-Unified-Trading-Account)
- [Cross vs isolated margin in perpetual futures (MetaMask)](https://metamask.io/news/cross-vs-isolated-margin-perps)
- [Martingale Bot vs Grid Bot (Phemex Academy)](https://phemex.com/academy/martingale-bot-vs-grid-bot)
- [Freqtrade vs Hummingbot vs CCXT (TrendRider)](https://trendrider.net/blog/freqtrade-vs-hummingbot-vs-ccxt-2026)
- [Trading Frameworks Übersicht (pytrade.org)](https://docs.pytrade.org/trading)
- [Best Crypto Market Data APIs (CoinCodeCap)](https://coincodecap.com/best-crypto-market-data-apis)
- [Crypto Exchange Fees Compared 2026](https://homecryptoinvest.com/articles/crypto-exchange-fees-2026.html)
- [DXY vs. Bitcoin: 2026 Correlation Shift (OSL)](https://www.osl.com/hk-en/academy/article/the-us-dollar-index-vs-bitcoin-why-the-inverse-correlation-matters)
- [Institutional Crypto Flows & 2026 Market Analysis (Amberdata)](https://blog.amberdata.io/institutional-crypto-flows-2026-market-analysis)
- [On-Chain Whale Activity 2026](https://mintarex.com/en/blog/reading-on-chain-whale-activity-2026)
- [Lessons from Algo Trading Failures (LuxAlgo)](https://www.luxalgo.com/blog/lessons-from-algo-trading-failures/)
