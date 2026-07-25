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
| O7 | MT5-Broker fuer Demo? (Datenqualitaet) | offen |
| O8 | Twelve Data API-Key erstellen | offen |
| O9 | Deployment-Ziel fuer Web-App | offen |
