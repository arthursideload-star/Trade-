# Getroffene Entscheidungen

Protokoll der Projektentscheidungen mit Datum und Begründung. Neue Entscheidungen werden
unten angehängt, alte nicht gelöscht — auch revidierte bleiben mit Vermerk stehen.

---

## 2026-07-25 — Grundsatzentscheidungen

### E1: Markt und Börsen — Binance und Bybit parallel

**Entscheidung:** Krypto Spot. Binance und Bybit werden beide angebunden.

**Technische Konsequenz:** Eine Freqtrade-Instanz unterstützt genau eine Börse. "Parallel"
wird deshalb umgesetzt als:

- **Eine Handelsinstanz** (Freqtrade) auf der primären Börse
- **Ein eigener Datensammler-Dienst**, der die zweite Börse nur mitliest und als
  Referenzpreis in die eigene Datenbank schreibt

Zweck der zweiten Börse ist zunächst **Datenqualität**, nicht Arbitrage: Ein Preis, der auf
Börse A um mehrere Prozent abweicht und auf B nicht, ist ein fehlerhafter Tick und kein Signal.
Ein späterer Ausbau zu einer zweiten Handelsinstanz bleibt offen.

**Offen:** Welche Börse ist die primäre Handelsbörse? (siehe Offene Punkte)

### E2: Basis — Freqtrade

**Entscheidung:** Freqtrade als Fundament statt Eigenbau.

**Was wir dadurch geschenkt bekommen:** Backtesting-Engine, Hyperopt, Walk-Forward-Werkzeuge,
Exchange-Anbindung über ccxt, Telegram-Steuerung, Dry-Run-Modus, ausgereiftes
Order-Management. Das sind mehrere Wochen Arbeit.

**Was wir dafür in Kauf nehmen:** Freqtrades Strategie-Interface ist auf *eine* Strategie mit
einem Signal ausgelegt. Die im Plan vorgesehene Ensemble- und Regime-Architektur muss darauf
abgebildet werden. Angedachter Weg: Regime-Erkennung und Signal-Ensemble laufen als eigene
Module, die einen aggregierten Score liefern; die Freqtrade-Strategie konsumiert nur diesen
Score. Damit bleibt die Ensemble-Logik testbar und unabhängig von Freqtrade.

**Zu prüfen:** Ob Freqtrades Kostenmodell (Gebühren, Slippage) für kurze Trades ausreichend
realistisch ist oder nachgeschärft werden muss.

### E3: Strategie-Fokus — Trendfolge

**Entscheidung:** Start mit Trendfolge, in zwei Varianten (Ausbruch und Rücksetzer).

**Begründung:** Beste empirische Grundlage aller Setup-Familien — Jegadeesh & Titman (1993)
und über 30 Jahre Folgeforschung. Wenige Parameter, robust über Assetklassen, verzeiht Latenz.

Die anderen Familien (Liquidity Sweep, Mean Reversion nach Liquidationskaskaden, Basis-Trade)
bleiben im Plan, kommen aber später als zusätzliche, möglichst unkorrelierte Ertragsquellen.

### E4: Handelsstil — kurze Trades, Kapital schrittweise aufbauen

**Entscheidung:** Kurze Haltedauern. Kapital wird klein gestartet und stufenweise erhöht.

**Harte technische Anforderung, die daraus folgt:**

Bei kurzen Trades entscheidet die Ordertyp-Wahl über die Machbarkeit der Strategie, nicht nur
über die Ausführungsqualität:

| Ausführung | Roundtrip-Kosten | Nötige Bewegung für Break-Even |
|---|---|---|
| Taker (Market) | 0,20–0,40 % | > 0,40 % |
| Maker (Post-Only) | 0,04–0,15 % | > 0,15 % |

Faktor 3 bis 5. Daraus folgt verbindlich:

1. **Post-Only-Limit-Orders sind der Standard**, Market-Orders nur bei Stop-Auslösung
2. **Mindest-Edge-Schwelle:** Ein Signal wird nur gehandelt, wenn die erwartete Bewegung die
   Roundtrip-Kosten um mindestens Faktor 3 übersteigt
3. **Slippage wird pro Fill gemessen** und fließt in das Backtest-Kostenmodell zurück
4. **Nicht-Ausführung ist einzuplanen:** Post-Only-Orders werden nicht garantiert gefüllt.
   Der Backtest muss das simulieren, sonst überschätzt er systematisch

**Kapitalstufen:** Erhöhung erst, wenn die Live-Ausführungsqualität der vorherigen Stufe
gemessen und stabil ist. Slippage skaliert mit der Ordergröße — Zahlen aus einer kleinen Stufe
gelten nicht automatisch für die nächste.

---

---

## 2026-07-25 (Nachtrag) — Auswertung des Beispiel-Bots

### E5: "EasyTrading AI Assistant" wird nicht als Vorbild verwendet

Der Nutzer stellte eine Telegram-Mini-App als Beispiel vor. Auswertung der Screenshots:

| Beobachtung | Einordnung |
|---|---|
| "Auszahlung 92 %" | Binäre Optionen, kein Handel. Break-Even-Trefferquote 100/192 = **52,08 %**; bei 50 % Trefferquote liegt der Hausvorteil bei 4 % pro Wette |
| Instrumente "AUD/CAD OTC", "EUR/RUB OTC" | OTC-Paare existieren an keiner Börse. Kursfeed wird vom Anbieter selbst erzeugt |
| Zeitrahmen 1 s / 5 s / 10 s | Keine handelbare Marktinformation auf dieser Auflösung |
| Einsatzfolge 10,00 → 21,96 → 48,22 $ | **Martingale**, konstanter Faktor ~2,196 |
| Demo-Guthaben 50.172 $ | Absorbiert ~12 Verluste in Folge — die Progression wirkt dort sicher |

