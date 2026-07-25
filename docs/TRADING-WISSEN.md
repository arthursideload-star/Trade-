# Trading-Wissensbasis

Rechercheergebnis für das Trading-Bot-Projekt.
Stand: 2026-07-25 (Recherche-Runde 2 — auf mehr als das Doppelte erweitert)

Dieses Dokument sammelt, was für den Bau des Bots und des Trading-Assistenten inhaltlich relevant
ist: wie im Markt Geld entsteht, wie man es schnell verliert, was Kerzen und Charts wirklich
aussagen, wie man Gelegenheiten maschinell erkennt und welche Datenquellen angebunden werden
sollten.

**Aufbau:** Teile I–XII sind die Grundlage aus Runde 1 (marktmechanik-, krypto- und
validierungsorientiert). Teile XIII–XXVI kamen in Runde 2 hinzu, mit Fokus auf **Forex** (Phase A,
Trading-Assistent), eine **vollständige Kerzen- und Chartmuster-Enzyklopädie**, **konkrete
Handelsstrategien mit vollständigen Regeln**, die vertieften Schulen (**SMC/ICT, Wyckoff, Elliott,
Fibonacci, harmonische Muster**), **Methodiken bekannter Trader** (Minervini, O'Neil, Stockbee,
Shapiro, PEAD, Druckenmiller, Turtles), **Trade-Management**, **Handelspsychologie** und die
konkrete **Abbildung des Wissens auf die Analyse-Engine des Assistenten**.

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

