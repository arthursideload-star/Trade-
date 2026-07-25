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

## Offene Punkte

| # | Frage | Status |
|---|---|---|
| O1 | Welche Börse ist die primäre Handelsbörse — Binance oder Bybit? | offen |
| O2 | Zielhaltedauer konkret — Minuten oder Stunden? Bestimmt Zeitrahmen und Datenauflösung | offen |
| O3 | Konkrete Kapitalstufen (Erhöhungsschritte ab 30 €) | offen |
| O4 | VPS-Anbieter und Standort (Börsennähe) | zugesagt, sobald Ergebnisse stimmen |
| O5 | Auswertung des Beispiel-Bots | ✅ erledigt (E5) |
| O6 | Plattformentscheidung | ✅ erledigt (E6) |