**Die entscheidende Rechnung:** Bei 30 € Realkapital ist bereits Schritt 2 der Progression
(10,00 $ + 21,96 $ = 31,96 $) nicht mehr finanzierbar. Zwei Fehlschläge in Folge — Wahrschein-
lichkeit ~25 % — beenden das Konto. Die Strategie, die im Demo unfehlbar aussieht, ist auf dem
Realkonto mathematisch nicht durchführbar.

**Konsequenz:** Kein Vorbild für dieses Projekt. Martingale-Progressionen sind im Risk-Layer
ausdrücklich ausgeschlossen (siehe V7 unten). Der Nutzer hat dort einen kleinen Betrag
eingezahlt und wurde zur Auszahlung und Dokumentation beraten.

### E6: Plattform — Krypto + Freqtrade, Perpetuals mit 1× Hebel

**Entscheidung** nach quantitativem Vergleich (siehe `PLATTFORM-VERGLEICH.md`).

MetaTrader 5 scheidet aus einem harten Grund aus: Die kleinstmögliche Position (0,01 Lot
EUR/USD) erfordert unter ESMA-Hebelgrenze 1:30 rund **33 € Margin** — mehr als das gesamte
Startkapital von 30 €. Dazu kommt, dass das offizielle `MetaTrader5`-Python-Paket nur unter
Windows läuft und Forex am Wochenende ruht, was dem 24/7-Ziel widerspricht.

Krypto Spot funktioniert mit 30 € (Mindestordergröße 5 USDT), ist für den gewünschten
Handelsstil aber zu teuer: 0,16 % pro Roundtrip ergeben bei 5 Trades/Tag rund 200 % Kostenlast
pro Jahr.

**Gewählt: USDT-Perpetuals mit hart auf 1× begrenztem Hebel.** Gebührenstruktur der Futures
(0,02 % Maker je Seite = 0,04 % Roundtrip, Faktor 4 günstiger als Spot), Risikoprofil einer
Spot-Position (Liquidation ~100 % entfernt). Funding fällt bei Haltedauern unter 8 Stunden
meist nicht an.

MT5 bleibt als spätere Ergänzung offen, sobald das Konto 300–500 € erreicht — Forex und Krypto
sind schwach korreliert und wären echte Diversifikation.

### E7: Zusätzliche harte Vorgaben aus dem Vergleich

| # | Vorgabe |
|---|---|
| V1 | Post-Only-Limit-Orders sind Pflicht; Market-Orders nur bei Stop-Auslösung |
| V2 | Hebel hart auf 1× begrenzt — im Code, nicht in der Börsenoberfläche |
| V3 | Maximal 3 Trades pro Tag und Symbol |
| V4 | Mindest-Zielbewegung 0,5 % (≈ 10× Roundtrip-Kosten) |
| V5 | Nicht-Ausführung von Post-Only-Orders muss im Backtest simuliert werden |
| V6 | Funding-Kosten werden mitgerechnet |
| **V7** | **Keine Martingale-, Grid- oder Averaging-Down-Logik.** Positionsgrößen werden bei Verlusten nie erhöht |

### E5b: Videoauswertung des Beispiel-Bots (Nachtrag)

Zwei Bildschirmaufnahmen (je ~17 s) wurden per Einzelbildextraktion ausgewertet. Sie bestätigen
und ergänzen die Screenshot-Analyse aus E5.

**Dokumentierter Verlauf einer laufenden Session (Video 2):**

| Trade 2 (laufend) | Einsatz | Ergebnis |
|---|---|---|
| Schritt 1 ↓ | 10,00 $ | verloren |
| Schritt 2 ↑ | 21,96 $ | verloren |
| Schritt 3 ↑ | 48,22 $ | verloren |
| **Zwischenstand** | | **−80,18 $** |

Session-Ergebnis −70,98 $; Guthaben von 50.172,60 $ auf 50.101,62 $ gefallen. Schritt 4 läge
bei rund 106 $.

**Übertragen auf 30 € Realkapital:** Nach Schritt 2 verbleiben 0,04 $. Schritt 3 ist nicht mehr
finanzierbar — das Konto wäre in dieser Session leer. Drei Verluste in Folge haben bei 50 %
Trefferquote eine Wahrscheinlichkeit von 12,5 %.

**Zwei zusätzliche Befunde aus den Videos:**

1. **Die Wettrichtung wechselt zwischen den Nachsetz-Schritten** (↓, ↑, ↑ bzw. ↑, ↓). Ein
   Signal, das bei jedem Nachsetzen die Richtung wechselt, ist keine Analyse. Die Anzeige
   "Signal: Trend ↑ HOCH" hat keine erkennbare Funktion für die Einsatzentscheidung.
2. **"Kosten: 💎 1 · Demo"** — jede Session verbraucht Credits. Der Ertrag der Anwendung
   entsteht aus Credit-Verkauf und Einzahlungen, nicht aus Handelsergebnissen.

