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

## Offene Punkte

| # | Frage | Status |
|---|---|---|
| O1 | Welche Börse ist die primäre Handelsbörse — Binance oder Bybit? | offen |
| O2 | Zielhaltedauer bei "kurzen Trades" — Minuten, Stunden oder Intraday? Bestimmt Zeitrahmen, Datenauflösung und Infrastrukturanforderungen | offen |
| O3 | Konkrete Kapitalstufen (Start und Erhöhungsschritte) | offen |
| O4 | Läuft der Bot auf einem eigenen VPS? Falls ja, welcher Standort (Börsennähe)? | offen |
| O5 | Beispiel-Bot des Nutzers — wird noch bereitgestellt und ausgewertet | wartend |