**Erweiterung 2026-07-25 (Recherche-Runde 2 — Forex-Fokus & Strategie-Tiefe):**
- [Teil XIII — Forex-Grundlagen und Marktmechanik](#teil-xiii--forex-grundlagen-und-marktmechanik)
- [Teil XIV — Kerzenmuster-Enzyklopädie](#teil-xiv--kerzenmuster-enzyklopädie)
- [Teil XV — Chartmuster-Enzyklopädie](#teil-xv--chartmuster-enzyklopädie)
- [Teil XVI — Konkrete Handelsstrategien mit vollständigen Regeln](#teil-xvi--konkrete-handelsstrategien-mit-vollständigen-regeln)
- [Teil XVII — Smart Money Concepts / ICT vertieft](#teil-xvii--smart-money-concepts--ict-vertieft)
- [Teil XVIII — Wyckoff vertieft](#teil-xviii--wyckoff-vertieft)
- [Teil XIX — Elliott Wave, Fibonacci, Harmonische Muster](#teil-xix--elliott-wave-fibonacci-harmonische-muster)
- [Teil XX — Methodiken bekannter Trader](#teil-xx--methodiken-bekannter-trader)
- [Teil XXI — Multi-Timeframe Top-Down-Workflow](#teil-xxi--multi-timeframe-top-down-workflow)
- [Teil XXII — Trade-Management vertieft](#teil-xxii--trade-management-vertieft)
- [Teil XXIII — Handelspsychologie und Prozessdisziplin](#teil-xxiii--handelspsychologie-und-prozessdisziplin)
- [Teil XXIV — News- und Event-Trading](#teil-xxiv--news--und-event-trading)
- [Teil XXV — Muster aus echten Trades](#teil-xxv--muster-aus-echten-trades)
- [Teil XXVI — Umsetzung im Trading-Assistenten](#teil-xxvi--umsetzung-im-trading-assistenten)
- [Teil XXVII — Indikatoren im Detail](#teil-xxvii--indikatoren-im-detail)
- [Teil XXVIII — Order-Typen, Spread, Slippage und Ausführung](#teil-xxviii--order-typen-spread-slippage-und-ausführung)
- [Teil XXIX — Risiko-Rechenbeispiele](#teil-xxix--risiko-rechenbeispiele)
- [Teil XXX — Backtest- und Journal-Metriken](#teil-xxx--backtest--und-journal-metriken)
- [Teil XXXI — Setup-Steckbriefe (Kurzreferenz)](#teil-xxxi--setup-steckbriefe-kurzreferenz)
- [Teil XXXII — Glossar A–Z](#teil-xxxii--glossar-az)
- [Teil XXXIII — Instrumentenprofile: der Charakter der Paare](#teil-xxxiii--instrumentenprofile-der-charakter-der-paare)
- [Teil XXXIV — Der schriftliche Handelsplan (Vorlage)](#teil-xxxiv--der-schriftliche-handelsplan-vorlage)
- [Teil XXXV — Zusätzliche Kernerkenntnisse (Runde 2)](#teil-xxxv--zusätzliche-kernerkenntnisse-runde-2)
- [Teil XXXVI — Einen Chart lesen: durchgerechnetes Beispiel](#teil-xxxvi--einen-chart-lesen-durchgerechnetes-beispiel)
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

# Teil XIII — Forex-Grundlagen und Marktmechanik

Dieser Teil kam mit dem Strategiewechsel zu Phase A (Trading-Assistent, Forex auf MT5-Demo)
hinzu. Der Krypto-Teil (Teil VII) bleibt für Phase B gültig. Forex und Krypto teilen die
Technik der Analyse, unterscheiden sich aber in Mechanik, Handelszeiten und Kostenstruktur.

## 13.1 Die Bausteine: Pip, Punkt, Lot, Spread

| Begriff | Definition | Beispiel |
|---|---|---|
| **Pip** | Kleinste "normale" Kursänderung; bei den meisten Paaren die 4. Nachkommastelle | EUR/USD 1,0842 → 1,0843 = 1 Pip |
| **Pip bei JPY-Paaren** | 2. Nachkommastelle | USD/JPY 148,52 → 148,53 = 1 Pip |
| **Pipette / Point** | Zehntel-Pip, 5. Nachkommastelle (bzw. 3. bei JPY) | 1,08425 → 1,08426 = 1 Point |
| **Lot (Standard)** | 100.000 Einheiten der Basiswährung | 1 Lot EUR/USD ≈ 108.420 $ Positionswert |
| **Mini-Lot** | 10.000 Einheiten (0,1 Lot) | Pip-Wert ≈ 1 $ |
| **Micro-Lot** | 1.000 Einheiten (0,01 Lot) | Pip-Wert ≈ 0,10 $ |
| **Spread** | Differenz Ask − Bid, die sofortige Kostenlast | EUR/USD oft 0,1–1,0 Pip |

**Pip-Wert-Formel** (für Paare mit USD als Notierungswährung, z. B. EUR/USD):

```
Pip-Wert = Lot-Größe × 0,0001
1 Standard-Lot: 100.000 × 0,0001 = 10 $ pro Pip
1 Micro-Lot:      1.000 × 0,0001 = 0,10 $ pro Pip
```

Für den Assistenten wichtig: **Alle Ziel-/Stop-Angaben werden zusätzlich in Pip und in Prozent
ausgegeben**, weil der Nutzer auf MT5 in Lot denkt, die Risiko-Rechnung aber in Prozent des
Kontos läuft. Ein Stop von 32 Pips bei EUR/USD ≈ 0,30 % Kursbewegung.

## 13.2 Die drei Handelssitzungen und warum die Uhrzeit alles ist 🔶

Forex läuft 24/5. Aber Volatilität und Liquidität sind extrem tageszeitabhängig. Kernzeiten
(UTC, Sommerzeit; im Winter jeweils −1 h beachten):

| Sitzung | Zeit (UTC) | Charakter |
|---|---|---|
| **Sydney** | 21:00–06:00 | Dünn, geringe Bewegung, weite Spreads |
| **Tokio (Asien)** | 00:00–09:00 | JPY-, AUD-, NZD-Paare aktiver; oft Range-Bildung |
| **London** | 07:00–16:00 | Höchstes Volumen der Welt; Trends starten hier |
| **New York** | 12:00–21:00 | USD-Nachrichten, zweite Volumenwelle |

**Das London–New-York-Overlap (ca. 12:00–16:00 UTC) ist das wichtigste Fenster.** Beide
größten Zentren sind gleichzeitig offen: engste Spreads, höchste Liquidität, größte Bewegungen
in EUR/USD, GBP/USD, USD/JPY. Für einen Assistenten, der kurze Trades vorschlägt, ist dieses
Fenster der ergiebigste Zeitraum. (Quelle: OANDA, FBS, Maven Trading — 🔶 Branchenkonsens.)

**Praktische Konsequenz für den Assistenten:**
- Ein Signal während des Asien-Nachmittags (dünnes Volumen) bekommt einen **Zeit-Malus** auf
  die Konfidenz.
- Die "London-Eröffnung" (07:00–09:00 UTC) und der Overlap-Beginn (12:00–13:00 UTC) sind die
  beiden häufigsten Zeitpunkte für saubere Ausbrüche.
- Freitagnachmittag (nach 19:00 UTC) und Sonntagabend-Eröffnung: dünn, sprunghaft, meiden.

## 13.3 Währungskorrelationen — Diversifikation ist oft eine Illusion 🔶

Korrelationen zwischen Paaren sind hoch und relativ stabil. Wer drei stark korrelierte Paare
gleichzeitig long ist, hat **eine** Position in dreifacher Größe, nicht drei Positionen.

| Paar-Beziehung | Typische Korrelation | Grund |
|---|---|---|
| EUR/USD ↔ GBP/USD | **+0,90 bis +0,95** | Eng verbundene Volkswirtschaften, beide gegen USD |
| EUR/USD ↔ USD/CHF | **−0,90 bis −0,95** | CHF läuft wie EUR, aber USD steht vorne → invers |
| AUD/USD ↔ NZD/USD | **+0,90+** | Beide Rohstoff-/China-getrieben |
| USD/CAD ↔ WTI-Öl | **stark negativ** | Kanada ist Ölexporteur |
| AUD/USD ↔ Gold/Kupfer | positiv | Australien ist Rohstoffexporteur |
| XAU/USD (Gold) ↔ DXY | **negativ** | Gold in USD notiert; starker USD = billigeres Gold |

(Quellen: Dukascopy, Mataf, DefcoFX — 🔶. Korrelationen driften; als Momentaufnahme, nicht als
Konstante behandeln. Der Assistent sollte sie rollierend über z. B. 20–60 Tage berechnen.)

**Regel für den Risk-Layer:** Wenn zwei offene/vorgeschlagene Trades |ρ| > 0,7 haben, zählen sie
gemeinsam auf das Risikobudget. Zwei gleichgerichtete Longs in EUR/USD und GBP/USD = 1,8-fache
Positionsgröße, nicht 2 × 1 %.

## 13.4 Der US-Dollar-Index (DXY) als übergeordneter Taktgeber

Der DXY misst den USD gegen einen Korb (EUR 57,6 %, JPY, GBP, CAD, SEK, CHF). Weil EUR/USD über
die Hälfte des Index ausmacht, ist DXY ↑ fast gleichbedeutend mit EUR/USD ↓. Für den Assistenten
ist der DXY-Trend ein **Kontextfilter**: Ein Long-Signal in EUR/USD gegen einen starken
DXY-Aufwärtstrend wird abgewertet.

## 13.5 Carry, Swap und Rollover

Wer eine Position über 22:00 UTC hält, zahlt oder erhält **Swap** — die Zinsdifferenz der beiden
Währungen. Long in einem Hochzinspaar gegen eine Niedrigzinswährung bringt positiven Carry, umgekehrt
Kosten. Für sehr kurze Trades (Intraday-Schließung) irrelevant; für Halten über Nacht ein realer
Posten, der ins Kostenmodell gehört (analog zu Funding in Krypto, Teil VII).

## 13.6 Was Forex von Krypto unterscheidet (Zusammenfassung)

| Dimension | Forex | Krypto-Perp |
|---|---|---|
| Handelszeit | 24/5, sitzungsabhängig | 24/7 |
| Wochenend-Gap | Ja (So-Eröffnung springt) | Nein |
| Zentrale Treiber | Zinsen, Makrodaten, Zentralbanken | Funding, OI, Liquidationen, On-Chain |
| Volatilität | niedriger (Majors ~0,5–0,8 %/Tag) | höher (BTC ~2–4 %/Tag) |
| Beste Zeit | London/NY-Overlap | rund um die Uhr, aber US-Handelszeit aktiver |
| Kostentreiber | Spread + Swap | Maker/Taker-Fee + Funding |

---

# Teil XIV — Kerzenmuster-Enzyklopädie

Ergänzt Teil III um eine vollständige, einzeln aufgeschlüsselte Musterliste. **Grundhaltung
bleibt (Teil III):** Isolierte Muster liegen bei 48–55 % Trefferquote; der Sprung auf 58–70 %
kommt ausschließlich aus Kontext (Ort im Chart, Trend, Volumen, Bestätigungskerze). Die
folgenden Prozentzahlen stammen aus Anbieter-/Blog-Backtests (🔶, u. a. LiberatedStockTrader
mit ~56.680 Trades, QuantifiedStrategies mit 75 Mustern) und sind als Rangordnung, nicht als
garantierte Erwartung zu lesen.

## 14.1 Anatomie-Wiederholung: die vier Zahlen

Jede Kerze kodiert Open, High, Low, Close. Daraus abgeleitet:
- **Körper** = |Close − Open| → Richtungsstärke der Periode
- **Oberer Docht** = High − max(Open, Close) → abgewiesene Aufwärtsbewegung
- **Unterer Docht** = min(Open, Close) − Low → abgewiesene Abwärtsbewegung
- **Range** = High − Low → Gesamtaktivität

Ein Muster ist nie mehr als eine bestimmte Kombination dieser Verhältnisse — deshalb ist die
Feature-Kodierung (Teil III, 3.8) der Mustererkennung überlegen: Sie erfasst dieselbe Information
kontinuierlich statt in willkürlichen Schwellen.

## 14.2 Einzelkerzen-Muster

| Muster | Form | Bedeutung im Kontext | Rohe Reliabilität 🔶 |
|---|---|---|---|
| **Hammer** | kleiner Körper oben, langer unterer Docht (≥ 2× Körper) | Am Support nach Abwärtstrend: Umkehr hoch | ~48 % roh, ~58 % mit Bestätigung, ~65 % am Support |
| **Hanging Man** | identisch zum Hammer | Am Widerstand nach Aufwärtstrend: Umkehr runter | schwächer als Hammer, braucht Bestätigung |
| **Inverted Hammer** | kleiner Körper unten, langer oberer Docht | Nach Abwärtstrend: mögliche Bodenbildung | mittel, Bestätigung nötig |
| **Shooting Star** | kleiner Körper unten, langer oberer Docht | Nach Aufwärtstrend am Widerstand: Umkehr runter | mittel-hoch am Widerstand |
| **Doji** | Open ≈ Close, Dochte beidseitig | Unentschlossenheit; nur an Extremen relevant | ~52 % (praktisch Zufall isoliert) |
| **Dragonfly Doji** | Open=Close oben, langer unterer Docht | Bullisch an Support | mittel |
| **Gravestone Doji** | Open=Close unten, langer oberer Docht | Bärisch an Widerstand | mittel |
| **Marubozu** | großer Körper, (fast) keine Dochte | Starke Fortsetzung in Körperrichtung | Fortsetzungssignal |
| **Spinning Top** | kleiner Körper, beide Dochte mittel | Momentumverlust, Vorstufe zur Wende | schwach allein |

**Der zentrale Kontextsatz (aus Teil III, hier vertieft):** Hammer und Hanging Man sind
**dieselbe Kerze**. Inverted Hammer und Shooting Star sind **dieselbe Kerze**. Was aus derselben
Form ein Kauf- oder Verkaufssignal macht, ist ausschließlich der vorausgegangene Trend und der
Ort (Support vs. Widerstand). Ein Bot, der Formen ohne Ort erkennt, erkennt nichts Handelbares.

## 14.3 Zwei-Kerzen-Muster

| Muster | Aufbau | Kontext | Reliabilität 🔶 |
|---|---|---|---|
| **Bullish Engulfing** | grüne Kerze umschließt vorherige rote vollständig | Am Support/nach Abwärtstrend | **60–65 %** mit Volumen & Level (Top-Rang) |
| **Bearish Engulfing** | rote Kerze umschließt vorherige grüne | Am Widerstand/nach Aufwärtstrend | **60–65 %** |
| **Bullish Harami** | kleine grüne Kerze im Körper der vorherigen großen roten | Trendabschwächung, Frühwarnung | schwächer als Engulfing |
| **Bearish Harami** | kleine rote im Körper der großen grünen | Trendabschwächung oben | mittel |
| **Tweezer Bottom** | zwei Kerzen mit fast identischem Low | Doppelte Abweisung nach unten | mittel, am Level stark |
| **Tweezer Top** | zwei Kerzen mit fast identischem High | Doppelte Abweisung nach oben | mittel |
| **Piercing Line** | rote Kerze, dann grüne schließt > 50 % in deren Körper | bullische Umkehr | mittel-hoch |
| **Dark Cloud Cover** | grüne Kerze, dann rote schließt > 50 % in deren Körper | bärische Umkehr | mittel-hoch |

**Warum Engulfing zuverlässiger ist:** Es kodiert einen echten Kräftewechsel — die neue Kerze
macht die gesamte Arbeit der vorherigen und mehr rückgängig. Das ist eine stärkere Aussage als
ein Docht. Deshalb rangiert es in fast allen Backtests oben.

## 14.4 Drei-Kerzen-Muster

| Muster | Aufbau | Bedeutung | Reliabilität 🔶 |
|---|---|---|---|
| **Morning Star** | große rote → kleine Kerze (Gap) → große grüne | starke bullische Umkehr am Boden | **~65–68 %** am Support (Spitzenrang) |
| **Evening Star** | große grüne → kleine Kerze (Gap) → große rote | starke bärische Umkehr oben | ~65 % |
| **Three White Soldiers** | drei aufeinanderfolgende große grüne Kerzen mit höheren Schlüssen | Starke Aufwärtsdynamik | **~61 %**, aber Vorsicht: oft schon überdehnt |
| **Three Black Crows** | drei große rote Kerzen mit tieferen Schlüssen | Starke Abwärtsdynamik | ~61 % |
| **Three Inside Up** | Bearish-Harami-Struktur + Bestätigungskerze | bullische Umkehr | mittel-hoch |
| **Rising/Falling Three Methods** | Trendkerze, drei kleine Gegenkerzen, Trendkerze | **Fortsetzung**, nicht Umkehr | Fortsetzungsmuster |

**Ranking-Konsens der Backtests 🔶** (bei Handel am relevanten Level, mit Volumenbestätigung):

1. Morning Star / Evening Star an Support/Widerstand — ~68 %
2. Bullish/Bearish Engulfing am Level mit Volumen — ~65 %
3. Hammer am Support im Aufwärtstrend — ~63 %
4. Three White Soldiers / Three Black Crows — ~61 %
5. Doji an Trendextremen — ~57 %

**Immer im Kopf behalten:** Diese Zahlen gelten *mit* Kontext. Dieselben Muster mitten in einer
Range oder ohne Volumen fallen auf ~50 % — Münzwurf minus Kosten.

## 14.5 Die drei Kontextfilter, die jedes Muster brauchen

Aus Teil III (3.7) übernommen und als Checkliste formuliert, die der Assistent pro Signal prüft:

1. **Ort:** Tritt das Muster an einem vorab markierten Level auf (Support/Widerstand, EMA,
   Bollinger-Band, POC/VWAP, Fib-Zone)? Ohne Level → kein Signal.
2. **Trendkontext:** Passt die implizierte Richtung zum übergeordneten Trend (Umkehrmuster nur
   am Ende eines Gegentrends, Fortsetzungsmuster mit dem Trend)?
3. **Bestätigung:** Schließt die Folgekerze in Signalrichtung? Ist das Volumen der Signalkerze
   über dem Durchschnitt? Erst dann gilt das Muster als bestätigt.

---

# Teil XV — Chartmuster-Enzyklopädie

Ergänzt Teil IV (4.3). Klassische Chartmuster sind größere Formationen über viele Kerzen. Die
Statistik stammt überwiegend aus Thomas Bulkowskis "Encyclopedia of Chart Patterns" (die einzige
groß angelegte, systematische Auswertung — 🔶, aber methodisch am seriösesten) und aus
Anbieter-Backtests. **Wichtige Ehrlichkeit vorweg:** Die im Netz kursierenden "89 %-Erfolgsquoten"
sind fast immer Rosinenpickerei. Bulkowskis eigene, nüchternere Kernzahl lautet: **nur etwa 51 %
der Muster erreichen ihr gemessenes Kursziel**, und Ausbrüche ohne Volumenbestätigung scheitern
fast doppelt so häufig. Die Muster sind nützliche Struktur, keine Wahrsagerei.

## 15.1 Umkehrmuster

| Muster | Aufbau | Signal | Kernzahlen 🔶 |
|---|---|---|---|
| **Head & Shoulders (Top)** | linke Schulter, höherer Kopf, rechte Schulter, Nackenlinie | bärische Umkehr bei Bruch der Nackenlinie | eines der zuverlässigsten Umkehrmuster; Bulkowski: ~14 % Fehlrate, Ø-Rückgang ~22 % |
| **Inverse H&S (Bottom)** | gespiegelt | bullische Umkehr | niedrigste Fehlrate der bullischen Muster (~11 %), Ø-Anstieg hoch |
| **Double Top ("M")** | zwei Hochs auf ähnlichem Niveau | bärisch bei Bruch des Zwischentiefs | ~88 % "Erfolg" in Blog-Zählungen, real: gemessenes Ziel seltener |
| **Double Bottom ("W")** | zwei Tiefs auf ähnlichem Niveau | bullisch bei Bruch des Zwischenhochs | eines der beliebtesten, robusten Bodenmuster |
| **Triple Top / Bottom** | drei Tests desselben Niveaus | Umkehr bei Bruch | Triple Bottom ~87 % in Blog-Statistik |
| **Rounding Bottom (Untertasse)** | langsame, runde Bodenbildung | bullisch, langsam | selten, aber verlässlich wenn sauber |

**Messregel (gemessenes Ziel / measured move):** Bei H&S ist das Kursziel die Höhe vom Kopf zur
Nackenlinie, projiziert vom Bruchpunkt nach unten. Bei Double Top/Bottom: Höhe der Formation,
projiziert vom Ausbruchspunkt. Der Assistent setzt daraus einen ersten Take-Profit-Vorschlag —
mit dem Hinweis, dass laut Bulkowski nur ~51 % dieses Ziel voll erreichen.

## 15.2 Fortsetzungsmuster

| Muster | Aufbau | Signal | Kernzahlen 🔶 |
|---|---|---|---|
| **Bull Flag** | steiler Anstieg (Pole), dann leichte Abwärts-Konsolidierung | Fortsetzung hoch bei Ausbruch | Flaggen gelten als sehr zuverlässig (Blog-Statistik teils > 80 %), kurze Muster |
| **Bear Flag** | steiler Fall, dann leichte Aufwärts-Konsolidierung | Fortsetzung runter | analog |
| **Pennant / Wimpel** | kleines symmetrisches Dreieck nach starkem Impuls | Fortsetzung | ähnlich Flagge, kurzlebig |
| **Ascending Triangle** | flache obere Linie, steigende Tiefs | meist bullischer Ausbruch | Fehlrate < 15 % in guten Trends |
| **Descending Triangle** | flache untere Linie, fallende Hochs | meist bärischer Ausbruch | Spiegelbild |
| **Symmetrical Triangle** | konvergierende Linien | Ausbruch in Trendrichtung wahrscheinlicher | richtungsneutral, Trend entscheidet |
| **Cup & Handle** | runde Basis + kleiner Rücksetzer (Henkel) | bullische Fortsetzung | O'Neil-/Minervini-Favorit, Fehlrate < 15 % |
| **Rising/Falling Wedge** | beide Linien geneigt, konvergierend | Rising Wedge meist bärisch, Falling meist bullisch | Umkehr *oder* Fortsetzung je nach Ort |

## 15.3 Die drei Fehlerquellen bei Chartmustern

1. **Bestätigungsfehler (Confirmation Bias) beim Zeichnen.** Ein Mensch (und ein schlecht
   gebauter Detektor) findet Muster, weil er sie sucht. Gegenmittel: objektive, testbare
   Definitionen (Pivot-Hochs/-Tiefs mit N Kerzen Abstand, Mindest-/Maximalhöhe, maximale
   Schulter-Asymmetrie in %).
2. **Ausbruch ohne Volumen.** Bulkowskis wichtigster Einzelbefund: Volumenbestätigung halbiert
   die Fehlrate. Ein Ausbruch bei unterdurchschnittlichem Volumen ist ein Verdachtsfall auf
   Fehlausbruch (siehe Teil VI, Liquidity Sweep).
3. **Der Fehlausbruch als eigenes Signal.** Ein gescheiterter Ausbruch aus einem Muster (Preis
   bricht, kehrt sofort zurück) ist oft ein stärkeres Signal in die *Gegenrichtung* als das
   Muster selbst — die gefangenen Trader müssen ihre Positionen glattstellen.

---

# Teil XVI — Konkrete Handelsstrategien mit vollständigen Regeln

Dieser Teil ist der praktischste des Dokuments: Jede Strategie ist als vollständiges Regelwerk
mit Einstieg, Stop, Ziel und Regime formuliert, sodass der Assistent (und später der Bot) sie
direkt umsetzen kann. Alle Strategien folgen der Grundregel aus Teil VI: **Setup + Trigger +
Invalidierung + Ziel**, nichts wird ohne definierten Stop gehandelt.

Legende: **TF** = Zeitrahmen, **SL** = Stop-Loss, **TP** = Take-Profit, **R** = Risiko-Einheit
(Abstand Einstieg↔Stop).

## 16.1 Trendfolge-Rücksetzer (das Arbeitspferd) 🎓-fundiert

Beste empirische Grundlage (Jegadeesh & Titman, Teil I). Kauft Stärke nach gesundem Rücksetzer.

- **Regime:** Aufwärtstrend. Filter: EMA 21 > 55 > 200 auf 1h und 4h; ADX(14) > 20.
- **Setup:** Preis zieht auf 15m in die EMA-21/55-Zone oder in die 38,2–61,8-%-Fib-Zone des
  letzten Impulses zurück.
- **Trigger:** Bullische Bestätigungskerze (Hammer/Bullish Engulfing) in der Zone, idealerweise
  mit RSI-Dreh aus < 40.
- **SL:** unter das Rücksetzer-Tief bzw. 1,5× ATR(14) unter Einstieg.
- **TP:** letzter Swing-High (1. Ziel), dann Trailing per Chandelier Exit (Teil XVI.10).
- **Mindest-R:R:** 1:2. Long-Spiegelbild im Abwärtstrend für Shorts.

## 16.2 Trendfolge-Ausbruch (Donchian / Range-Break)

- **Regime:** Kompression, die in Expansion übergeht. Bollinger-Bandbreite im unteren Perzentil.
- **Setup:** Klare horizontale Range oder Donchian-Kanal (20 Perioden) über mehrere Kerzen.
- **Trigger:** Schlusskurs außerhalb der Range **mit** Volumen über Durchschnitt.
- **SL:** zurück in die Range (unter die Ausbruchskante) oder 1,5× ATR.
- **TP:** Range-Höhe projiziert (measured move), Rest per Trailing.
- **Kritischer Filter:** Ausbruch ohne Volumen = Verdacht auf Fehlausbruch → nicht handeln oder
  auf Rücksetzer-Retest der Kante warten.

## 16.3 Moving-Average-Crossover (Trendfilter, kein Solo-Signal) 🔶

- **Klassik:** Golden Cross (50 über 200) bullisch, Death Cross bärisch. **Backtest-Realität
  (QuantifiedStrategies, 65 Jahre):** Als reines Ein-/Ausstiegssignal liefert es ungefähr
  Marktrendite bei deutlich reduziertem Drawdown — der Wert liegt in der Glättung, nicht in
  Überrendite. Ein getesteter Sweet Spot über 300 Jahre / 16 Märkte war **13/48-EMA**.
- **Bessere Verwendung:** Als **Regimefilter**, nicht als Trigger. Der 200-EMA trennt "nur Longs"
  von "nur Shorts"; der eigentliche Einstieg kommt aus 16.1/16.2.
- **Warnung:** In Seitwärtsphasen produziert jedes Crossover eine Serie von Fehlsignalen
  (Whipsaws). Deshalb immer mit ADX-Trendfilter kombinieren.

## 16.4 RSI/MACD-Divergenz (Umkehr-Frühwarnung) 🔶

- **Regular Bullish Divergence:** Preis macht tieferes Tief, RSI/MACD macht höheres Tief →
  Verkaufsdruck lässt nach → mögliche Umkehr **hoch**.
- **Regular Bearish Divergence:** Preis höheres Hoch, Indikator tieferes Hoch → Umkehr **runter**.
- **Hidden Bullish:** Preis höheres Tief, Indikator tieferes Tief → Trendfortsetzung hoch.
- **Hidden Bearish:** Preis tieferes Hoch, Indikator höheres Hoch → Fortsetzung runter.
- **Regel:** Divergenz **nie allein** handeln. Warten auf Preis-Bestätigung (Umkehrkerze am
  Level) + Volumen über 10-Perioden-Schnitt. Am zuverlässigsten am **Ende ausgedehnter,
  sauberer Trends** — je länger und klarer der Trend, desto aussagekräftiger die Divergenz.

## 16.5 Supply- & Demand-Zonen 🔶

- **Demand-Zone (Kaufzone):** Basis vor einem starken Anstieg (Drop-Base-Rally oder Rally-Base-
  Rally). **Supply-Zone (Verkaufszone):** Basis vor starkem Fall (Rally-Base-Drop).
- **Frische Zonen zählen.** Eine unberührte Zone hat die höchste Wahrscheinlichkeit; mit jedem
  Test werden Orders absorbiert und die Zone schwächt sich ab.
- **Einstieg:** Limit-Order an der **proximalen** Kante (die dem Preis zugewandte). Bei Demand:
  Buy-Limit an der Oberkante. Bei Supply: Sell-Limit an der Unterkante.
- **SL:** knapp hinter die **distale** Kante der Zone.
- **Top-Down-Pflicht:** Zone muss zum übergeordneten Trend passen (im Aufwärtstrend nur
  Demand-Zonen für Longs).

## 16.6 VWAP-Strategien (institutioneller Referenzpreis)

- **VWAP-Mean-Reversion (Range-Tag):** In ruhigen Sitzungen kehrt der Preis zum VWAP zurück.
  Abweichung > 2 Standardabweichungen (VWAP-Bänder) → Rückkehr zum VWAP als Ziel.
- **VWAP-Trend-Ride (Trend-Tag):** An Trendtagen ist der VWAP dynamischer Support/Widerstand;
  Rücksetzer an den VWAP von oben = Long-Chance im Aufwärtstrend.
- **Institutionelle Logik:** Große Adressen messen ihre Ausführung am VWAP; deshalb ist er ein
  echtes Ordermagnet-Niveau, kein geglätteter Indikator.

## 16.7 London-Breakout (Session-Strategie, forex-spezifisch) 🔶

- **Idee:** Die Asien-Sitzung bildet eine enge Range; die London-Eröffnung (07:00 UTC) bricht sie.
- **Setup:** Markiere Hoch/Tief der letzten Asien-Stunden (z. B. 00:00–07:00 UTC).
- **Trigger:** Buy-Stop knapp über dem Range-Hoch, Sell-Stop knapp unter dem Range-Tief.
- **SL:** die gegenüberliegende Range-Kante (oder Range-Hälfte). **TP:** 1–2× Range-Höhe.
- **Bestes Paar:** GBP/USD, EUR/USD. **Harte Warnung:** An Tagen mit Hochimpakt-News (NFP, CPI,
  Zinsentscheid) **nicht** anwenden — die Range bricht dann durch News, nicht durch Struktur, und
  reversed oft (siehe Teil XXIV).

## 16.8 Turtle-Trading (historisches Trendfolge-Regelwerk)

Das dokumentierte Regelwerk von Richard Dennis' "Turtles" — historisch bedeutsam, weil es zeigt,
dass ein **rein mechanisches** System profitabel sein kann:

- **System 1:** Kaufe bei 20-Tage-Hoch-Ausbruch, verkaufe bei 10-Tage-Tief.
- **System 2:** 55-Tage-Ausbruch, Ausstieg bei 20-Tage-Gegentief.
- **Positionsgröße:** über "N" (= ATR) volatilitätsnormiert; Einheit = 1 % Konto / (N × Punktwert).
- **Pyramiding:** Aufstocken alle ½N zugunsten des Trends, bis max. 4 Einheiten.
- **Lehre für uns:** Volatilitätsnormierte Größe + Ausbruch + strikter Ausstieg. Nicht 1:1
  kopieren (die Edge ist längst zerfallen, Teil XI), aber die **Struktur** ist vorbildlich.

## 16.9 Liquidity-Sweep / Stop-Hunt-Reversal (fortgeschritten)

- **Setup:** Klar sichtbares Swing-Hoch/-Tief, unter/über dem viele Stops liegen.
- **Trigger:** Preis schießt kurz über das Level (nimmt Liquidität), **schließt aber wieder
  zurück** in die Range (Fehlausbruch). Einstieg in Gegenrichtung des Sweeps.
- **SL:** knapp jenseits des Sweep-Extrems. **TP:** gegenüberliegende Liquidität / POC.
- **Logik:** Deckt sich mit ICT (Teil XVII) und Wyckoff-Spring (Teil XVIII) — dieselbe Mechanik
  unter drei Namen.

## 16.10 Ausstiegs-/Trailing-Bausteine für alle Strategien

- **Break-Even:** Stop auf Einstieg ziehen, wenn +1R erreicht — aber nicht reflexartig
  ("risikofreier Trade" ≠ Ziel); besser hinter Struktur ziehen.
- **Chandelier Exit (Chuck LeBeau):** Trailing-Stop = höchstes Hoch der letzten 22 Perioden − 3×
  ATR(22). Bleibt im Trend, steigt nur mit, fällt nie. Ideal für Trendfolge.
- **Partielles Schließen:** ⅓ bei 1. Ziel, ⅓ bei 2. Ziel, ⅓ mit Trailing laufen lassen.
  **Ehrlichkeitshinweis:** Zu frühes Teilschließen senkt den Erwartungswert des Systems — es
  fühlt sich sicher an, kostet aber die großen Gewinner, die das System tragen.

---

# Teil XVII — Smart Money Concepts / ICT vertieft

Ergänzt Teil IV (4.7). SMC/ICT ("Inner Circle Trader") ist die populärste Preisaktions-Schule
der letzten Jahre. **Ehrliche Einordnung vorweg (gilt für den ganzen Teil):** Vieles daran ist
umbenannte, altbekannte Marktstruktur (Support/Widerstand, Fehlausbruch, Angebot/Nachfrage). Es
gibt **keine** belastbare akademische Evidenz für eine eigenständige ICT-Edge; die Community-
"Backtests" sind selektiv. Trotzdem ist das Vokabular nützlich, weil es beschreibt, *wo Stops
liegen und wie sie geräumt werden* — und das ist reale Mechanik. Wir übernehmen die Konzepte als
**Struktur-Features**, nicht als Glaubenssystem.

## 17.1 Marktstruktur: BOS und CHoCH

- **BOS (Break of Structure):** Preis bricht ein vorheriges Swing-Hoch (im Aufwärtstrend) bzw.
  -Tief (im Abwärtstrend) → **Trendfortsetzung** bestätigt.
- **CHoCH (Change of Character):** Der erste Bruch **gegen** die bisherige Struktur (im
  Aufwärtstrend wird erstmals ein Swing-Tief gebrochen) → mögliche **Trendwende**. Frühwarnung.
- **Umsetzung:** algorithmisch über Pivot-Erkennung (Swing-Hoch/-Tief mit N Kerzen Bestätigung).
  Das ist dieselbe Marktstruktur-Logik wie in Teil IV.1, nur benannt.

## 17.2 Order Blocks

- **Definition:** Die letzte gegenläufige Kerze **vor** einem impulsiven Move. Ein bullischer
  Order Block ist die letzte rote Kerze vor einem starken Anstieg — dort haben (angeblich)
  Institutionen positioniert.
- **Handel:** Beim Retest des Order Blocks Einstieg in Impulsrichtung, SL hinter den Block.
- **Realität:** Funktional identisch zu einer frischen Demand-/Supply-Zone (Teil XVI.5). Der
  Mehrwert liegt in der präzisen Kerzen-Definition, nicht in Magie.

## 17.3 Fair Value Gap (FVG) / Imbalance

- **Definition:** Drei-Kerzen-Muster, bei dem der Docht der 1. und der 3. Kerze sich nicht
  überlappen — die mittlere (Impuls-)Kerze hinterlässt eine "Lücke", in der der Preis zu schnell
  war, um alle Orders zu füllen.
- **Erwartung:** Der Preis kehrt oft zurück, um die Lücke zu "füllen", bevor er weiterläuft →
  Einstiegszone auf dem Rücklauf.
- **Umsetzung:** einfach algorithmisch erkennbar (High[1] < Low[3] für bullische FVG). Als
  Feature: "Abstand des aktuellen Preises zur nächsten unfilled FVG".

## 17.4 Liquidität und Killzones

- **Liquidität:** Cluster von Stop-Orders über Swing-Hochs (buy-side liquidity) und unter
  Swing-Tiefs (sell-side liquidity). Institutionen brauchen diese Gegenorders, um große
  Positionen zu füllen.
- **Liquidity Sweep / Stop Hunt:** Preis läuft gezielt über/unter das Level, löst die Stops aus,
  dreht dann. Identisch zur Strategie in Teil XVI.9 und zum Wyckoff-Spring (Teil XVIII).
- **Killzones (Zeitfenster):** ICT betont bestimmte Zeitfenster (London-Open, NY-Open). Das
  überschneidet sich mit den realen Volatilitätsfenstern aus Teil XIII.2 — der handfeste Kern
  hinter dem Mystizismus.

## 17.5 Das idealtypische SMC-Setup (Konfluenz)

Ein "A+-Setup" nach SMC vereint mehrere Elemente: **Liquidity Sweep** eines Swing-Tiefs → **CHoCH**
(Strukturbruch nach oben) → Rücklauf in einen **Order Block**, der innerhalb einer **FVG** liegt,
im **Discount**-Bereich (untere Hälfte der Range). Vier Konfluenzen auf einem Trade. Für uns
übersetzt: Das ist ein hochbewertetes Konfluenz-Signal im Sinne von Teil VI.2 — mehrere
unabhängige Faktoren zeigen in dieselbe Richtung. Genau so soll es der Ensemble-Score erfassen,
ohne dass wir an eine geheime institutionelle Formel glauben müssen.

---

# Teil XVIII — Wyckoff vertieft

Ergänzt Teil IV (4.6). Die Wyckoff-Methode (Richard D. Wyckoff, 1930er) ist der **beste
verfügbare Rahmen für Marktphasen**, weil sie Volumen und Preis zusammen liest und eine
testbare Ereignisabfolge liefert. Der volle Zyklus: **Akkumulation → Markup → Distribution →
Markdown**.

## 18.1 Die drei Gesetze

1. **Angebot und Nachfrage:** Steigt Nachfrage über Angebot, steigt der Preis — und das zeigt
   sich zuerst im Volumen, dann im Preis.
2. **Ursache und Wirkung:** Die Größe der Handelsspanne (die "Ursache", gemessen über Volume
   Profile/Point&Figure) bestimmt die Reichweite der Folgebewegung (die "Wirkung").
3. **Aufwand und Ergebnis:** Großes Volumen (Aufwand) mit kleiner Preisbewegung (Ergebnis) =
   Absorption durch eine große Gegenpartei = Warnsignal für baldige Wende.

## 18.2 Akkumulations-Schema (Boden) — Phasen A–E

| Ereignis | Bedeutung |
|---|---|
| **PS (Preliminary Support)** | Erste Käufe nach langem Fall, Volumen zieht an |
| **SC (Selling Climax)** | Panik-Tief mit riesigem Volumen; Angebot erschöpft sich |
| **AR (Automatic Rally)** | Scharfe Erholung, da kaum Verkäufer übrig → definiert Range-Oberkante |
| **ST (Secondary Test)** | Rücktest des SC-Bereichs bei geringerem Volumen |
| **Spring / Shakeout** | **Fehlausbruch nach unten** unter die Range — räumt Stops schwacher Hände, dann schnelle Rückkehr. Das zentrale Kaufsignal, wenn mit niedrigem Volumen bestätigt |
| **Test** | Erneuter Test des Spring-Tiefs mit noch geringerem Volumen |
| **SOS (Sign of Strength)** | Breite Aufwärtskerze mit steigendem Volumen bricht die Range |
| **LPS (Last Point of Support)** | Höheres Tief nach dem SOS → Einstieg mit definiertem Stop |

Phasen: **A** = Stoppen des Abwärtstrends (PS, SC, AR, ST) · **B** = Aufbau der Ursache
(Absorption, längste Phase) · **C** = Test (Spring) · **D** = Markup-Beginn (SOS, LPS) ·
**E** = Ausbruch/Trend.

## 18.3 Distributions-Schema (Top) — das Spiegelbild

| Ereignis | Bedeutung |
|---|---|
| **PSY (Preliminary Supply)** | Erste großen Verkäufe nach langem Anstieg |
| **BC (Buying Climax)** | Euphorie-Hoch, riesiges Volumen, breite Kerze |
| **AR (Automatic Reaction)** | Scharfer Abverkauf → definiert Range-Unterkante |
| **UT / UTAD (Upthrust After Distribution)** | **Fehlausbruch nach oben** über die Range — fängt Ausbruchskäufer, dreht innerhalb 1–3 Kerzen. Das zentrale Verkaufssignal |
| **SOW (Sign of Weakness)** | Breite Abwärtskerze auf hohem Volumen bricht die Range → Markdown |

## 18.4 Die praktische Wyckoff-Regel für den Assistenten

Zwei Signaturen sind maschinell erfassbar und hochwertig:
- **Spring:** Preis unter das jüngste Range-Tief, Schluss aber wieder in der Range, **bei
  fallendem** Volumen → bullisch.
- **UTAD:** Preis über das jüngste Range-Hoch, Schluss wieder in der Range → bärisch.
- **Absorption:** hohes Volumen + kleine Range am Widerstand → verdächtig auf Distribution.

Diese decken sich mit Liquidity Sweep (Teil XVI.9/XVII.4) — der Assistent kann sie als **ein**
robustes Feature "Fehlausbruch mit Volumendivergenz" implementieren.

---

# Teil XIX — Elliott Wave, Fibonacci, Harmonische Muster

Diese drei gehören zusammen: Sie sind populär, optisch überzeugend und **methodisch am
schwächsten belegt** aller Werkzeuge in diesem Dokument. Sie kommen hier vollständig hinein,
weil der Nutzer sie in Videos sehen wird — aber mit klarer Warnung.

## 19.1 Elliott Wave

- **Grundstruktur:** Trends laufen in **5 Wellen** (Impuls: 1-2-3-4-5), Korrekturen in **3 Wellen**
  (A-B-C).
- **Die drei unverrückbaren Regeln:**
  1. Welle 2 läuft nie unter den Start von Welle 1 zurück.
  2. Welle 3 ist nie die kürzeste der Wellen 1/3/5 (meist die längste).
  3. Welle 4 überlappt nicht das Kursgebiet von Welle 1 (außer bei Diagonalen).
  Wird eine Regel verletzt, ist die Zählung falsch.
- **Fibonacci-Bezug:** Welle 2 korrigiert oft 50–61,8 % von Welle 1; Welle 3 ist oft 161,8 % von
  Welle 1; Welle 4 korrigiert oft 38,2 % von Welle 3.
- **Ehrliche Kritik 🔶:** Die Theorie ist **subjektiv und nicht mathematisch validierbar** —
  zwei Analysten zählen dieselbe Bewegung unterschiedlich. Zuverlässiger auf Tages-/Wochenchart
  als intraday (zu viel Rauschen). Lernkurve 1–2 Jahre. **Verwendung bei uns:** höchstens als
  grober Kontext ("stehen wir eher in einem Impuls oder einer Korrektur?"), niemals als Trigger.

## 19.2 Fibonacci-Retracements und -Extensions

- **Retracement-Level:** 23,6 % · 38,2 % · **50 %** · **61,8 %** (Golden Ratio) · 78,6 %.
- **Golden Pocket:** die Zone 50–61,8 %. Gesunde Korrekturen enden oft dort → bevorzugte
  Einstiegszone im Trend (deckt sich mit Teil XVI.1).
- **Extension-Level (Ziele):** 127,2 % · **161,8 %** · 261,8 % — für Take-Profit-Projektionen.
- **Stop-Platzierung:** knapp jenseits des nächsten Fib-Levels (z. B. bei Einstieg an 61,8 %
  Stop unter 78,6 %).
- **Wahrheit über Fibonacci 🔶:** Die Zahlen sind **keine Magie**. Sie funktionieren teils als
  selbsterfüllende Prophezeiung (viele schauen darauf) und sind **nur mit Konfluenz** brauchbar —
  ein Fib-Level, das mit einem Support, einer EMA oder einem POC zusammenfällt, ist wertvoll; ein
  isoliertes Fib-Level ist Dekoration.

## 19.3 Harmonische Muster (Gartley, Bat, Butterfly, Crab) 🔶

Präzise Fibonacci-Formationen mit den Punkten X-A-B-C-D; Einstieg bei D auf eine Umkehr.

| Muster | Kern-Ratio (D-Punkt) |
|---|---|
| **Gartley** | D bei 78,6 % Retracement von XA; B bei 61,8 % |
| **Bat** | D bei 88,6 % von XA; B bei 38,2–50 % |
| **Butterfly** | D bei 127,2 % **Extension** von XA (über X hinaus) |
| **Crab** | D bei 161,8 % Extension von XA — die extremste Variante |

- **Behauptete Trefferquote 🔶:** "> 70 %" — das stammt aus Anbieterquellen und ist **nicht
  unabhängig belegt**. Realistisch als "Zone erhöhter Umkehrwahrscheinlichkeit" behandeln, mit
  Bestätigung und engem Stop hinter D.
- **Verwendung bei uns:** optional, niedrig gewichtet, nur als zusätzlicher Konfluenzpunkt in
  einer bereits stimmigen Zone. Kein eigenständiges Signal.

**Gemeinsame Warnung für Teil XIX:** Alle drei Systeme sind **prognosestark im Rückblick,
schwach im Vorlauf**. Sie eignen sich, um Zonen zu markieren, nicht um allein Trades auszulösen.
Wir gewichten sie im Ensemble deutlich unter den evidenzbasierten Faktoren (Trend, Momentum,
Volumen, Level).

---

# Teil XX — Methodiken bekannter Trader

Konkrete, benannte Systeme erfolgreicher Trader. Ein Teil dieser Beschreibungen stammt aus einer
umfangreichen Trading-Skills-Sammlung, die im selben Git-Repository liegt (Branch
`claude-trading-skills`, 64 dokumentierte Skills mit Rechnern und Playbooks) — dort sind diese
Methodiken bereits als ausführbare Screener implementiert. Sie sind überwiegend für Aktien
entwickelt, ihre **Struktur** ist aber auf Forex/Krypto übertragbar.

## 20.1 Mark Minervini — VCP (Volatility Contraction Pattern) & SEPA

- **Kernidee:** Vor einem starken Ausbruch zieht sich die Volatilität in **immer engeren**
  Rücksetzern zusammen (z. B. −25 % → −12 % → −6 %). Das Angebot versiegt, eine kleine Nachfrage
  genügt für den Ausbruch.
- **Trend-Template (Vorfilter, alle müssen gelten):** Preis über 150- und 200-Tage-MA;
  150 > 200; 200-MA seit ≥ 1 Monat steigend; Preis ≥ 30 % über 52-Wochen-Tief; innerhalb 25 %
  des 52-Wochen-Hochs; relative Stärke hoch.
- **Einstieg:** Ausbruch über den **Pivot** (Hoch der letzten, engsten Kontraktion) mit
  Volumenschub.
- **Stop:** knapp unter den Pivot / die letzte Kontraktion — typisch eng (5–8 %), weil der
  Ausbruchspunkt per Definition nah am Tief liegt.
- **Übertragung:** "Enge Basis + Volumenkontraktion + Ausbruch mit Volumen" ist auch auf
  Intraday-Forex ein valides Setup (= Teil XVI.2, präzisiert).

## 20.2 William O'Neil — CANSLIM

Wachstums-Aktienmethode; als **Kontext-Checkliste** lehrreich (7 Komponenten):

| Buchstabe | Bedeutung |
|---|---|
| **C** | Current earnings — aktuelles Quartalsgewinnwachstum stark |
| **A** | Annual earnings — Jahresgewinnwachstum stark |
| **N** | New — neues Produkt/Management/Hoch |
| **S** | Supply & demand — kleine Streuung + Volumen im Ausbruch |
| **L** | Leader — relativer-Stärke-Führer, kein Nachzügler |
| **I** | Institutional sponsorship — steigende institutionelle Beteiligung |
| **M** | Market direction — nur kaufen, wenn der Gesamtmarkt im Aufwärtstrend ist |
| Zusatz | **Follow-Through Day** und **Distribution Days** zur Markttiming-Bestätigung |

**Lehre für uns (das "M"):** Nie gegen den übergeordneten Markt handeln. Für Forex heißt das:
DXY-/Index-Kontext beachten, bevor ein Einzelpaar gehandelt wird.

## 20.3 Stockbee — Momentum Burst (Kurzfrist-Swing)

Aus dem Playbook der Skills-Sammlung, ein 2–5-Tage-Swing:

- **Trigger (einer von drei):** 4-%-Ausbruch, Dollar-Ausbruch oder Range-Expansion — **immer
  über einer Liquiditätsschwelle**; der 4-%-Ausbruch und die Range-Expansion verlangen zusätzlich
  Volumen über dem Vortag.
- **Basis:** vorherige enge, range-kontrahierte Basis (dieselbe Idee wie VCP).
- **Wichtige Disziplin aus dem Playbook:** Ein bloßer 4-%-Move ist **nie** allein ein Kauf. Es
  folgt zwingend ein Chart-Check und eine Risiko-Distanz-Prüfung; ist der Stop zu weit für die
  Risikopolitik, ist es **kein Trade** (nicht: kleiner sizen).
- **Nicht verwechseln:** mit PEAD (Earnings-Drift, 2–6 Wochen) — anderes Zeithorizont-Kohort.

## 20.4 Post-Earnings Announcement Drift (PEAD) 🎓

- **Akademische Basis:** Ball & Brown (1968), Bernard & Thomas (1989) — Aktien, die auf positive
  Gewinnüberraschung hochspringen, driften **wochenlang weiter**. Eine der am besten
  dokumentierten Marktanomalien (Unterreaktion).
- **Handelbares Muster (Wochenkerzen):** Nicht den Gap-Tag jagen, sondern warten auf einen
  geordneten **roten Wochenrücksetzer** nach dem Gap, dann Einstieg, wenn eine **grüne
  Wochenkerze über dem Hoch der roten schließt**. Halten 2–6 Wochen.
- **Übertragung:** Das Prinzip "auf Überraschung folgt gerichteter Drift, aber kaufe den
  Rücksetzer, nicht die Spitze" gilt auch für Krypto nach großen Katalysatoren.

## 20.5 Jason Shapiro — COT-Contrarian (antizyklisch)

Aus dem `shapiro-contrarian`-Playbook — ein diszipliniertes Fade-System:

- **Idee:** Überfülltes spekulatives Positioning **faden** — aber Crowding allein ist **nie** ein
  Trade. Drei Bedingungen müssen zusammenkommen:
  1. **Crowding-Extrem** im COT-Report (3-Jahres-COT-Index-Extrem der Großspekulanten).
  2. **News-Reaction-Failure:** Der Markt reagiert **nicht** auf Nachrichten, die der überfüllten
     Seite helfen sollten → die Crowd liegt falsch.
  3. **Wochen-Preisaktion** dreht bereits gegen die Crowd (Key Reversal / Fehlausbruch).
- **Gate:** fail-closed — nur wenn **alle drei** bestätigt sind, wird überhaupt gesized.
- **Lehre für uns:** Das Muster "Sentiment-Extrem + ausbleibende Reaktion auf passende News +
  beginnende Gegenbewegung" ist ein starkes Umkehr-Konfluenzsignal. In Krypto ist das Pendant:
  extreme Funding Rate + Preis reagiert nicht mehr auf gute News + erste Gegenbewegung (Teil VII).

## 20.6 Stanley Druckenmiller — Makro & asymmetrische Größe

- **Liquiditätsanalyse** vor Fundamentaldaten: "Erst das Geld, dann die Kurse."
- **Konzentration statt Streuung:** wenige Trades mit hoher Überzeugung, groß gesized — aber mit
  striktem Verlust-Schnitt. "It's not whether you're right or wrong, but how much you make when
  right and how much you lose when wrong."
- **Lehre:** Erwartungswert wird von wenigen großen Gewinnern getragen; entscheidend ist, klein
  zu verlieren und die Gewinner laufen zu lassen — genau die Asymmetrie aus Teil I.

## 20.7 Was diese Methodiken gemeinsam haben

1. **Kontraktion vor Expansion** (VCP, Stockbee, Turtle): Enge Basen brechen sauberer aus.
2. **Nur mit dem übergeordneten Markt/Trend** (CANSLIM "M", Minervini Trend-Template).
3. **Definierte Invalidierung vor Einstieg** (alle) — ohne Stop kein Trade.
4. **Volumen bestätigt den Ausbruch** (alle Ausbruchssysteme).
5. **Erwartungswert aus Asymmetrie**, nicht aus hoher Trefferquote (Druckenmiller, Turtles).

Diese fünf Punkte sind die belastbarste Essenz aller erfolgreichen Systeme — sie decken sich mit
Teil VI und sind der Kern dessen, was der Assistent bewerten soll.

---

# Teil XXI — Multi-Timeframe Top-Down-Workflow

Der konkrete Analyse-Ablauf, den der Assistent bei jeder Anfrage durchläuft — von der großen zur
kleinen Zeitebene. Das ist die praktische Umsetzung von Teil IV.8 (Konfluenz) und die
Verdrahtung aller vorherigen Teile.

## 21.1 Die drei Ebenen und ihre Rollen

| Ebene | Zeitrahmen (Forex) | Frage | Werkzeuge |
|---|---|---|---|
| **Kontext** | 4h (+ 1d) | *Wohin darf ich überhaupt handeln?* | EMA-Fächer, ADX, Marktstruktur (BOS/CHoCH), große S/R-Zonen |
| **Setup** | 1h / 15m | *Wo ist eine konkrete Zone?* | Supply/Demand, Fib-Golden-Pocket, Volume Profile, Order Block |
| **Trigger** | 15m / 5m | *Wann genau steige ich ein?* | Kerzenmuster, RSI-Dreh, Mikro-BOS, Volumen |

**Eiserne Regel:** Die Trigger-Ebene darf nur in die Richtung feuern, die die Kontext-Ebene
erlaubt. Ein perfektes 5m-Kaufsignal gegen einen intakten 4h-Abwärtstrend wird **verworfen oder
stark abgewertet**, nicht gehandelt.

## 21.2 Der Ablauf Schritt für Schritt

```
1. KONTEXT (4h): Trend bestimmen (EMA-Fächer + ADX) → Regime setzen
   → erlaubte Richtung: nur Long / nur Short / kein Handel (Seitwärts)
2. KONTEXT (4h): große S/R-Zonen und offene Liquidität markieren
3. SETUP (1h/15m): konkrete Zone im erlaubten Bereich suchen
   (Demand/Supply, Golden Pocket, POC, Order Block) — muss "frisch" sein
4. KONFLUENZ prüfen: Wie viele unabhängige Faktoren zeigen zusammen?
   (Trend + Zone + Fib + Volumen + Struktur) → Score aus Teil VI.2
5. TRIGGER (15m/5m): auf Bestätigung in der Zone warten
   (Umkehrkerze + Momentum-Dreh + Volumen)
6. RISIKO: Stop hinter die Zone/Struktur, Größe aus 1 % Kontorisiko (Teil IX)
   → Mindest-R:R 1:2, sonst kein Trade
7. AUSGABE: Richtung, Konfidenz (aus Konfluenz-Score), Einstieg, SL, TP, R:R,
   Begründung (welche Faktoren) + Zeit-/News-Warnung
```

## 21.3 Warum Top-Down und nicht Bottom-Up

Wer auf dem 5m-Chart anfängt, sieht überall Signale — die meisten sind Rauschen innerhalb einer
größeren Struktur. Top-Down filtert das Rauschen weg, **bevor** es Konfidenz aufbaut. Das ist der
wichtigste Einzelhebel gegen Fehlsignale und deckt sich mit der Erkenntnis aus Teil XII.7 (höherer
Zeitrahmen filtert, niedrigerer triggert).

---

# Teil XXII — Trade-Management vertieft

Ergänzt Teil IX und Teil XVI.10. Der Einstieg ist der am meisten überschätzte Teil eines Trades;
**Management und Ausstieg** entscheiden über den Erwartungswert. 🔶

## 22.1 Die Einstiegsarten

| Art | Wann | Vor-/Nachteil |
|---|---|---|
| **Limit an der Zone** | Preis läuft in die geplante Zone | Bester Preis, aber Nicht-Ausführung möglich |
| **Stop-Einstieg (Breakout)** | Ausbruch bestätigen lassen | Verpasst keinen Move, aber schlechterer Preis |
| **Bestätigungskerze abwarten** | Umkehr-Setups | Weniger Fehlsignale, etwas später dran |

Der Assistent gibt eine **konkrete Einstiegsmethode** aus, nicht nur "kaufen" — inklusive der
Warnung, dass Limit-Orders in der Zone nicht garantiert gefüllt werden (analog Post-Only in Krypto).

## 22.2 Stop-Loss: die vier Typen

1. **Struktur-Stop:** hinter das letzte Swing-Hoch/-Tief oder die Zonenkante. **Bevorzugt** —
   folgt der Marktlogik.
2. **Volatilitäts-Stop (ATR):** 1,5–3× ATR je nach Zeitrahmen (Scalp 1,0–1,5× · Day 1,5–2,5× ·
   Swing 2,0–3,0×). Passt sich der Marktaktivität an.
3. **Prozent-Stop:** fester %-Abstand. Einfach, aber ignoriert Struktur — nur als Notnagel.
4. **Zeit-Stop:** Wenn das Setup nach X Kerzen nicht in Gewinn läuft, schließen. Fängt "tote"
   Trades, die Kapital binden.

**Regel:** Der Stop wird aus der **Struktur** bestimmt, dann wird die **Größe** so gewählt, dass
der Stop 1 % Konto kostet — nie umgekehrt. Den Stop an eine gewünschte Größe anzupassen ("ich
will größer rein, also enger Stop") ist einer der häufigsten Kontokiller.

## 22.3 Break-Even, Trailing, Teilverkäufe — die Erwartungswert-Falle

- **Break-Even:** Stop auf Einstieg bei +1R ist verlockend ("risikofrei"), **schneidet aber
  Gewinner ab**, die kurz zurückkommen, bevor sie laufen. Besser: hinter die nächste Struktur
  ziehen, nicht mechanisch auf Einstieg.
- **Trailing:** verbessert das R:R im Trend, killt es aber, wenn zu eng — ein geplantes 1:3 wird
  real oft 1:1. Chandelier Exit (Teil XVI.10) ist der beste Kompromiss.
- **Teilverkäufe:** ⅓/⅓/⅓ fühlt sich gut an, **senkt aber den Erwartungswert**, weil die
  großen Gewinner (die das System tragen) beschnitten werden. Nur einsetzen, wenn die
  Psychologie es sonst nicht aushält — bewusst als Komfort-, nicht als Optimierungs-Maßnahme.

## 22.4 Risiko-Ertrags-Verhältnis und nötige Trefferquote

Der Zusammenhang, den jeder Trade-Vorschlag zeigen sollte:

| R:R | Break-Even-Trefferquote | Kommentar |
|---|---|---|
| 1:1 | 50 % | plus Kosten → real > 52 % nötig |
| 1:1,5 | 40 % | |
| **1:2** | **34 %** | Standardziel des Assistenten |
| 1:3 | 25 % | selten sauber erreichbar (Trailing kollabiert oft) |

**Erwartungswert (das Fundament, Wiederholung aus Teil I):**
```
E = (Trefferquote × Ø-Gewinn) − (Verlustquote × Ø-Verlust) − Kosten
```
Ein System mit 40 % Treffern und 1:2 R:R hat positiven Erwartungswert; ein System mit 70 %
Treffern und 1:0,5 R:R kann negativ sein. **Der Assistent optimiert auf E, nicht auf Trefferquote.**

---

# Teil XXIII — Handelspsychologie und Prozessdisziplin

Auch bei einem halbautomatischen Assistenten trifft am Ende **ein Mensch** die Klick-Entscheidung.
Und selbst beim späteren Vollautomaten ist der Mensch das schwächste Glied — er greift ein,
übersteuert den Bot, dreht das Risiko hoch nach Verlusten. Deshalb gehört Psychologie in die
Wissensbasis. 🔶/📊

## 23.1 Die harte Zahl

70–90 % der Privattrader verlieren über die Zeit Geld; ESMA nennt 74–89 % für CFD-Konten (📊,
deckt sich mit Teil II). **Der entscheidende Befund der Verhaltensforschung:** Die meisten
verlieren **nicht wegen einer falschen Strategie, sondern weil sie eine funktionierende Strategie
nicht konsequent umsetzen.** Angst, Gier, Selbstüberschätzung und Rache übersteuern den Plan —
oft innerhalb von Minuten nach einem Gewinn oder Verlust.

## 23.2 Die teuersten Denkfehler

| Fehler | Mechanik | Gegenmittel im System |
|---|---|---|
| **Revenge Trading** | Nach Verlust sofort neuer Trade ohne Setup, nur um zurückzuholen | Tages-Verlust-Limit (−3 %) → Handelssperre; der Bot verweigert nach Limit weitere Einstiege |
| **Overtrading** | Aus Langeweile/Aufregung zu viele Trades → Kosten fressen alles | Max. 3 Trades/Tag/Symbol (V3); Konfidenzschwelle |
| **Verluste laufen lassen** | Hoffnung statt Stop; "wird schon zurückkommen" | Stop als **echte Order**, nicht im Kopf |
| **Gewinner zu früh nehmen** | Angst, den Gewinn zu verlieren → Erwartungswert sinkt | Trailing statt fixem Frühausstieg; Teil XXII.3 |
| **Selbstüberschätzung nach Gewinnserie** | Größe hochdrehen, Regeln lockern | Feste Größenregel im Code (Teil IX), nicht diskretionär |
| **FOMO** | Einem Move hinterherspringen, der schon gelaufen ist | Nur an geplanten Zonen einsteigen, nie mitten im Move |
| **Anchoring** | Am Einstiegspreis kleben ("erst wenn ich wieder bei 0 bin") | Entscheidung nur nach Setup-Status, nicht nach P&L |

**Eine Studie (2024, 🔶):** Trader mit fester Vor-Trade-Routine (inkl. emotionalem Check) hatten
**34 % höhere Plan-Treue**. Zahl "78 % der Revenge-Trader verlieren binnen 6 Monaten mehr als
ihre Einzahlung" ist plausibel, aber Blog-Quelle — als Warnung, nicht als Fakt.

## 23.3 Warum ein Bot hier hilft — und wo er selbst gefährdet ist

**Vorteil Automatisierung:** Ein Bot kennt keine Angst, keine Rache, keine Langeweile. Er setzt
die Regeln stur um. Das ist der eigentliche Grund, warum systematischer Handel dem
diskretionären im Durchschnitt überlegen ist — nicht bessere Prognose, sondern **konsequente
Ausführung**.

**Restrisiko Mensch:** Der Nutzer kann den Bot übersteuern (Position manuell vergrößern, Stop
wegnehmen, "nur dieses eine Mal" gegen die Regel). Deshalb: Risikolimits **im Code** (CLAUDE.md-
Grundsatz), Änderungen brauchen einen Commit. Das ist bewusst unbequem — Unbequemlichkeit ist
hier ein Feature.

## 23.4 Prozess über Ergebnis

Der wichtigste mentale Rahmen: **Ein guter Trade ist ein regelkonformer Trade — unabhängig vom
Ergebnis.** Ein Gewinn aus Regelbruch ist ein schlechter Trade (er verstärkt schlechtes
Verhalten). Ein Verlust aus einem korrekt ausgeführten, positiv-Erwartungswert-Setup ist ein
guter Trade. Über viele Trades zahlt der Prozess, nicht das Einzelergebnis. Das Trade-Journal
(Phase A, Sprint A5) bewertet deshalb **Prozesstreue**, nicht nur P&L.

---

# Teil XXIV — News- und Event-Trading

Makro-Ereignisse bewegen Forex stärker und schneller als jedes Chartmuster. Der Assistent muss
sie **kennen**, um zu warnen — nicht unbedingt, um sie zu handeln. 🔶

## 24.1 Die Ereignisse mit dem größten Impact

| Ereignis | Was | Wirkung auf Majors |
|---|---|---|
| **NFP** (Non-Farm Payrolls) | US-Arbeitsmarkt, 1. Freitag/Monat, 12:30 UTC | 80–150+ Pips in Minuten, **berüchtigt für Reversals** |
| **CPI** (Inflation) | monatlich | sehr hoch, treibt Zinserwartung |
| **FOMC / Zinsentscheid** | Fed, 8×/Jahr, + Pressekonferenz | 100–400 Pips möglich, oft in der Pressekonferenz mehr als in der Zahl |
| **EZB / BoE / BoJ** | Zinsentscheide | analog für EUR/GBP/JPY |
| **GDP, PMI, Retail Sales** | Konjunktur | mittel |

## 24.2 Der Kernmechanismus: Überraschung, nicht Niveau

**Der Markt bewegt sich nicht, weil eine Zahl hoch oder niedrig ist, sondern weil sie von der
Erwartung abweicht.** Kommt CPI exakt wie erwartet, passiert oft fast nichts ("priced in").
Weicht die Zahl stark ab, springt der Preis über mehrere Paare gleichzeitig. Das ist dasselbe
Prinzip wie "what's priced in" im Quant-Framework (Teil XXV) und wie die News-Reaction-Failure
bei Shapiro (Teil XX.5).

## 24.3 Zwei legitime Umgangsweisen

1. **Meiden (Standard für den Anfänger-Assistenten):** In den ~30 Minuten um ein Hochimpakt-
   Ereignis **keine** Signale ausgeben bzw. mit dickem Warnhinweis. Spreads explodieren, Stops
   werden gerissen, Slippage ist massiv. Für kurze, technische Trades ist das der sicherste Weg.
2. **Straddle/Breakout (fortgeschritten, riskant):** Vor der Zahl Buy-Stop über und Sell-Stop
   unter die enge Vor-News-Range, um die erste Bewegung zu fangen. **Gefahr:** NFP reversed oft
   80 Pips in einer Richtung und komplett zurück binnen 15 Min → beide Seiten können ausgelöst und
   gestoppt werden. Nur mit reduzierter Größe und weitem Verständnis.

## 24.4 Regel für den Assistenten

Der Assistent zieht einen **Wirtschaftskalender** (Forex Factory / Twelve Data / Finnhub) und
markiert Hochimpakt-Ereignisse für das gewählte Paar. Standardverhalten: **Signale um solche
Ereignisse mit einem roten Warnbanner versehen und die Konfidenz auf "handle nicht" setzen.**
Der London-Breakout (Teil XVI.7) und alle technischen Setups werden an News-Tagen ausgesetzt.

---

# Teil XXV — Muster aus echten Trades

Was das Beobachten vieler echter Trading-Sessions (Videos, Journale, die Skills-Sammlung) immer
wieder zeigt — die wiederkehrenden Wahrheiten jenseits der Theorie.

## 25.1 Der 7-Schichten-Signal-Stack (aus dem Quant-Framework der Skills-Sammlung)

Ein Trade verdient nur dann Kapital, wenn die Schichten 1–5 **übereinstimmen**:

```
1. Makro-Regime      → Risk-on / Risk-off / Übergang
2. Thema / Sektor    → läuft der übergeordnete Kontext mit?
3. Screener/Setup    → konkretes Muster (Trend, Ausbruch, Umkehr)
4. Setup-Bestätigung → Chart/Trigger stimmt visuell
5. Was ist eingepreist? → Abweichung von der Erwartung = Chance
6. Sizing            → R-Multiples, Positionsgröße
7. Postmortem        → Journal, was hat funktioniert
```

Die **Kill-Regel** dazu: Jeder Trade braucht **vor** dem Einstieg (a) eine schriftliche These,
(b) ein Invalidierungskriterium ("was macht diese These falsch") und (c) nach dem Ausstieg einen
Journaleintrag. Keine Ausnahmen. Das *ist* das manuelle Review-Gate.

## 25.2 Die zehn wiederkehrenden Beobachtungen

1. **Die großen Gewinner sind wenige.** Ein Großteil des Jahresertrags kommt aus einer Handvoll
   Trades. Wer diese früh abschneidet (Teil XXII.3), zerstört das System.
2. **Die meisten Verluste kommen aus wenigen Fehlern**, oft demselben (Regelbruch nach Verlust).
3. **Fehlausbrüche sind allgegenwärtig.** Der erste Ausbruch aus einer Range scheitert häufig;
   der Retest ist oft der bessere Einstieg.
4. **Volumen verrät die Wahrheit.** Ausbruch ohne Volumen = Misstrauen. Absorption (viel Volumen,
   wenig Bewegung) = bevorstehende Wende.
5. **Der Trend ist zäher, als man denkt.** Trendfolge verliert die meisten Trader, weil sie zu
   früh gegen den Trend wetten ("das muss doch mal drehen").
6. **Enge Basen brechen sauber aus** (VCP, Stockbee, Turtle). Weite, wilde Basen brechen unsauber.
7. **Die erste Stunde einer Sitzung** (London-Open, NY-Open) trägt einen Großteil der Bewegung.
8. **Runde Zahlen und Vortageshoch/-tief** sind reale Magnete (Stops liegen dort).
9. **Nach starken Trendtagen folgt oft eine Range** — Regime wechselt, Strategie muss mitwechseln.
10. **Die meisten "Signale" sind Rauschen.** Nichtstun ist die häufigste korrekte Entscheidung.
    Ein gutes System handelt selten.

## 25.3 Die Anti-Muster (woran man Scharlatanerie erkennt)

Direkt aus der Auswertung des EasyTrading-Bots (Teil-Entscheidungen E5/E5b) verallgemeinert:

- **Wechselnde Richtung ohne neue Information** = keine Analyse.
- **Einsatz nach Verlust erhöhen** (Martingale) = eingebauter Totalverlust (Teil II.4).
- **Sekunden-"Zeitrahmen"** = keine handelbare Marktinformation, nur Rauschen.
- **"OTC"-Instrumente / anbietergenerierte Kurse** = kein echter Markt.
- **Gewinn-Screenshots ohne Verlust-Kontext** = Überlebenden-Verzerrung.
- **"Signal"-Anzeigen ohne Funktion für die Entscheidung** = Dekoration zum Verkauf von Credits.

Wenn ein "Bot" oder eine "Challenge" eines dieser Merkmale zeigt, ist es kein Trading.

---

# Teil XXVI — Umsetzung im Trading-Assistenten

Wie das gesamte Wissen dieses Dokuments konkret in die Analyse-Engine des Assistenten (Phase A,
PLAN.md) einfließt. Das schließt den Kreis von Theorie zu Code.

## 26.1 Von Wissen zu Feature — die Abbildung

| Wissensteil | Feature im Assistenten |
|---|---|
| Trend (Teil V, XVI.1/3) | EMA-Fächer-Ausrichtung + ADX + Regressionssteigung, je TF |
| Regime (Teil IV.1, VI.2) | ADX-Schwelle + Volatilitäts-Perzentil → Trend/Range/Volatil |
| Kerzen (Teil III, XIV) | kontinuierliche Körper-/Docht-Features + benannte Muster **nur am Level** |
| Chartmuster (Teil XV) | objektive Pivot-Definitionen, Volumen-Bestätigung erzwungen |
| S/R, Zonen (IV.2, XVI.5, XVII.2) | horizontale Level-Cluster, frische Demand/Supply-Zonen |
| Volume Profile / VWAP (IV.4/5, XVI.6) | POC/HVN/LVN, VWAP-Abweichung in σ |
| Fehlausbruch/Spring (XVI.9, XVIII, XVII.4) | ein Feature "Sweep + Rückschluss + Volumendivergenz" |
| Fibonacci (XIX.2) | Golden-Pocket-Zone, **nur** als Konfluenz mit anderem Level |
| News (XXIV) | Wirtschaftskalender-Flag → Konfidenz-Veto |
| Sitzungen/Zeit (XIII.2) | Zeit-Gewichtung der Konfidenz (Overlap = voll, Asien-Nachmittag = Malus) |
| Korrelation (XIII.3) | rollierende Korrelationsmatrix → Risikobudget-Bündelung |

## 26.2 Der Konfidenz-Score (Zusammenführung)

Der Ausgabe-Konfidenzwert ist ein gewichteter Konfluenz-Score (Teil VI.2), **regime-abhängig**
umgewichtet, plus harte Vetos:

```
Konfidenz-Basis = Σ (Faktor_Score × Regime_Gewicht)
  Faktoren: Trend-Ausrichtung (Multi-TF), Momentum, Kerze-am-Level,
            Volumen, Zonen-/S-R-Nähe, Fehlausbruch-Signatur

Vetos (setzen Konfidenz → "nicht handeln"):
  - Signal gegen den 4h-Trend (außer klares Umkehr-Regime)
  - Hochimpakt-News in < 30 Min
  - dünne Sitzung (Asien-Nachmittag, Freitagabend)
  - R:R < 1:2 nicht erreichbar
  - Zone bereits mehrfach getestet (nicht mehr frisch)
```

## 26.3 Die Ausgabe-Karte (was der Nutzer sieht)

Jede Empfehlung enthält verbindlich: **Richtung** (Long/Short/Abwarten), **Konfidenz %**,
**Einstiegsmethode** (Limit an Zone / Stop-Breakout / Bestätigung abwarten), **Stop-Loss**
(in Preis, Pip und %), **Take-Profit** (in Preis, Pip, % und R:R), **Regime**, **Begründung**
(welche Faktoren zusammenkamen) und **Warnungen** (News, Zeit, Korrelation). Nie nur "kaufen" —
immer das vollständige, nachvollziehbare Bild, damit der Nutzer lernt statt blind zu folgen.

## 26.4 Was der Assistent bewusst NICHT tut

- **Keine Sekunden-Trades.** Untergrenze ist der 5m-Trigger, geplant für Halten über Minuten bis
  Stunden — nicht die 1-Sekunden-Wetten der Binäroptionen-Apps (Teil XXV.3).
- **Keine Prognose als Sicherheit.** Konfidenz ist Wahrscheinlichkeit, nicht Vorhersage.
- **Keine Größenerhöhung nach Verlusten.** Nie Martingale/Grid (V7).
- **Kein Handel ohne Stop.** Jede Empfehlung hat eine definierte Invalidierung.

Damit ist der Assistent die praktische, entschärfte, ehrliche Umsetzung genau dessen, was der
Nutzer in den Videos gesehen hat — nur auf einem echten Markt, mit echten Positionen, echtem
Stop-Loss und ohne die eingebauten Verlustmechaniken.

---

# Teil XXVII — Indikatoren im Detail

Ergänzt Teil V um die konkrete Mechanik jedes wichtigen Indikators: Formel, Standardeinstellung,
Signal und — am wichtigsten — die typische Fehlanwendung. **Grundsatz aus Teil V bleibt:** Kein
Indikator ist ein Signal, jeder ist nur eine Umformung des Preises. Wert entsteht durch
Kombination *unkorrelierter* Indikatoren, nicht durch das Stapeln von fünf Trendindikatoren, die
alle dasselbe sagen.

## 27.1 Trendindikatoren

**Gleitende Durchschnitte (SMA/EMA)**
- **Formel EMA:** `EMA_t = Preis_t × k + EMA_{t-1} × (1−k)`, mit `k = 2/(N+1)`. EMA reagiert
  schneller als SMA, weil jüngere Kerzen stärker gewichtet werden.
- **Übliche Perioden:** 21 (kurz), 50 (mittel), 200 (lang). Der EMA-Fächer (8/21/55/200) zeigt
  Trend + Trendstärke auf einen Blick: sauber gestaffelt = starker Trend, verschlungen = Range.
- **Fehler:** In Seitwärtsphasen produziert jedes Crossover Whipsaws. Immer mit ADX-Trendfilter
  kombinieren (Teil XVI.3).

**ADX / DMI (Average Directional Index)**
- Misst **Trendstärke**, nicht Richtung. +DI und −DI zeigen die Richtung, ADX die Kraft.
- **Lesart:** ADX < 20 = kein Trend (Range) · 20–25 = Trend beginnt · > 25 = starker Trend · > 40
  = sehr stark, evtl. überdehnt.
- **Zentrale Rolle:** ADX ist der beste einzelne **Regime-Schalter** — er entscheidet, ob
  Trendfolge- oder Mean-Reversion-Strategien laufen dürfen.

**Ichimoku Kinko Hyo ("Ein-Blick-Gleichgewicht")** 🔶
- Sechs Komponenten aus Hoch/Tief-Mittelwerten (Goichi Hosoda, 1930er):
  - **Tenkan-sen** (Wandlung) = (9-Perioden-Hoch + 9-Tief)/2 — kurzfristig
  - **Kijun-sen** (Basis) = (26-Hoch + 26-Tief)/2 — mittelfristig, dynamischer Support
  - **Senkou Span A** = (Tenkan + Kijun)/2, 26 Perioden **in die Zukunft** projiziert
  - **Senkou Span B** = (52-Hoch + 52-Tief)/2, 26 Perioden vorprojiziert
  - **Kumo (Wolke)** = Fläche zwischen Span A und B — Support/Widerstand-Zone
  - **Chikou Span** = Schlusskurs, 26 Perioden **zurück** versetzt — Bestätigungsfilter
- **Signale:** Preis über der Wolke = Aufwärtstrend; Tenkan/Kijun-Kreuzung = Trigger; Kumo-Twist
  (Span A kreuzt B) = vorausschauender Trendwechsel; Kumo-Breakout = Ausbruchsstrategie.
- **Fehler:** überladen auf niedrigen Zeitrahmen; am besten auf 1h+ und als Trendfilter, nicht
  als alleiniges Signal.

## 27.2 Momentum-Indikatoren

**RSI (Relative Strength Index)**
- **Formel:** `RSI = 100 − 100/(1+RS)`, `RS = Ø-Gewinn / Ø-Verlust` über N (Standard 14).
- **Lesart:** > 70 überkauft, < 30 überverkauft — **aber:** in starken Trends bleibt RSI lange
  überkauft/überverkauft. Überkauft ist **kein** Verkaufssignal im Aufwärtstrend.
- **Beste Nutzung:** (a) **Divergenz** (Teil XVI.4), (b) RSI-Dreh aus dem Extrem *am Level* als
  Bestätigung, (c) 40/60 als Trend-Bias-Grenze (im Aufwärtstrend hält RSI über 40).

**MACD (Moving Average Convergence Divergence)**
- **Formel:** MACD-Linie = EMA(12) − EMA(26); Signallinie = EMA(9) der MACD-Linie; Histogramm =
  MACD − Signal.
- **Signale:** MACD kreuzt Signallinie (Trigger); Nulllinien-Kreuzung (Trendwechsel); Histogramm-
  Divergenz (Momentumverlust, Frühwarnung).
- **Fehler:** nachlaufend; in Ranges viele Fehlsignale. Stärke liegt in der Divergenz.

**Stochastik (%K / %D)**
- Misst, wo der Schluss innerhalb der jüngsten Hoch-Tief-Range liegt. %K schnell, %D geglättet.
- **Lesart:** > 80 überkauft, < 20 überverkauft; %K/%D-Kreuzung im Extrem als Trigger.
- **Beste Nutzung:** in Range-Regimen für Mean-Reversion; im Trend unbrauchbar allein.

## 27.3 Volatilitäts-Indikatoren

**ATR (Average True Range)**
- **Formel:** True Range = max(Hoch−Tief, |Hoch−Vorschluss|, |Tief−Vorschluss|); ATR = Ø(TR) über
  N (Standard 14). Erfasst auch Gaps.
- **Nutzung:** **Stop-Abstand** (1,5–3× ATR je Stil) und **Positionsgröße** (Teil IX/XXII).
  Formel: `Größe = (Konto × Risiko%) / (ATR × Multiplikator)`. Die Position schrumpft automatisch,
  wenn die Volatilität steigt — gleiches Geldrisiko bei ruhigem wie bei wildem Markt.
- **Kein Richtungssignal**, reines Maß für "wie weit bewegt sich das hier normal".

**Bollinger Bands**
- **Formel:** Mittelband = SMA(20); obere/untere Bänder = ± 2 Standardabweichungen.
- **Signale:** Preis am oberen Band = relativ hoch; **Squeeze** (Bänder eng) = niedrige
  Volatilität vor Ausbruch; **Band-Walking** (Preis läuft am Band entlang) = starker Trend, kein
  Umkehrsignal.
- **Fehler:** "Band berührt = Umkehr" ist falsch im Trend. Bollinger misst *relative* Lage, nicht
  Richtung.

**Keltner Channel + der Squeeze**
- Keltner = EMA(20) ± 1,5× ATR. Nutzt ATR statt Standardabweichung.
- **BB/KC-Squeeze (John Carter):** Wenn die Bollinger Bands **komplett innerhalb** des Keltner
  Channels liegen, ist die Volatilität außergewöhnlich niedrig → **Kompression vor Expansion**.
  Der Ausbruch (mit Volumen) aus dem Squeeze ist ein hochwertiges Setup (deckt sich mit Teil
  XVI.2). Standard: BB(20; 2σ) + KC(20; 1,5× ATR).

## 27.4 Volumen-Indikatoren

**OBV (On-Balance Volume)**
- Kumuliert Volumen: +Volumen an grünen Kerzen, −Volumen an roten. Steigender OBV bestätigt
  Aufwärtstrend; OBV-Divergenz zum Preis = Warnung.
- **Forex-Einschränkung:** Echtes Volumen fehlt im dezentralen Spot-Forex; MT5 zeigt nur
  **Tick-Volumen** (Anzahl Kursänderungen) als Näherung. Für Krypto/Perp ist echtes Volumen
  verfügbar und aussagekräftiger.

**VWAP** — siehe Teil IV.5 und XVI.6 (institutioneller Referenzpreis, Ordermagnet).

## 27.5 Pivot Points (Intraday-Level) 🔶

Vorab berechnete Support/Widerstand-Level aus den Vortageswerten — beliebt bei Daytradern, weil
viele darauf schauen (teils selbsterfüllend).

- **Standard-Pivot:** `P = (Hoch + Tief + Schluss) / 3`; darum R1/S1, R2/S2, R3/S3.
- **Camarilla (Nick Scott, 1989):** acht Level aus der Vortages-Range mit Fibonacci-Multiplikatoren
  (0,0916 · 0,183 · 0,275 · 0,55). Wichtigste Level: **R3/S3** (Ausbruchszone) und **R4/S4**
  (Extrem-Umkehrzone).
- **Fibonacci-Pivot:** klassischer Pivot ± 38,2/61,8/100 % der Vortages-Range.
- **Nutzung:** Als zusätzliche horizontale Konfluenz-Level, nicht als eigenständiges Signal.

## 27.6 Der Redundanz-Test (aus Teil V, hier als Regel)

Vor Aufnahme eines Indikators ins Ensemble: **Liefert er Information, die die vorhandenen nicht
schon haben?** RSI, Stochastik und Williams %R sind fast dieselbe Information (Momentum-Oszillator)
— drei davon sind nicht dreimal so gut, sondern einmal mit dreifachem Rechenaufwand. Ein gutes
Set kombiniert je einen aus Trend / Momentum / Volatilität / Volumen / Struktur — fünf
*unkorrelierte* Blickwinkel.

---

# Teil XXVIII — Order-Typen, Spread, Slippage und Ausführung

Die beste Analyse ist wertlos, wenn die Order schlecht ausgeführt wird. Ergänzt Teil VI.5 (Krypto)
um die allgemeine und forex-spezifische Ausführung. 🔶

## 28.1 Die Order-Typen

| Typ | Was | Garantie |
|---|---|---|
| **Market** | sofort zum besten verfügbaren Preis | Ausführung garantiert, **Preis nicht** |
| **Limit** | nur zu Preis X oder besser | Preis garantiert, **Ausführung nicht** |
| **Stop (Market)** | wird bei Preis X zur Market-Order | fängt Ausbruch/Stop-Loss, **Slippage-Risiko** |
| **Stop-Limit** | wird bei X zur Limit-Order zu Y | Preis kontrolliert, kann leer ausgehen bei schnellem Move |
| **Trailing Stop** | Stop läuft im Gewinn mit | sichert Gewinn, kann bei Rücksetzer früh auslösen |
| **OCO (One-Cancels-Other)** | zwei Orders verknüpft, eine löscht die andere | für gleichzeitiges TP + SL |
| **OTO (One-Triggers-Other)** | Ausführung der einen aktiviert die andere | für automatisches Setzen von SL/TP nach Einstieg |

## 28.2 Spread — die stille Dauerkost

Der Spread (Ask − Bid) wird bei **jedem** Ein- und Ausstieg bezahlt. Bei EUR/USD oft 0,1–1,0 Pip,
bei exotischen Paaren und in dünnen Zeiten deutlich mehr. **Konsequenz:** Der Trade startet immer
im Minus (um den Spread). Für kurze Trades ist der Spread relativ zur Zielbewegung groß — deshalb
gehört er ins Signal-Filter (Teil VI.4): Ziel muss ein Vielfaches des Spreads sein.

## 28.3 Slippage — wann die Ausführung wehtut

Slippage = Differenz zwischen erwartetem und tatsächlichem Fill-Preis. **Drei Szenarien mit
extremer Slippage:**
1. **Geplante News** (NFP, FOMC, CPI): Spreads weiten sich um das 5–20-fache für 30–60 Sekunden.
2. **Gap-Eröffnungen** (Forex Sonntagabend, Aktien-Open): Preis springt über die angezeigten Level.
3. **Dünne Liquidität** (Off-Session, exotische Paare): schon kleine Orders bewegen den Preis.

Ein Stop-Loss als Market-Order kann in diesen Momenten weit jenseits des geplanten Niveaus
gefüllt werden — der Grund, warum News-Zeiten gemieden werden (Teil XXIV).

## 28.4 Die Ausführungsregeln für den Assistenten/Bot

- **Einstieg:** bevorzugt Limit an der Zone (bester Preis), mit dem ehrlichen Hinweis, dass er
  nicht gefüllt werden könnte. Für Ausbrüche: Stop-Einstieg mit einkalkulierter Slippage.
- **Stop-Loss:** immer als **echte Order an der Börse/beim Broker**, nie nur im Speicher (Teil
  XII.18). Ein Stop im Bot-Kopf schützt nicht, wenn der Bot abstürzt.
- **TP + SL zusammen:** als OCO setzen, damit nie eine offene Position ohne Absicherung existiert.
- **Slippage messen:** jeden Fill mit dem erwarteten Preis vergleichen und die Differenz ins
  Kostenmodell zurückspeisen (Teil VI.5) — der Backtest wird dadurch mit der Zeit realistischer.

---

# Teil XXIX — Risiko-Rechenbeispiele

Ergänzt Teil IX mit konkreten Zahlen, damit der Nutzer die Mathematik greifen kann. Alle
Beispiele mit dem realistischen Startkapital des Projekts.

## 29.1 Positionsgröße aus 1 % Kontorisiko

**Gegeben:** Konto 30 €, Risiko 1 % = 0,30 € pro Trade. EUR/USD, Einstieg 1,0850, Stop 1,0820
(30 Pips).

```
Risiko in Pip     = 30 Pips
Erlaubter Verlust = 0,30 €
Erlaubter €/Pip   = 0,30 € / 30 = 0,01 €/Pip
Micro-Lot bringt  = 0,10 €/Pip → nötig: 0,01/0,10 = 0,1 Micro-Lot
```

**Ergebnis:** Bei 30 € Konto ist selbst ein Micro-Lot (0,01 Lot) für 1 % Risiko bei 30-Pip-Stop
**zu groß** — das Konto ist zu klein für sauberes Risikomanagement in Forex. Genau der Befund aus
PLATTFORM-VERGLEICH.md. **Konsequenz:** Auf MT5-Demo mit größerem virtuellem Konto üben; echtes
Geld erst bei ausreichender Kapitalbasis. Der Assistent rechnet die Größe trotzdem korrekt aus und
sagt ehrlich, wenn die Mindestgröße das Risikolimit sprengt → **kein Trade** (nicht: Limit erhöhen).

## 29.2 Dieselbe Rechnung mit 1.000 € (Demo/Ziel)

```
Risiko 1 % = 10 €; Stop 30 Pips → erlaubt 0,333 €/Pip → ~3 Micro-Lot (0,03 Lot). Sauber machbar.
```

Das zeigt, warum Kapital schrittweise aufgebaut wird: Erst ab einer gewissen Größe erlaubt die
Mindestordergröße überhaupt diszipliniertes Risiko.

## 29.3 Drawdown-Erholung (die Asymmetrie in Zahlen)

| Verlust | Nötiger Gewinn zur Erholung |
|---|---|
| −10 % | +11,1 % |
| −20 % | +25 % |
| −33 % | +50 % |
| **−50 %** | **+100 %** |
| −75 % | +300 % |
| −90 % | +900 % |

`Erholung = 1/(1−Verlust) − 1`. Deshalb ist Kapitalerhalt keine Vorsicht, sondern Arithmetik
(Teil I.4). Ein Konto, das man halbiert, muss sich verdoppeln — das schafft kaum jemand.

## 29.4 Verlustserien — was normal ist

Bei 50 % Trefferquote ist die Wahrscheinlichkeit für **N Verluste in Folge** irgendwann in einer
Serie von 100 Trades:

| Serie | Einzelwahrscheinlichkeit | In 100 Trades fast sicher? |
|---|---|---|
| 5 in Folge | 3,1 % | ja, kommt vor |
| 7 in Folge | 0,8 % | wahrscheinlich |
| 10 in Folge | 0,1 % | selten, aber möglich |

**Konsequenz:** Bei 10 % Risiko pro Trade halbiert eine 7er-Serie das Konto (Teil XII.15). Bei
1 % kostet dieselbe Serie 7 % — unangenehm, aber überlebbar. Die Serie **kommt**; die Frage ist
nur, ob das Konto sie übersteht.

## 29.5 Erwartungswert eines Systems durchgerechnet

**System A:** 40 % Treffer, Ø-Gewinn 2R, Ø-Verlust 1R.
```
E = 0,40 × 2R − 0,60 × 1R = 0,80R − 0,60R = +0,20R pro Trade  → profitabel
```
**System B:** 70 % Treffer, Ø-Gewinn 0,5R, Ø-Verlust 1R.
```
E = 0,70 × 0,5R − 0,30 × 1R = 0,35R − 0,30R = +0,05R pro Trade  → kaum profitabel
```
Nach Kosten (z. B. 0,1R/Trade) ist System B **negativ**, System A klar positiv — obwohl B
"öfter recht hat". Das ist der Kern von Teil I: **Trefferquote täuscht, Erwartungswert zählt.**

---

# Teil XXX — Backtest- und Journal-Metriken

Wie der Assistent misst, ob seine Signale funktionieren. Ergänzt Teil VIII. Das Trade-Journal
(Phase A, Sprint A5) ist das wichtigste Werkzeug, um aus Meinung Evidenz zu machen.

## 30.1 Die Kennzahlen, die zählen

| Metrik | Formel / Bedeutung | Zielrichtung |
|---|---|---|
| **Trefferquote (Win Rate)** | Gewinner / alle Trades | allein irreführend (Teil I) |
| **Erwartungswert / Expectancy** | (WR × Ø-Gewinn) − (LR × Ø-Verlust) | **> 0 nach Kosten** — die Kernmetrik |
| **Profit Factor** | Bruttogewinn / Bruttoverlust | > 1,3 brauchbar, > 1,7 gut |
| **Ø-R-Multiple** | mittleres Ergebnis in R pro Trade | > 0,1R solide |
| **Max Drawdown** | größter Peak-to-Trough-Rückgang | so klein wie möglich |
| **Sharpe / Sortino** | Rendite pro Risikoeinheit (Sortino nur Abwärtsrisiko) | > 1 ordentlich |
| **MAE (Max Adverse Excursion)** | tiefster Punkt gegen dich während des Trades | zeigt, ob Stops zu weit/eng |
| **MFE (Max Favorable Excursion)** | bester Punkt für dich während des Trades | zeigt, ob Ziele zu nah (Geld liegen gelassen) |

**MAE/MFE-Analyse** ist der praktischste Journal-Hebel: Wenn viele Gewinner erst weit ins Minus
liefen (hohe MAE), ist der Einstieg zu früh. Wenn viele Trades den TP knapp verfehlten und
zurückkamen (hohe MFE, kleiner Realgewinn), sind die Ziele zu weit.

## 30.2 Die Validierungsregeln (aus Teil VIII, verdichtet)

1. **Out-of-Sample oder nichts.** Auf Fenster A optimieren, auf Fenster B messen (Walk-Forward).
2. **Versuche zählen.** Wer 100 Varianten testet, findet zufällig eine gute — Deflated Sharpe.
3. **Realistisches Kostenmodell.** Spread + Slippage + (Krypto) Funding immer einrechnen.
4. **Selbsttest der Engine.** Eine Zufallsstrategie muss exakt die Kosten als Verlust zeigen;
   zeigt sie Gewinn, hat die Backtest-Engine einen Bug (Look-Ahead).
5. **Parameter-Robustheit.** Bricht das Ergebnis bei ±20 % Parameteränderung zusammen, ist es an
   die Vergangenheit angepasst und live wertlos.

## 30.3 Das Journal-Schema (was pro Trade festgehalten wird)

```
Datum/Zeit (UTC) · Paar · Richtung · Setup-Typ · Regime ·
Einstieg · Stop · Ziel · geplantes R:R · Positionsgröße ·
Konfidenz-Score des Assistenten · These (1 Satz) · Invalidierung ·
Ergebnis (R) · MAE · MFE · Ausstiegsgrund · Prozess-Note (regelkonform ja/nein)
```

Die **Prozess-Note** ist bewusst getrennt vom Ergebnis: Ein regelkonformer Verlust ist ein guter
Trade, ein Gewinn aus Regelbruch ein schlechter (Teil XXIII.4). So misst das Journal Disziplin,
nicht nur Glück.

## 30.4 Shadow-Mode als Brücke zum Bot (Phase B)

Bevor der spätere Vollautomat echtes Geld bewegt, läuft er im **Shadow-Mode**: erzeugt Signale
live, führt aber keine Orders aus. Diese "Papier-Signale" werden mit denselben Metriken bewertet
wie echte Trades. Erst wenn die Shadow-Performance über genug Trades stimmt, wird scharf
geschaltet (Teil VIII / IX). Für Phase A ist das Trade-Journal des Nutzers das Äquivalent.

---

# Teil XXXI — Setup-Steckbriefe (Kurzreferenz)

Die handelbaren Setups aus Teil XVI als kompakte "Handelskarten" — eine schnelle Nachschlagliste
für den Assistenten und den Nutzer. Jeder Steckbrief: Regime · Trigger · Stop · Ziel.

**S1 — Trendfolge-Rücksetzer (Long)**
Regime: Aufwärtstrend (EMA 21>55>200, ADX>20) · Trigger: Umkehrkerze in EMA-21/55- oder
Golden-Pocket-Zone + RSI-Dreh aus <40 · Stop: unter Rücksetzer-Tief / 1,5× ATR · Ziel: letzter
Swing-High, dann Chandelier-Trailing · R:R ≥ 1:2.

**S2 — Range-Ausbruch**
Regime: Kompression (Bollinger-Squeeze / niedrige Bandbreite) · Trigger: Schluss außerhalb der
Range **mit Volumen** · Stop: zurück in die Range · Ziel: Range-Höhe projiziert · Fehlausbruch-
Filter: ohne Volumen nicht handeln.

**S3 — Divergenz-Umkehr**
Regime: Ende eines ausgedehnten, sauberen Trends · Trigger: RSI/MACD-Divergenz + Preis-
Bestätigungskerze am Level + Volumen · Stop: hinter das Extrem · Ziel: erste Gegen-Struktur.

**S4 — Supply/Demand-Zone**
Regime: passend zum HTF-Trend · Trigger: frische, unberührte Zone; Limit an proximaler Kante ·
Stop: hinter distale Kante · Ziel: gegenüberliegende Zone / POC.

**S5 — Liquidity Sweep / Wyckoff-Spring**
Regime: Range mit klarem Extrem · Trigger: Docht über/unter das Level, Schluss zurück in Range,
Volumendivergenz · Stop: knapp jenseits des Sweep-Extrems · Ziel: gegenüberliegende Liquidität.

**S6 — London-Breakout (Forex)**
Regime: ruhige Asien-Range, kein News-Tag · Trigger: Buy-/Sell-Stop an Range-Kanten zur
London-Eröffnung · Stop: gegenüberliegende Kante · Ziel: 1–2× Range-Höhe · **Veto bei
Hochimpakt-News.**

**S7 — VWAP-Rücksetzer (Trendtag)**
Regime: Trendtag · Trigger: Rücklauf an den VWAP von der Trendseite · Stop: jenseits VWAP ± 1σ ·
Ziel: Tageshoch/-tief.

**S8 — BB/KC-Squeeze-Breakout**
Regime: Bollinger komplett im Keltner (Squeeze) · Trigger: Ausbruch + Band-Expansion + Volumen ·
Stop: Squeeze-Mitte · Ziel: Trailing.

Für jeden Steckbrief gilt der Rahmen aus Teil VI: **Ohne definierten Stop und R:R ≥ 1:2 kein
Trade.**

---

# Teil XXXII — Glossar A–Z

Kompaktes Nachschlagewerk der wichtigsten Begriffe aus diesem Dokument. Damit der Nutzer Videos
und Charts versteht, ohne alles neu suchen zu müssen.

- **ADX** — Average Directional Index; misst Trendstärke (nicht Richtung). Regime-Schalter.
- **Ask / Bid** — Kaufpreis (Ask) / Verkaufspreis (Bid); Differenz = Spread.
- **ATR** — Average True Range; Volatilitätsmaß für Stops und Positionsgröße.
- **Backtest** — Test einer Strategie auf historischen Daten. Nur out-of-sample aussagekräftig.
- **BOS** — Break of Structure; Bruch eines Swing-Hochs/-Tiefs, Trendfortsetzung.
- **Breakout** — Ausbruch aus einer Range/einem Muster.
- **CHoCH** — Change of Character; erster Strukturbruch gegen den Trend, Wendewarnung.
- **Chandelier Exit** — ATR-Trailing-Stop (Höchsthoch − 3× ATR).
- **Confluence / Konfluenz** — Zusammentreffen mehrerer unabhängiger Signale am selben Ort.
- **Divergenz** — Preis und Momentum-Indikator laufen auseinander; Umkehr- oder Fortsetzungssignal.
- **Drawdown** — Rückgang vom Kapital-Höchststand; asymmetrisch zu erholen.
- **DXY** — US-Dollar-Index; übergeordneter Taktgeber für USD-Paare.
- **EMA** — Exponential Moving Average; jüngere Kerzen stärker gewichtet.
- **Engulfing** — Zwei-Kerzen-Umkehrmuster; eine Kerze umschließt die vorherige.
- **Erwartungswert (Expectancy)** — durchschnittliches Ergebnis pro Trade; die Kernmetrik.
- **FVG** — Fair Value Gap; Drei-Kerzen-Imbalance, oft "gefüllt".
- **Funding Rate** — periodische Zahlung zwischen Long/Short in Perpetual-Futures (Krypto).
- **Golden Cross / Death Cross** — 50-MA kreuzt über/unter 200-MA.
- **Golden Pocket** — Fibonacci-Zone 50–61,8 %, bevorzugte Rücksetzer-Einstiegszone.
- **Head & Shoulders** — Umkehrmuster mit drei Gipfeln; Kopf höher als die Schultern.
- **HTF / LTF** — Higher / Lower Timeframe; höherer filtert, niedrigerer triggert.
- **Ichimoku** — japanisches All-in-one-Trendsystem mit "Wolke" (Kumo).
- **Kelly-Kriterium** — mathematisch optimale Positionsgröße; praktisch nur fraktional (¼–½).
- **Killzone** — von ICT betontes Zeitfenster (deckt sich mit Sitzungs-Overlaps).
- **Liquidität / Liquidity Sweep** — Stop-Cluster; Preis läuft sie ab und dreht (Stop Hunt).
- **Lot / Pip / Point** — Positionsgröße / kleinste Kursänderung / Zehntel-Pip (Forex).
- **MACD** — Momentum-Indikator aus EMA-Differenz + Signallinie + Histogramm.
- **MAE / MFE** — Max Adverse / Favorable Excursion; schlechtester/bester Punkt im Trade.
- **Marktstruktur** — Abfolge von höheren Hochs/Tiefs (Trend) bzw. deren Bruch.
- **Martingale** — Einsatz nach Verlust erhöhen; eingebauter Totalverlust. **Verboten (V7).**
- **Mean Reversion** — Strategie auf Rückkehr zum Mittelwert; nur im Range-Regime.
- **Order Block** — letzte Gegenkerze vor Impuls (SMC); ~ frische Angebots-/Nachfragezone.
- **Overtrading** — zu viele Trades; Kosten und Fehler steigen.
- **PEAD** — Post-Earnings Announcement Drift; Kursdrift nach Gewinnüberraschung.
- **Pip-Wert** — Geldwert einer Pip-Bewegung, abhängig von der Lot-Größe.
- **Pivot Points** — vorab berechnete Intraday-Support/Widerstand-Level.
- **POC** — Point of Control; Preis mit dem höchsten gehandelten Volumen (Volume Profile).
- **Post-Only** — Limit-Order, die nur als Maker ausgeführt wird (günstigere Gebühr, Krypto).
- **Profit Factor** — Bruttogewinn / Bruttoverlust.
- **R / R-Multiple** — Risiko-Einheit (Abstand Einstieg↔Stop); Ergebnisse in R gemessen.
- **Range** — Seitwärtsphase zwischen Support und Widerstand.
- **Regime** — Marktzustand (Trend / Range / volatil); bestimmt die erlaubte Strategie.
- **RSI** — Relative Strength Index; Momentum-Oszillator 0–100.
- **R:R** — Risk-Reward-Ratio; Verhältnis Risiko zu Zielgewinn.
- **Sharpe / Sortino** — risikoadjustierte Rendite (Sortino nur Abwärtsrisiko).
- **Slippage** — Differenz zwischen erwartetem und tatsächlichem Fill-Preis.
- **SMC / ICT** — Smart Money Concepts / Inner Circle Trader; Preisaktions-Schule.
- **Spread** — Ask−Bid; sofortige Kostenlast bei jedem Ein-/Ausstieg.
- **Spring / Upthrust (UTAD)** — Wyckoff-Fehlausbruch nach unten (bullisch) / oben (bärisch).
- **Stop-Loss** — Order, die den Verlust begrenzt; muss real an der Börse liegen.
- **Support / Widerstand (S/R)** — Preiszonen mit erhöhter Kauf-/Verkaufsreaktion.
- **Swap / Rollover** — Zinsdifferenz-Kosten/-Ertrag beim Halten über Nacht (Forex).
- **Take-Profit** — Order, die den Gewinn realisiert.
- **Tick-Volumen** — Anzahl Kursänderungen; Volumen-Näherung im Forex (kein echtes Volumen).
- **Trailing Stop** — Stop, der im Gewinn mitläuft.
- **Trend** — gerichtete Abfolge höherer Hochs/Tiefs (auf) bzw. tieferer (ab).
- **VCP** — Volatility Contraction Pattern (Minervini); enger werdende Basen vor Ausbruch.
- **VWAP** — Volume Weighted Average Price; institutioneller Referenzpreis / Ordermagnet.
- **Walk-Forward** — rollierende Optimierung/Validierung; einzig valide Backtest-Methode.
- **Whipsaw** — Fehlsignal-Serie in Seitwärtsmärkten (v. a. bei MA-Crossovers).
- **Wyckoff** — Methode der Marktphasen (Akkumulation/Distribution) über Preis + Volumen.

---

# Teil XXXIII — Instrumentenprofile: der Charakter der Paare

Jedes Paar hat einen eigenen "Charakter" — typische Tagesbewegung, beste Sitzung, Haupttreiber.
Der Assistent sollte das kennen, um Signale realistisch zu bewerten. Angaben sind grobe
Größenordnungen (🔶, driften über Zeit) und dienen der Einordnung, nicht als exakte Prognose.

## 33.1 Die Majors

| Paar | Ø-Tagesrange | Beste Sitzung | Haupttreiber | Charakter |
|---|---|---|---|---|
| **EUR/USD** | ~50–90 Pips | London/NY-Overlap | Fed vs. EZB, DXY | liquidestes Paar, engste Spreads, "sauberste" Technik |
| **GBP/USD ("Cable")** | ~80–130 Pips | London | BoE, UK-Daten, Risk-Sentiment | volatiler, impulsiver, gut für Breakouts |
| **USD/JPY** | ~50–90 Pips | Tokio + NY | Fed vs. BoJ, US-Renditen, Risk-on/off | rendite- und risikogetrieben, oft trendstark |
| **USD/CHF ("Swissy")** | ~50–80 Pips | London | SNB, Safe-Haven-Flüsse | invers zu EUR/USD, ruhiger |
| **AUD/USD ("Aussie")** | ~50–80 Pips | Asien/Tokio | China, Rohstoffe, Risk-Sentiment | rohstoff-/China-gekoppelt |
| **USD/CAD ("Loonie")** | ~60–100 Pips | NY | WTI-Öl, Fed vs. BoC | stark ölgetrieben (invers zu WTI) |
| **NZD/USD ("Kiwi")** | ~50–80 Pips | Asien | Milchpreise, China, RBNZ | ähnlich AUD, dünner |

## 33.2 Cross-Paare und Gold

- **EUR/GBP:** ruhig, range-lastig, kleiner Tagesrange (~30–50 Pips); gut für Mean-Reversion,
  schlecht für Breakouts. Beste Zeit London.
- **EUR/JPY, GBP/JPY ("Beast"):** sehr volatil, große Ranges (GBP/JPY oft 100–200 Pips);
  Risk-Sentiment-Barometer; nur mit weiten Stops und kleiner Größe.
- **XAU/USD (Gold):** kein Währungspaar, aber auf MT5 handelbar; invers zum DXY, Safe-Haven,
  reagiert stark auf Realzinsen und Krisen; große Bewegungen, weite Stops nötig.

## 33.3 Die praktische Konsequenz

- **Anfänger-Fokus: EUR/USD und USD/JPY.** Engste Spreads, ruhigste Technik, meiste Liquidität.
- **GBP/JPY, GBP/USD** erst, wenn Risikomanagement sitzt — die Größe muss wegen der weiten Ranges
  kleiner sein (gleiches €-Risiko = weniger Lot).
- Der Assistent normiert Stops und Ziele **über ATR des jeweiligen Paares**, nicht über feste
  Pip-Zahlen — 30 Pips sind bei EUR/GBP viel, bei GBP/JPY wenig.

---

# Teil XXXIV — Der schriftliche Handelsplan (Vorlage)

Aus der Skills-Sammlung (Kill-Regel, Teil XXV.1) und der Psychologie (Teil XXIII): Der wichtigste
Einzelfaktor gegen undisziplinierte Verluste ist ein **vor** dem Handeln schriftlich fixierter
Plan. Diese Vorlage kann der Nutzer für sich ausfüllen; der Assistent erzeugt pro Trade die
konkreten Werte.

## 34.1 Der Dauerplan (einmal festlegen)

```
1. Ziel & Zeithorizont: Was will ich, bis wann, realistisch?
2. Kapital & Risiko: Kontogröße, Risiko pro Trade (max 1 %), Tages-Verlust-Limit (−3 %)
3. Märkte: welche Paare, welche Sitzungen (Fokus London/NY-Overlap)
4. Setups: welche der Steckbriefe S1–S8 handle ich? (lieber 2–3 gut als 8 schlecht)
5. Zeiten: wann handle ich, wann NICHT (News, dünne Sitzungen, nach Verlust-Limit)
6. Ausführung: Order-Typen, Stop immer real gesetzt, TP+SL als OCO
7. Journal: jeder Trade wird protokolliert (Schema Teil XXX.3)
8. Review: wöchentliche Auswertung (Erwartungswert, Prozess-Treue)
```

## 34.2 Der Pro-Trade-Plan (jeder einzelne Trade)

```
- Paar, Richtung, Setup-Typ, Regime
- These in EINEM Satz: warum steigt/fällt das jetzt wahrscheinlich?
- Invalidierung: was macht diese These falsch? → das ist der Stop
- Einstieg, Stop, Ziel, geplantes R:R (≥ 1:2)
- Positionsgröße aus 1 % Kontorisiko gerechnet
- Warnungen geprüft: News? Zeit? Korrelation zu offenen Trades?
```

## 34.3 Die drei Fragen vor jedem Klick

1. **Ist das ein geplantes Setup — oder springe ich einem Move hinterher?** (FOMO-Check)
2. **Kenne ich meine Invalidierung, und ist der Stop real gesetzt?** (Risiko-Check)
3. **Handle ich, um meinem Plan zu folgen — oder um einen Verlust zurückzuholen?** (Rache-Check)

Wenn eine Antwort nicht sauber ist: **nicht handeln.** Nichtstun ist die häufigste korrekte
Entscheidung (Teil XXV.2).

---

# Teil XXXV — Zusätzliche Kernerkenntnisse (Runde 2)

Ergänzt Teil XII um die verdichtete Essenz der neuen Teile XIII–XXXIV. Nummeriert weiter ab 23.

23. **Die Uhrzeit ist ein Signalfilter.** Der London/NY-Overlap trägt den Großteil der sauberen
    Bewegungen; dünne Sitzungen produzieren Rauschen. Zeit gehört in den Konfidenz-Score.
24. **Forex-Paare sind hoch korreliert.** EUR/USD und GBP/USD sind fast dasselbe Geschäft; drei
    korrelierte Longs sind eine große Position, keine drei kleinen.
25. **Kerzenmuster sind ohne Ort wertlos.** Hammer und Hanging Man sind dieselbe Kerze — nur der
    Trend und das Level machen daraus ein Signal.
26. **Engulfing und Morning/Evening Star sind die zuverlässigsten Kerzenmuster** — weil sie einen
    echten Kräftewechsel kodieren, nicht nur einen Docht.
27. **Bulkowskis ehrliche Zahl: nur ~51 % der Chartmuster erreichen ihr Ziel.** Volumen-
    bestätigung halbiert die Fehlrate. Muster sind Struktur, keine Wahrsagerei.
28. **Der Fehlausbruch ist oft das bessere Signal als der Ausbruch.** Gefangene Trader müssen
    glattstellen — das treibt die Gegenbewegung (Liquidity Sweep / Spring / UTAD, dieselbe Sache).
29. **SMC/ICT ist umbenannte Marktstruktur.** Nützliches Vokabular, keine geheime Edge. Als
    Struktur-Features übernehmen, nicht als Glaubenssystem.
30. **Wyckoff ist der beste Rahmen für Marktphasen**, weil er Preis und Volumen zusammen liest
    (Aufwand vs. Ergebnis). Spring und UTAD sind maschinell erfassbar.
31. **Fibonacci, Elliott und harmonische Muster sind im Rückblick stark, im Vorlauf schwach.**
    Nur als Konfluenz mit echten Leveln, niedrig gewichtet, nie als alleiniger Trigger.
32. **Alle erfolgreichen Systeme teilen fünf Merkmale:** Kontraktion vor Expansion, nur mit dem
    Trend, definierte Invalidierung vor Einstieg, Volumenbestätigung, Erwartungswert aus Asymmetrie.
33. **Top-Down oder Rauschen.** Wer auf dem 5m-Chart anfängt, sieht überall Signale. Der höhere
    Zeitrahmen filtert, bevor Konfidenz entsteht.
34. **Der Ausstieg entscheidet über den Erwartungswert, nicht der Einstieg.** Zu frühes
    Teilverkaufen und mechanisches Break-Even schneiden die großen Gewinner ab, die alles tragen.
35. **Der Stop wird aus der Struktur bestimmt, die Größe folgt daraus** — nie umgekehrt. Den Stop
    an eine gewünschte Größe anzupassen ist ein Kontokiller.
36. **News bewegen über Überraschung, nicht über das Niveau.** Erwartete Zahlen bewegen nichts.
    Um Hochimpakt-Ereignisse herum: nicht handeln (Spreads, Slippage, Reversals).
37. **Der wichtigste Vorteil eines Bots ist Disziplin, nicht Prognose.** Er kennt keine Angst,
    keine Rache, keine Langeweile. Deshalb sind Risikolimits im Code, nicht in der Konfiguration.
38. **Ein regelkonformer Verlust ist ein guter Trade.** Das Journal bewertet Prozesstreue, nicht
    nur P&L — sonst verstärkt ein Zufallsgewinn schlechtes Verhalten.
39. **Bei kleinem Konto ist sauberes Risiko oft unmöglich.** Wenn die Mindestordergröße das
    1 %-Limit sprengt, ist die richtige Antwort "kein Trade", nicht "Limit erhöhen".
40. **Indikatoren müssen unkorreliert sein.** Fünf Trendindikatoren sagen fünfmal dasselbe. Je
    einer aus Trend/Momentum/Volatilität/Volumen/Struktur ist mehr wert als zehn ähnliche.
41. **Jedes Paar hat einen Charakter.** 30 Pips sind bei EUR/GBP viel und bei GBP/JPY wenig —
    Stops und Ziele werden über ATR normiert, nicht über feste Pip-Zahlen.
42. **Der schriftliche Plan vor dem Klick ist der stärkste Schutz vor sich selbst.** Drei Fragen:
    geplantes Setup? Stop real gesetzt? Handle ich dem Plan oder der Rache?

Diese 20 Punkte plus die 22 aus Teil XII sind die 42-Punkte-Essenz des gesamten Dokuments — die
Kurzfassung, an der sich jede Signalbewertung des Assistenten messen lassen muss.

---

# Teil XXXVI — Einen Chart lesen: durchgerechnetes Beispiel

Damit alles Vorherige greifbar wird: eine vollständige Analyse, so wie der Assistent sie
durchläuft — von der großen Zeitebene bis zur fertigen Empfehlung. Die Zahlen sind erfunden, der
**Ablauf** ist echt und exakt der aus Teil XXI. So sieht "der Bot guckt sich den Chart an und
entscheidet" konkret aus.

## 36.1 Ausgangslage

Paar: **EUR/USD**. Aktueller Kurs: **1,0840**. Uhrzeit: **13:15 UTC** (London/NY-Overlap — gutes
Fenster, Teil XIII.2). Wirtschaftskalender: keine Hochimpakt-News in den nächsten 2 Stunden
(Teil XXIV — kein Veto).

## 36.2 Schritt 1 — Kontext (4h)

- **Trend:** EMA 21 (1,0795) > EMA 55 (1,0760) > EMA 200 (1,0710), alle steigend, Preis darüber
  → **Aufwärtstrend**. ADX(14) = 27 → **Trend bestätigt** (> 25). **Regime: Aufwärtstrend →
  erlaubte Richtung: nur Long.**
- **Struktur:** letzte Bewegung bildete ein höheres Hoch bei 1,0870 und ein höheres Tief bei
  1,0800 (intakte Aufwärts-Marktstruktur, kein CHoCH).
- **Große Level:** Widerstand bei 1,0870 (letztes Hoch), Support-Zone 1,0800–1,0810 (letztes
  Tief + runde Zahl).

## 36.3 Schritt 2 — Setup (1h / 15m)

- Der Preis ist von 1,0870 auf aktuell 1,0840 zurückgelaufen — ein **gesunder Rücksetzer im
  Aufwärtstrend** (Setup-Kandidat S1, Teil XXXI).
- **Fib des letzten Impulses** (1,0800 → 1,0870): 50 % = 1,0835, 61,8 % = 1,0827 → **Golden
  Pocket 1,0827–1,0835** (Teil XIX.2).
- **EMA 21 auf 1h** liegt bei 1,0832 — fällt fast mit dem Golden Pocket zusammen.
- **Demand-Zone** (frische Basis vor dem letzten Anstieg) bei 1,0825–1,0835.
- **Konfluenz:** Golden Pocket + EMA 21 + Demand-Zone + höheres Tief der Struktur — **vier
  unabhängige Faktoren** zeigen auf dieselbe Zone bei ~1,0830.

## 36.4 Schritt 3 — Trigger (15m / 5m)

- Der Preis läuft in die Zone 1,0830 und bildet dort eine **bullische Engulfing-Kerze** (Teil
  XIV.3) — Bestätigung am Level.
- **RSI(14)** dreht aus 38 nach oben (Teil XXVII.2) — Momentum-Bestätigung.
- **Tick-Volumen** der Engulfing-Kerze über dem 20-Kerzen-Schnitt (Teil XXVII.4).

## 36.5 Schritt 4 — Risiko und Ziel

- **Einstieg:** 1,0838 (Schluss der Bestätigungskerze; alternativ Limit an 1,0832).
- **Stop-Loss:** 1,0818 — unter die Demand-Zone und das höhere Tief (Struktur-Stop, Teil XXII.2).
  Abstand = **20 Pips**.
- **Take-Profit 1:** 1,0870 (letztes Hoch) = +32 Pips → **R:R ≈ 1:1,6**.
- **Take-Profit 2:** 1,0898 (Fib-Extension 127,2 %) = +60 Pips → **R:R ≈ 1:3**, Rest per
  Chandelier-Trailing (Teil XVI.10).
- **Mindestziel R:R ≥ 1:2** wird über TP2 erreicht → **Trade gültig**.

## 36.6 Schritt 5 — Positionsgröße

Bei Demo-Konto 1.000 €, Risiko 1 % = 10 €, Stop 20 Pips → erlaubt 0,50 €/Pip → **5 Micro-Lot
(0,05 Lot)** (Teil XXIX.2). Bei 30-€-Echtkonto wäre die Mindestgröße zu groß → **kein Echttrade,
nur Demo** (Teil XXIX.1).

## 36.7 Die fertige Ausgabe-Karte

```
EUR/USD  —  ▲ LONG   Konfidenz: 76 %   Regime: Aufwärtstrend
Einstieg:    1,0838
Stop-Loss:   1,0818   (−20 Pips / −0,18 %)
Take-Profit: 1,0870 (TP1) → 1,0898 (TP2)   R:R bis 1:3
Größe:       5 Micro-Lot (0,05 Lot) bei 1.000 € Demo, 1 % Risiko

Begründung: 4h-Aufwärtstrend (EMA-Fächer + ADX 27); Rücksetzer in
Konfluenzzone (Golden Pocket 50–61,8 % + EMA 21 + frische Demand-Zone +
höheres Tief); bullische Engulfing-Kerze am Level mit RSI-Dreh aus 38
und überdurchschnittlichem Volumen; Overlap-Zeit, keine News.

Warnungen: keine (News frei, gute Sitzung). Bei offenem GBP/USD-Long
beachten: EUR/USD und GBP/USD korrelieren ~+0,9 → gemeinsames Risiko.
```

## 36.8 Was das Beispiel zeigt

Kein einzelner Faktor löst den Trade aus — es ist das **Zusammentreffen** aus Trend, Zone,
Kerze, Momentum, Volumen und Zeit, das die Konfidenz auf 76 % hebt. Genau diese Konfluenz-Logik
(Teil VI.2) ist der Unterschied zwischen einem echten Analyse-Assistenten und einer App, die
zufällig "hoch" oder "runter" anzeigt (Teil XXV.3). Und weil jeder Schritt begründet ausgegeben
wird, **lernt der Nutzer mit jedem Signal**, statt blind zu folgen — das erklärte Ziel von Phase A.

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

**Recherche-Runde 2 (2026-07-25) — Forex, Kerzen, Strategien 🔶/🎓**

*Kerzen- und Chartmuster-Statistik*
- [The 10 Best Candle Patterns Proven With 56,680 Trades (LiberatedStockTrader)](https://www.liberatedstocktrader.com/candle-patterns-reliable-profitable/)
- [The Doji Myth: 8,029 Trades Prove It Wrong (LiberatedStockTrader)](https://www.liberatedstocktrader.com/doji-candle/)
- [Assessing the Reliability of Japanese Candlestick Patterns Across Market Regimes (Science Publishing Group) 🎓](https://www.sciencepublishinggroup.com/article/10.11648/j.im.20260101.16)
- [Candlestick Pattern Backtesting: ES and AAPL (TradesViz)](https://www.tradesviz.com/blog/candlestick-pattern-effectiveness-backtesting/)
- [Head and shoulders pattern success rate (ChartScout)](https://chartscout.io/head-and-shoulders-pattern)
- [How to Backtest Chart Patterns Using Bulkowski's Methods (QuantStrategy.io)](https://quantstrategy.io/blog/how-to-backtest-chart-patterns-using-bulkowskis-statistical/)
- [Chart Patterns Cheat Sheet 2025 (VT Markets)](https://www.vtmarkets.com/discover/chart-patterns-cheat-sheet-2025-stock-trading-patterns-guide/)

*Forex-Mechanik, Sitzungen, Korrelation*
- [Forex Trading Sessions Explained: Hours, Volatility & Best Times (Maven Trading)](https://maventrading.com/blog/forex-trading-sessions-hours-volatility-guide)
- [Best Time to Trade Forex: Session Overlaps & Peak Hours (OANDA)](https://www.oanda.com/us-en/skills-and-insights/education/trading-asset-classes/forex/when-is-the-best-time-for-forex-trading/)
- [Forex Correlation Pairs — Currency Correlation (Dukascopy)](https://www.dukascopy.com/swiss/english/marketwatch/articles/forex-correlation-pairs/)
- [Currency Pairs Correlation Table (Defcofx)](https://www.defcofx.com/currency-pairs-correlation-table/)

*Strategien, Preisaktion, SMC/Wyckoff*
- [ICT Trading Strategy: Complete Guide (LiteFinance)](https://www.litefinance.org/blog/for-beginners/trading-strategies/ict-trading-strategy/)
- [Anatomy of a Valid Order Block in Smart Money Concepts (LiquidityFinder)](https://liquidityfinder.com/news/anatomy-of-a-valid-order-block-in-smart-money-concepts-67221)
- [Supply and Demand Trading Zones Explained (TrendSpider)](https://trendspider.com/learning-center/what-are-supply-and-demand-zones/)
- [Wyckoff Accumulation Pattern: Phases, Schematics (TrendSpider)](https://trendspider.com/learning-center/chart-patterns-wyckoff-accumulation/)
- [Wyckoff Distribution Pattern Explained (BitMEX)](https://www.bitmex.com/blog/wyckoff-distribution)
- [Does the Death Cross Actually Work? 65 Years of Data (QuantifiedStrategies)](https://www.quantifiedstrategies.com/death-cross-in-trading/)
- [RSI Divergence: Bullish vs Bearish Signals (LuxAlgo)](https://www.luxalgo.com/blog/rsi-divergence-bullish-vs-bearish-signals/)
- [Divergence Trading: RSI & MACD Setup Rules (TradingSim)](https://www.tradingsim.com/blog/divergence)

*Fibonacci, Elliott, Harmonisch*
- [Guidelines for Applying Elliott Wave Theory (StockCharts ChartSchool)](https://chartschool.stockcharts.com/table-of-contents/market-analysis/elliott-wave-analysis-articles/guidelines-for-applying-elliott-wave-theory)
- [Elliott Wave Trading — Why To Be Cautious (LiberatedStockTrader)](https://www.liberatedstocktrader.com/elliott-wave-theory-principle-examples-stock-market/)
- [A Trader's Guide to Fibonacci Trading Strategies (Switch Markets)](https://www.switchmarkets.com/learn/fibonacci-trading-strategies)
- [Harmonic Patterns: Gartley, Bat, Butterfly & Crab (TradingSim)](https://www.tradingsim.com/blog/harmonic-patterns-in-stock-trading)

*News, Trade-Management, Psychologie, Volatilität*
- [Forex News Trading Guide: NFP, CPI, FOMC (PriceActionNinja)](https://priceactionninja.com/forex-news-trading-guide-nfp-cpi-fomc-major-releases/)
- [News-driven FX Trading: FOMC, CPI, NFP (FXEmpire)](https://www.fxempire.com/education/article/news-driven-fx-trading-how-to-trade-events-like-the-fomc-cpi-and-nfp-1549791)
- [Trade Management After Entry: Stop Loss, Partial Profits (ChartMini)](https://chartmini.com/blog/trade-management-what-to-do-after-you-enter-2026)
- [Dynamic reward/risk ratio and risk management (Tradeciety)](https://tradeciety.com/how-to-manage-risk-as-a-trader-become-a-professional-risk-manager)
- [How to Use ATR for Volatility-Based Stop-Losses (LuxAlgo)](https://www.luxalgo.com/blog/how-to-use-atr-for-volatility-based-stop-losses/)
- [ATR Trailing Stop Guide: Chandelier Exit (StratBase)](https://stratbase.ai/en/blog/average-true-range-trailing-stop)
- [Retail Trading Mistakes: 25 Costly Errors (TradeVerse)](https://www.tradeversejournal.com/blog/retail-trading-mistakes)
- [Common Trading Mistake: Overtrading (OANDA)](https://www.oanda.com/us-en/skills-and-insights/education/trading-psychology/common-mistakes/common-trading-mistake-overtrading/)

*Indikatoren, Ausführung, Pivots (Recherche-Runde 3)*
- [Ichimoku Cloud Trading Strategies (TrendSpider)](https://trendspider.com/learning-center/ichimoku-cloud-trading-strategies/)
- [Ichimoku Cloud know-how: Trend, signals & setups (OANDA)](https://www.oanda.com/us-en/skills-and-insights/education/technical-analysis/indicators-and-oscillators/ichimoku-cloud-trading-guide-key-strategies/)
- [BB/KC Squeeze: Trading Range Breakouts (TrendSpider)](https://trendspider.com/learning-center/bb-kc-squeeze-a-powerful-indicator-for-trading-range-breakouts/)
- [A Quantitative Study of the Bollinger Bands Squeeze (Superalgos/Medium)](https://medium.com/superalgos/a-quantitative-study-of-the-bollinger-bands-squeeze-strategy-9f47143f33fb)
- [Camarilla Pivot Points (TradingView Scripts)](https://www.tradingview.com/scripts/camarilla/)
- [Pivot Points: Formula, Types, Trading Guide (Strike.money)](https://www.strike.money/technical-analysis/pivot-points)
- [Order Types Explained: Market, Limit, Stop, Stop-Limit, Trailing, Bracket (ChartMini)](https://chartmini.com/blog/order-types-explained)
- [Types of Forex Orders: Market, Limit, Stop & More (Volity)](https://volity.io/forex/forex-orders-types/)

*Projekt-intern*
- Git-Branch `claude/trading-skills-repo-4q0qo9` — 64 dokumentierte Trading-Skills mit Playbooks
  (Stockbee Momentum Burst, PEAD, Shapiro COT-Contrarian, Minervini VCP, CANSLIM, Quant-Framework
  mit 7-Schichten-Signal-Stack). Referenzmaterial für Teil XX und XXV.