**Begriffliche Klarstellung für dieses Projekt:** Die Anwendung kennt keine Haltedauer. Der rote
Balken ist ein Ablauf-Countdown einer binären Option, kein Kursverlauf einer offenen Position.
Der Wunsch nach "Trades wie dort, etwa 1 Minute" lässt sich deshalb nicht auf echten Handel
übertragen — es gibt dort keine Position, die gehalten wird.

### E8: Primäre Handelsbörse — Binance

**Entscheidung** (vom Nutzer delegiert): Binance als Handelsbörse, Bybit als Datenreferenz.

Begründung: höchste Perpetual-Liquidität und engste Spreads, umfangreichste kostenlose
Zusatzdaten (Funding, Open Interest, Long/Short-Ratio, Taker-Volumen) direkt über die reguläre
API, gute Dokumentation, nutzbares Testnet.

### Analyse: Kostenlast nach Haltedauer

Der Nutzer wünscht Haltedauern um eine Minute. Berechnungsgrundlage: BTC mit grob 45 %
annualisierter Volatilität, √Zeit-Skalierung, mittlere absolute Bewegung ≈ 0,8 σ.

| Haltedauer | Typische Bewegung | Roundtrip (Maker) | Kosten/Bewegung |
|---|---|---|---|
| 1 Minute | ~0,05 % | 0,04 % | **80 %** |
| 5 Minuten | ~0,11 % | 0,04 % | 36 % |
| 15 Minuten | ~0,19 % | 0,04 % | 21 % |
| 1 Stunde | ~0,38 % | 0,04 % | 11 % |
| 4 Stunden | ~0,77 % | 0,04 % | 5 % |

Zwei verschärfende Effekte bei sehr kurzen Haltedauern:

1. **Post-Only ist nicht durchhaltbar.** Limit-Orders werden nicht garantiert gefüllt; ein
   Ausstieg innerhalb einer Minute erzwingt Market-Orders. Damit verdoppeln sich die
   Roundtrip-Kosten auf 0,10 % — das Doppelte der durchschnittlichen Minutenbewegung.
2. **Adverse Selection.** Als Maker wird man bevorzugt dann gefüllt, wenn besser informierte
   Gegenparteien handeln. Auf Minutenebene ist das der dominierende Effekt.

**Empfehlung: 15 Minuten als praktische Untergrenze.** Entscheidung des Nutzers steht aus;
er stellt weiteres Material (Videos) zur Verfügung.

---

## 2026-07-25 (Nachtrag 2) — Strategiewechsel: Erst Halbautomat, dann Vollautomat

### E9: Zwei-Phasen-Ansatz — Trading-Assistent vor autonomem Bot

**Entscheidung:** Statt direkt den autonomen Bot zu bauen, wird zuerst ein
**Trading-Assistent als Web-App** entwickelt (Phase A). Der autonome Bot folgt als Phase B,
sobald die Analyse-Engine sich bewaehrt hat.

**Begruendung:**
- Der Nutzer moechte zuerst lernen und manuell handeln, bevor ein Bot allein entscheidet
- Manuelles Handeln auf MT5-Demo ist risikofrei
- Die Analyse-Engine wird in Phase B wiederverwendet — kein Doppelaufwand
- Validierung durch echte Nutzung (Trade-Journal) statt nur Backtest
- Der Nutzer ist im Urlaub und hat nur Handy + iPad, kein PC

### E10: Plattform fuer Phase A — Forex auf MetaTrader 5 Demo

**Entscheidung:** Start mit Forex auf MT5-Demo, nicht mit Krypto.

**Begruendung:**
- MT5 Demo ist kostenlos, kein Echtgeld noetig
- Forex-Daten auf MT5-Demo sind in Echtzeit (kein 15-Min-Delay — das betrifft Aktien,
  nicht Forex)
- Der Nutzer hat MT5 bereits installiert
- Majors (EUR/USD, GBP/USD etc.) haben die engsten Spreads und die zuverlaessigste
  technische Analyse

**Nicht revidiert:** E6 (Krypto + Perpetuals) gilt weiterhin fuer Phase B.

### E11: Interface — Web-App statt Bildschirm-Analyse

**Entscheidung:** Der Assistent ist eine Web-App, die Daten direkt von einer API holt.
Kein Bildschirm-Lesen (Screen Capture + OCR).

**Begruendung:** Bildschirm-Lesen ist fehleranfaellig, langsam und unnoetig, weil dieselben
Daten als exakte Zahlen per API verfuegbar sind. Eine Web-App laeuft auf iPad und Handy
gleichzeitig — der Nutzer kann auf einem Geraet handeln und auf dem anderen analysieren.

### E12: Topstep-Bewertung — vorerst nicht

**Entscheidung:** Prop-Trading-Firms (Topstep, FTMO etc.) werden vorerst nicht genutzt.

**Analyse des Topstep-Angebots ($50K Account):**
- 85 $/Monat laufende Kosten
- Profit Target 3.000 $ (6 %) bei Max Drawdown 2.000 $ (4 %)
- Consistency Rule: Kein Tag darf > 50 % des Gesamtgewinns ausmachen
- Geschaeftsmodell basiert darauf, dass 85-90 % der Teilnehmer scheitern

**Spaeter moeglich:** Wenn der Bot/Assistent nachweislich profitabel ist, koennte eine
Prop-Firm-Challenge ein sinnvoller Weg zu groesserem Kapital sein. Aber erst nach Beweis,
nicht als Experiment.

---

## Offene Punkte

| # | Frage | Status |
|---|---|---|
| O1 | Welche Boerse ist die primaere Handelsboerse — Binance oder Bybit? | ✅ Binance (E8), gilt fuer Phase B |
| O2 | Zielhaltedauer konkret | ✅ 15m+ fuer Phase B; fuer Phase A flexibel (manuell) |
| O3 | Konkrete Kapitalstufen (Erhoehungsschritte ab 30 €) | offen (Phase B) |
| O4 | VPS-Anbieter und Standort | offen (Phase B) |
| O5 | Auswertung des Beispiel-Bots | ✅ erledigt (E5) |
| O6 | Plattformentscheidung | ✅ erledigt (E6) |
| O7 | MT5-Broker fuer Demo? (Datenqualitaet) | ✅ PuPrime-Demo vorerst (E14) |
| O8 | Twelve Data API-Key erstellen | offen |
| O9 | Deployment-Ziel fuer Web-App | offen (durch E13 relativiert) |

---

## 2026-07-25 (Nachtrag 3) — Gehirn, Broker, Datenquellen

### E13: Gehirn des Assistenten — Claude (Opus) via Abo, als Claude-Code-Skills-Projekt

**Entscheidung:** Claude selbst ist das analytische Gehirn, genutzt ueber das Claude-Abo
(interaktiv), nicht ueber die kostenpflichtige API. Umsetzung als **Claude-Code-Skills-Projekt**
(Hybrid: deterministische Rechner + Claude-Orchestrierung + Live-Daten via Skills/MCP).

**Begruendung / ehrliche Abgrenzung:**
- Ein Abo deckt **interaktive** Nutzung ab (Halbautomat) ohne Extra-Kosten pro Analyse.
- Ein Abo gibt **keinen** API-Schluessel fuer einen 24/7-Vollautomaten — dafuer braeuchte es die
  Anthropic-API (Kosten pro Token, Opus teuer). Das bleibt Phase B.
- Der gewuenschte Assistent passt exakt zum Abo-Modell. Der vorhandene Branch
  `claude-trading-skills` demonstriert das Muster bereits.

Details im neuen `docs/BOT-PLAN.md`. Verfeinert Phase A aus PLAN.md (die eigenstaendige Web-App
aus E9 wird durch das Skills-Projekt ersetzt bzw. optional).

### E14: Broker — PuPrime-Demo vorerst, echtes Geld spaeter eher IC Markets

**Entscheidung:** Der vom Nutzer angelegte PuPrime-Account wird als **Demo** zum Ueben genutzt.
Fuer echtes Geld ist **IC Markets** die vorlaeufige Empfehlung.

**Begruendung:**
- Fuer eine **Demo** ist die Broker-Wahl fast egal — beide bieten kostenlose MT5-Demos mit
  EA-Unterstuetzung. PuPrime reicht zum Ueben vollstaendig.
- **PuPrime:** Hauptregulierung Seychelles (FSA, offshore), kein Tier-1; MT4/MT5 mit EA; min.
  Einzahlung 20 $ (Cent) / 50 $ (Standard); Financial-Commission-Mitglied (bis 20.000 € Deckung).
  **Aber:** dokumentierte Auszahlungsbeschwerden und Warnhinweise mehrerer Aufsichten
  (FCA, AMF, daenische FSA, SEC Philippinen). Fuer echtes Geld ein Risiko.
- **IC Markets:** Tier-1 (ASIC + CySEC), seit 2007, sauberer Ruf, beste Wahl fuer Algo/EA,
  Raw-Spread 0.0 + 7 $ Kommission. Keine Boni (Tier-1-Regulatoren verbieten sie).

### E15: Einzahlungsbonus wird NICHT als Auswahlkriterium verwendet

**Entscheidung:** Der PuPrime-Bonus (50 % / 100 % auf die erste Einzahlung, bis 1.000 $) wird
nicht als Grund fuer eine Broker-Wahl genommen und vorerst nicht aktiviert.

**Begruendung:** Der Bonus selbst ist **nicht auszahlbar** (nur die daraus erzielten Gewinne, nach
Erfuellung der Bedingungen). Einzahlungsboni sind typisch fuer Offshore-Broker und locken
Einzahlungen an; das reale Risiko sind die Auszahlungsbeschwerden, nicht der fehlende Bonus.
50 € + 50 € Bonus bei einem Broker mit Auszahlungsproblemen sind weniger wert als 50 € bei einem
Broker, bei dem man sein Geld sicher wiederbekommt. **Und ohnehin:** In Phase A wird gar kein
echtes Geld gebraucht — nur die Demo.

### E16: Datenquellen — weltweite News (Veto + Kontext) und oeffentliche Disclosures

**Entscheidung:** Der Assistent bindet zwei zusaetzliche Datenquellen an (vom Nutzer als MCPs
hinzugefuegt): weltweite **Nachrichten** und **Disclosure-/"Insider"-Daten**.

**Praezisierung (rechtlich wichtig):**
- **News:** aktiv genutzt — als **Veto** um Hochimpakt-Ereignisse und als **Kontext** fuer die
  Richtung (Geopolitik, Zentralbanken). Weltereignisse bewegen Forex stark (Teil XXIV).
- **"Insider":** Handel auf **echten** Insiderinformationen (nicht-oeffentlich) ist **illegal**.
  Genutzt werden ausschliesslich **oeffentliche Pflichtmeldungen** (US-Kongress/STOCK Act,
  SEC Form 4, 13F) — das ist legal, aber **aktienbezogen** und fuer reines Forex kaum relevant;
  wertvoll erst bei Aufnahme von Aktien/Krypto.
- **Session-Hinweis:** Autorisierungspflichtige MCP-Server verbinden sich nur in der
  interaktiven Claude-Sitzung des Nutzers, nicht in automatischen Build-Sessions.

### Offene Punkte (Ergaenzung)

| # | Frage | Status |
|---|---|---|
| O10 | Marktscope | ✅ Phase A nur Forex (E17) |
| O11 | Spaetere Autonomie | ✅ Vollautomat als Ziel, sobald Startkapital da ist (E17) |
| O12 | Konkrete Namen/Autorisierung der beiden MCP-Server (News, Disclosure) | offen |
| O13 | Broker fuer echtes Geld | vertagt (spaeter entscheiden) |

### E17: Roadmap bestaetigt (Nutzer-Antworten 2026-07-25)

**Entscheidung** aus vier Nutzer-Antworten:

1. **Marktscope Phase A:** nur **Forex** (Halbautomat). Aktien/Krypto spaeter.
2. **Architektur:** Der **Chat** (Claude-Code-Skills-Projekt) reicht fuer den Halbautomaten, bei
   dem der Nutzer die Trades selbst klickt. Ein **gehostetes Dashboard/Website** ist ein
   Nice-to-have jetzt und **Pflicht spaetestens beim Vollautomaten** (Ueberblick uebers System).
3. **Broker:** spaeter entscheiden (Demo laeuft auf PuPrime).
4. **Autonomie-Ziel:** Sobald ein gutes **Startkapital** vorhanden ist, ein **Vollautomat**, der
   moeglichst taeglich automatisch handelt. Braucht dann Anthropic-API (Claude im Loop) oder einen
   deterministischen Bot ohne Claude im Loop — Entscheidung bei Phase-B-Start.

**Konkrete Phasen daraus:**
- **Phase A (jetzt):** Forex-Halbautomat als Chat/Skills-Projekt. Du klickst die Trades.
- **Phase A.5 (optional):** kleines gehostetes Dashboard fuer den Ueberblick.
- **Phase B (mit Kapital):** Vollautomat 24/7 + Website/Dashboard. Autonomie-Technik und Kosten
  werden zu Phase-B-Start entschieden.

---

## 2026-07-26 — Spezialisierung auf Edelmetalle

### E18: Marktfokus auf Gold (XAU/USD) und Silber (XAG/USD)

**Entscheidung (Nutzer, 2026-07-26):** Der Assistent wird gezielt auf **Gold und Silber**
ausgelegt statt auf Forex allgemein. Begruendung des Nutzers: schnelle Bewegungen in beide
Richtungen, erkennbare Muster und Kerzen.

**Umsetzung:** Neues Python-Paket `metals/` mit Kontraktspezifikationen, Indikatoren,
Level-Erkennung, metallspezifischer Mustererkennung, Setup-Katalog G1–G12, Risikoregeln und
Top-Down-Orchestrierung. Wissensbasis in `docs/GOLD-SILBER.md`.

**Fachliche Einordnung, die zur Entscheidung gehoert:** Die Beobachtung des Nutzers stimmt —
Gold bewegt sich normal 60–100 USD/oz am Tag, an Nachrichtentagen 150–300, deutlich mehr als
die meisten Waehrungspaare. Dieselbe Volatilitaet macht aber jeden Groessenfehler um denselben
Faktor teurer. Deshalb wurden sechs metallspezifische Risikoregeln **zusaetzlich** zu R1–R8
fest im Code verankert (siehe E19). Ohne diese waere die Spezialisierung eine Risikoerhoehung
statt einer Chancenverbesserung.

**Was ausdruecklich nicht gilt:** "Schnell Geld machen" ist kein Projektziel und keine
realistische Erwartung. Hoehere Volatilitaet erhoeht die Streuung der Ergebnisse, nicht ihren
Erwartungswert. Der Erwartungswert kommt aus der Regeltreue.

### E19: Sechs metallspezifische Risikoregeln M1–M6 im Code

**Entscheidung:** Zusaetzlich zu R1–R8 gelten fuer Metalle:

| # | Regel | Grund |
|---|---|---|
| M1 | Stop nie enger als 1,0 × ATR(14) | Enger ist Rauschen; ein normaler Docht nimmt ihn mit |
| M2 | Stop 0,25 × ATR **jenseits** des Levels, nie darauf | Gold greift durch Levels, um Stops zu holen |
| M3 | Kein Einstieg bei Spread > 15 % des ATR | Sonst wird die Kante an den Broker gezahlt |
| M4 | Gold und Silber teilen **ein** Risikobudget von 1,5 % | Ihre Korrelation macht zwei Positionen zu einer |
| M5 | Freitag ab 19:00 UTC flat | Wochenend-Gaps ≥ 5 USD in ~35 % der Wochen; ein Stop schuetzt nicht |
| M6 | Stops nicht auf runden Zahlen | Orderfluss buendelt sich dort |

**Ort:** `metals/risk.py`, als Modulkonstanten. Nach Projektregel (CLAUDE.md) nicht aus
Konfiguration oder Umgebungsvariablen lesbar — eine Aenderung erfordert einen Commit.

### E20: Kanonische Einheit ist USD pro Feinunze, nicht "Pips"

**Entscheidung:** Im gesamten `metals/`-Paket wird nie in Pips gerechnet.

**Begruendung:** Bei Gold ist "Pip" mehrdeutig. Ein Teil der Broker und Lehrquellen nennt 0,01
einen Pip (1 USD pro Standardlot), ein anderer Teil 0,10 (10 USD pro Lot). Wer eine Formel aus
der einen Quelle mit einer Zahl aus der anderen kombiniert, sizet um den Faktor 10 falsch. Die
Umrechnung in Lots passiert genau einmal, in `metals/risk.size_position`, ueber die
Kontraktgroesse in Unzen.

### E21: Datenquellen — alle Kategorien ohne API-Schluessel abgedeckt

**Entscheidung:** 28 Quellen in sieben Kategorien angebunden (`metals/sources/registry.py`,
dokumentiert in `docs/DATENQUELLEN.md`). Jede Kategorie ist **ohne einen einzigen Schluessel**
nutzbar; Schluessel verbessern Aufloesung und Zuverlaessigkeit.

**Begruendung:** Der Assistent muss am ersten Tag funktionieren, ohne dass der Nutzer sich erst
bei fuenf Anbietern registriert. Fallback-Ketten sorgen dafuer, dass ein erschoepftes
Gratis-Kontingent den Assistenten nicht stumm schaltet.

### E22: Das News-Veto versagt geschlossen

**Entscheidung:** Ist die Nachrichtenebene nicht erreichbar, **blockiert** der Assistent, statt
anzunehmen, dass nichts passiert ist.

**Praezisierung nach einem Testfund:** GDELT allein zaehlt **nicht** als erreichbare
Nachrichtenebene. GDELT misst weltweite Berichterstattungsmenge, nicht Schlagzeilen der Quellen,
die Geldpolitik fuehren — ein Durchlauf, in dem nur GDELT antwortet, haette ein FOMC-Statement
nicht gesehen. Erforderlich ist mindestens ein kuratierter Feed (Fed, EZB, Kitco, GoldSeek,
Mining.com).

**Begruendung:** Bei Gold blind durch einen CPI-Druck zu handeln ist der dokumentierte Weg, ein
Konto in einer Kerze zu halbieren. Spreads weiten sich auf ein Vielfaches, und die erste
Spike-Richtung ist in ueber 40 % der Faelle falsch.

### E23: Kein Gold-Silber-Ratio-Pairtrade auf diesem Konto

**Entscheidung:** Die Ratio wird zur **Regime-Erkennung und Instrumentenwahl** genutzt, nicht
als Spread-Trade gehandelt.

**Begruendung:** Der klassische Trade (bei Ratio > 80 Silber long / Gold short) braucht zwei
Positionen, zwei Spreads und zwei Swaps bei einem Konvergenzhorizont von Monaten. Die
historischen Extreme hielten ueber ein Jahr an — darauf laesst sich kein 1-%-Risiko-Stop legen.
Der Code nennt diese Gruende ausdruecklich, wenn ein Extrem erreicht wird, statt den Trade
kommentarlos vorzuschlagen oder ihn zu verschweigen.

### Offene Punkte (Ergaenzung)

| # | Frage | Status |
|---|---|---|
| O14 | Kontraktgroesse XAGUSD beim eigenen Broker (5.000 oder 1.000 Unzen?) | **offen — vor dem ersten Silber-Trade in MT5 pruefen** |
| O15 | Setup-Konfidenzen sind kalibrierte Schaetzungen, keine gemessenen Trefferquoten | offen bis 30+ Trades pro Setup im Journal |
| O16 | Journal-Modul (Erfassung, MAE/MFE, Prozess-Note) | noch nicht implementiert |
| O17 | Live-Erreichbarkeit aller Endpunkte | in der Build-Session nicht pruefbar (Netzpolicy); im interaktiven Chat mit `python -m metals check` pruefen |

---

## 2026-07-26 (2) — Scalping, Ausstiege und Backtest

### E24: Scalping als eigener Modus auf M5 mit M1-Bestaetigung

**Entscheidung (Nutzer):** Der Bot soll Gold-**Scalping** koennen. Umgesetzt als eigener
Modus (`metals/scalping.py`) mit den Setups S1-S6, getrennt vom Swing-Katalog G1-G12.

**Warum M5 und nicht M1:** M1 auf Gold ist ueberwiegend Spread und Rauschen. Der Konsens der
Scalping-Quellen ist, dass M5 die brauchbare Untergrenze ist. M1 dient nur als
Einstiegsbestaetigung, nachdem ein M5-Setup scharfgeschaltet hat.

### E25: Setups sind Zustandsautomaten, keine Einzelkerzen-Pruefungen

**Entscheidung:** Jedes Scalping-Setup laeuft als Vier-Phasen-Maschine
SCANNING → ARMED → WINDOW_OPEN → ENTRY, mit einem eigenen INVALIDATED-Zustand.

**Herkunft:** Idee aus `ilahuerta-IA/backtrader-pullback-window-xauusd` (MIT). Uebernommen
wurde die Struktur, der Code ist neu geschrieben.

**Begruendung:** Eine Einzelkerzen-Pruefung kann nicht ausdruecken "ich habe darauf gewartet,
und dann hat der Markt etwas getan, das sagt, ich lag falsch". Diese Unterscheidung trennt
ein Setup von einem Muster.

### E26: Der Spread bekommt ein eigenes Veto (S6)

**Entscheidung:** Kein Scalp, wenn der Spread ueber 10 % der Stop-Distanz liegt.

**Begruendung:** Bei 3 USD/oz Stop und 0,20 Spread startet jeder Trade 6,7 % seines Risikos
im Minus, mit Slippage eher 10 %. Bei vier Trades taeglich ist das ein permanenter Abfluss.
Ein enger Stop ist beim Scalping nicht "effizient", sondern teuer.

### E27: Tagesziel nach oben stoppt genauso wie das Verlustlimit

**Entscheidung:** Bei **+2 %** am Tag ist ebenso Schluss wie bei −3 %.

**Begruendung:** Einen guten Tag zurueckzugeben ist die haeufigste Art, eine gute Woche zu
verlieren. Die meisten Systeme kennen nur das Verlustlimit; das ist die Haelfte des Problems.

Zusaetzlich: Stopp nach **2 Verlusten in Folge** (das Regime passt nicht mehr zu den Setups)
und nach **4 Trades am Tag** (ab da wird Langeweile gehandelt, nicht Setups).

### E28: Backtest auf simulierten Daten — und warum das ausdruecklich gekennzeichnet ist

**Sachlage:** Die Build-Umgebung hat keinen Netzzugang (Organisations-Policy, 403 auf alle
externen Hosts). Historische Golddaten konnten in dieser Session nicht geladen werden.

**Entscheidung:** Statt keine Auswertung zu liefern oder eine Zahl zu erfinden, wurde ein
Marktsimulator gebaut (`metals/simulate.py`), der Golds dokumentierte statistische
Eigenschaften nachbildet — Volatilitaets-Cluster, fette Raender, Session-Profil,
Liquiditaets-Sweeps. Jede daraus gewonnene Zahl ist im Code, im Report und in der
Dokumentation als **simuliert** gekennzeichnet.

**Was diese Zahlen zeigen:** ob die Mechanik stimmt und ob es **strukturelle** Fehler gibt.
**Was sie nicht zeigen:** eine Erfolgswahrscheinlichkeit auf echtem Gold. Fuer echte Zahlen:
`python -m metals backtest --source live` im interaktiven Chat.

### E29: Backtest-Konstruktionsregeln, damit die Zahlen nicht luegen

Vier Regeln, alle getestet:

1. **Kein Lookahead** — der Detektor bei Kerze i sieht nur 0..i. Regressionstest: derselbe
   Backtest ueber ein Praefix muss dieselben Trades erzeugen.
2. **Stop vor Ziel** — deckt eine Kerze beides ab, gilt der Stop als zuerst getroffen.
3. **Kosten immer** — Spread bei Ein- und Ausstieg plus Slippage; Brutto und Netto werden
   getrennt ausgewiesen.
4. **Konfidenzintervall auf den Erwartungswert** — schliesst es die Null ein, ist keine Kante
   nachgewiesen, unabhaengig vom Punktschaetzer.

### E30: Zwei durch den Backtest gefundene Fehler

**Fund 1 — Trailing auf der Fuellkerze (Bug, behoben).** Der Trailing-Stop zog schon auf
derselben Kerze nach, auf der das erste Ziel gefuellt wurde, berechnet aus deren Hoch. Der
Runner-Stop landete rund 0,4R ueber dem Einstieg und wurde beim naechsten Ruecksetzer
mitgenommen. **Jeder Runner wurde zu einem Kleingewinn.** Behoben, Regressionstest vorhanden.

**Fund 2 — Die Teilgewinn-Falle (Strategie, nicht Code).** 60 % bei 1R schliessen und den
Rest per Break-even-Stop absichern ergibt im Gewinnfall +0,60R gegen −1,00R im Verlustfall.
Erforderliche Trefferquote fuer Break-even: **62,5 %**, vor Kosten. Das ist Arithmetik, kein
Marktphaenomen — es gilt auf jedem Markt und auf echten Daten genauso. Deshalb wurde ein
Vergleich mehrerer Ausstiegsstrukturen aufgesetzt (`metals/evaluate.experiment_grid`).

### E31: `/trade` als Slash-Command

**Entscheidung (Nutzer):** `.claude/commands/trade.md` — bei `/trade` beginnt Claude die
Gold-Analyse und begleitet die Sitzung: Richtung (hoch/runter/abwarten), Einstieg, Stop,
zwei Ziele, Groesse, und ausdruecklich **wann aufgehoert wird**.

Die harten Grenzen sind im Command verankert: kein Einstieg ohne Stop, keine Zahlen fuer
einen regelwidrigen Trade, und wenn `metals stop` AUFHOEREN sagt, wird die Sperre erklaert,
nicht wegdiskutiert.

### Offene Punkte (Ergaenzung)

| # | Frage | Status |
|---|---|---|
| O18 | Backtest auf echten historischen M5-Daten | **offen — im interaktiven Chat mit `--source live`** |
| O19 | Setup-Konfidenzen auf echten Daten kalibrieren | offen |
| O20 | Ausstiegsstruktur final festlegen, nachdem echte Daten vorliegen | offen |

---

## 2026-07-26 (3) — MetaTrader-Anbindung und echte Historie

### E32: Expert Advisor fuer MT5, startet im Advisor-Modus

**Entscheidung (Nutzer):** Der Bot soll direkt in MetaTrader nutzbar sein. Umgesetzt als
`mt5/Experts/GoldScalpAssistant.mq5` mit den Setups S2, S4, S5 und denselben harten
Risikoregeln wie das Python-Paket.

**Standardmodus ist ADVISOR, nicht AUTO.** Der EA zeichnet, rechnet und meldet, platziert
aber keine Order. Begruendung: Die Strategie hat keinen nachgewiesenen positiven
Erwartungswert (E28-E30). Ein EA, der beim ersten Start selbstaendig handelt, setzt eine
Behauptung um, die noch nicht belegt ist. Der Advisor-Modus erlaubt es, die Einschaetzung
des Systems gegen die eigene zu halten, bevor es etwas ausgeben darf.

### E33: Positionsgroesse in MT5 ueber den Tickwert des Brokers

**Entscheidung:** Der EA rechnet die Losgroesse ueber `SYMBOL_TRADE_TICK_VALUE` und
`SYMBOL_TRADE_TICK_SIZE`, nicht ueber eine angenommene Kontraktgroesse.

**Begruendung:** Das Python-Paket muss 100 Unzen pro Lot annehmen und ausdruecklich davor
warnen (offener Punkt O14). Das Terminal kennt den echten Wert. An dieser einen Stelle ist
die MT5-Version strikt besser als die Python-Version, und die Silber-Kontraktgroessenfrage
loest sich dort von selbst.

### E34: Drei Broker-Randbedingungen, die es im Backtest nicht gibt

Aus der Analyse des freien MQL5-Produkts "Gold Scalper for MT5" (Nachfolger des
Goldfinch-EA) uebernommen — dessen dokumentierte Risiken betreffen diesen Code direkt:

1. **Mindest-Stop-Abstand** (`SYMBOL_TRADE_STOPS_LEVEL`). Bei Gold oft 10-50 Punkte. Ein
   Scalping-Stop darunter wird vom Server abgelehnt. Der EA weitet den Stop und
   protokolliert es.
2. **Teilgewinn kann unmoeglich sein.** Faellt eine Seite der 60/40-Teilung unter die
   Mindest-Lotgroesse, geht kein Teilverkauf. Der EA schliesst dann vollstaendig und nennt
   den Grund — besser ein kleiner Gewinn als eine abgelehnte Order, waehrend der Preis
   weglaeuft.
3. **Phantom-Trades bei duenner Tick-Dichte.** Im Strategietester erzeugt jede Modellierung
   ausser "Jeder Tick basierend auf realen Ticks" bei Scalping Trades, die live nicht
   zustande kaemen. Steht als Warnung in `mt5/README.md`.

**Fachliche Bestaetigung nebenbei:** Goldfinch handelt Volatilitaets-Expansion — die
Traegheit nach einer ploetzlichen Preisbeschleunigung. Das ist dieselbe Idee wie Setup S5,
unabhaengig entstanden. Und: Der EA hat Pflicht-Stop, kein Martingale, kein Grid — dieselben
Grundsaetze wie R6/R7 hier.

### E35: Historische Daten kommen aus einer Datei, nicht aus einer API

**Sachlage** (aus der Nutzer-Recherche, PDF vom 2026-07-26): Praktisch jede kostenlose
Live-API begrenzt Intraday-Historie auf 30-60 Tage. yfinance 60 Tage, TraderMade kostenlos
2 Tage, Alpha Vantage hat fuer Spot-Gold gar keinen Intraday-Endpunkt, Finnhub hat den
Forex-Candle-Endpunkt weitgehend hinter Bezahlplaene verschoben.

**Entscheidung:** Neues Modul `metals/sources/history.py` laedt heruntergeladene Dateien.
Unterstuetzt die Formate, in denen diese Downloads tatsaechlich ankommen: Dukascopy (UTC),
Kaggle/MetaTrader (Brokerzeit), HistData (US Eastern ohne Sommerzeit), generisch.

**Empfohlene Quellen:** Dukascopy (`dukascopy-python`, MIT, nachvollziehbare Herkunft, UTC,
keine Tiefenbegrenzung) oder der Kaggle-Datensatz `novandraanugrah/xauusd-gold-price-
historical-data` (CC0, fertige CSV, aber Community-Upload und Brokerzeit).

### E36: Die Zeitzone hat bewusst keinen Standardwert

**Entscheidung:** `history.load()` verlangt die Quell-Zeitzone als Pflichtargument. Kein
Default, kein Raten.

**Begruendung:** Die Quellen widersprechen sich (UTC / US Eastern ohne DST / Brokerzeit
undokumentiert), und eine falsch verschobene Reihe zerstoert jede Session-Regel **lautlos**.
Die London-Open-Setups wuerden mitten in der Asien-Session feuern, und an den Backtest-Zahlen
sieht man nichts. Ein falscher Standardwert ist schlimmer als ein Fehler.

**Zusaetzliche Absicherung:** Der Lader rechnet nach, ob die volatilsten Stunden dort liegen,
wo sie bei Gold liegen muessen (12:00-17:00 UTC, London/NY-Overlap), und warnt, wenn nicht.
Dazu Pruefung auf Duplikate, unmoegliche OHLC-Zeilen, Wochenend-Bars, Luecken und Spruenge
ueber 5 % — die Fehler, die diese Community-Datensaetze tatsaechlich haben.

### Offene Punkte (Ergaenzung)

| # | Frage | Status |
|---|---|---|
| O14 | Kontraktgroesse XAGUSD | **im MT5-EA geloest** (Tickwert des Brokers); im Python-Paket weiterhin offen |
| O18 | Backtest auf echten historischen M5-Daten | **Werkzeug fertig** — Datei herunterladen und `--source file` |
| O21 | EA auf echten Broker-Ticks im Strategietester pruefen | offen |
| O22 | Advisor- gegen Auto-Modus vergleichen (stimmen die Signale mit der Chat-Analyse ueberein?) | offen |
