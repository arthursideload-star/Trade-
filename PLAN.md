# Entwicklungsplan: Autonomer 24/7 Trading-Bot

Status: Architektur & Roadmap
Letzte Aktualisierung: 2026-07-25

---

## 1. Designziele

Das System soll drei Dinge können, und der gesamte Aufbau richtet sich danach:

| Ziel | Bedeutung im Code |
|---|---|
| **24/7 autonom** | Kein manueller Eingriff im Normalbetrieb. Selbstheilung bei Verbindungsabbrüchen, Neustart mit vollständiger Zustandswiederherstellung, Deployment ohne Handelsunterbrechung. |
| **Präzise Analyse** | Mehrere Zeitebenen, mehrere Signalquellen, Regime-Erkennung, Konfidenz-Bewertung statt binärer Kauf/Verkauf-Entscheidungen. |
| **Präzise Ausführung** | Der beste Analysewert ist wertlos, wenn die Order 0,3 % schlechter gefüllt wird als gedacht. Ausführungsqualität wird gemessen und optimiert. |

**Präzision ist eine technische Eigenschaft, keine Vorhersagegenauigkeit.** Kein System kennt
den nächsten Kurs. Was ein gut gebautes System kann: aus vielen schwachen Signalen einen
belastbaren Erwartungswert formen, diesen exakt in Positionsgrößen übersetzen, verlustarm
ausführen und sich anpassen, wenn sich der Markt ändert. Darauf zielt jeder Baustein hier.

---

## 2. Systemarchitektur

Der Bot besteht aus entkoppelten Diensten, die über einen internen Event-Bus kommunizieren.
Das ist der Schlüssel für 24/7-Betrieb: Ein abstürzender Analyse-Dienst darf nie eine offene
Position verwaisen lassen.

```
┌──────────────────────────────────────────────────────────────────────┐
│                          MARKET DATA LAYER                            │
│  WebSocket-Feeds (Trades, Orderbuch, Kerzen) · REST-Fallback ·        │
│  Normalisierung · Lückenerkennung · Persistenz (TimescaleDB)          │
└────────────────────────────────┬─────────────────────────────────────┘
                                 │ NormalizedTick / Bar
┌────────────────────────────────▼─────────────────────────────────────┐
│                          FEATURE ENGINE                               │
│  Inkrementelle Indikatorberechnung über mehrere Zeitebenen            │
│  (1m · 5m · 15m · 1h · 4h · 1d) → Feature-Vektor mit Zeitstempel      │
└────────────────────────────────┬─────────────────────────────────────┘
                                 │ FeatureSnapshot
┌────────────────────────────────▼─────────────────────────────────────┐
│                          ANALYSIS ENGINE                              │
│  ┌────────────┐  ┌────────────┐  ┌──────────┐  ┌─────────────────┐   │
│  │  Regime-   │  │  Signal-   │  │ Signal-  │  │  Meta-Modell    │   │
│  │  Detektor  │→ │  Modelle   │→ │ Ensemble │→ │  (Konfidenz)    │   │
│  └────────────┘  └────────────┘  └──────────┘  └─────────────────┘   │
└────────────────────────────────┬─────────────────────────────────────┘
                                 │ Signal(direction, edge, confidence)
┌────────────────────────────────▼─────────────────────────────────────┐
│                        PORTFOLIO & RISK ENGINE                        │
│  Positionsgröße (Vol-Targeting) · Korrelationsmatrix ·                │
│  Exposure-Limits · Kapitalschutz-Layer (Vetorecht)                    │
└────────────────────────────────┬─────────────────────────────────────┘
                                 │ TargetPosition
┌────────────────────────────────▼─────────────────────────────────────┐
│                          EXECUTION ENGINE                             │
│  Order-Typ-Wahl · Slicing (TWAP/Iceberg) · Retry & Idempotenz ·       │
│  Fill-Tracking · Slippage-Messung · Reconciliation                    │
└────────────────────────────────┬─────────────────────────────────────┘
                                 │
┌────────────────────────────────▼─────────────────────────────────────┐
│                    EXCHANGE ADAPTER (ccxt / native)                   │
│         Backtest · Paper (Testnet) · Live — identische Schnittstelle  │
└──────────────────────────────────────────────────────────────────────┘

Querschnitt: State Store · Watchdog · Metrics/Alerting · Config-Service
```

**Zentrale Regel:** Backtest, Paper und Live unterscheiden sich ausschließlich im
Exchange-Adapter. Alles darüber ist derselbe Code. Nur so sagen Testergebnisse etwas über
den Live-Betrieb aus.

---

## 3. Datenschicht — die Grundlage jeder Präzision

Schlechte Daten erzeugen präzise falsche Signale. Deshalb ist das der erste Baustein.

**Quellen (Krypto Spot als Referenz):**
- WebSocket: Trades, Orderbuch-Deltas (L2), Kerzen — primär, niedrige Latenz
- REST: Lückenfüllung, historische Daten, Kontostand
- Zusatzdaten: Funding Rates, Open Interest, Long/Short-Ratio — auch für Spot-Signale wertvoll
- Zweite Börse als Referenzpreis (erkennt fehlerhafte Ticks der Hauptbörse)

**Qualitätssicherung — läuft permanent mit:**
- Lückenerkennung: Fehlt eine Kerze, wird sie per REST nachgeladen, bevor Signale rechnen
- Ausreißerfilter: Ticks, die > X Standardabweichungen vom Referenzpreis abweichen, werden verworfen
- Uhrzeit-Drift: NTP-Sync, Abgleich mit Börsen-Serverzeit; alles intern in UTC
- Staleness-Wächter: Kommen 30 Sekunden keine Daten, gilt der Feed als tot → Reconnect → bei Fehlschlag kein Handel
- Sequenznummern im Orderbuch prüfen; bei Lücke Snapshot neu anfordern

**Speicherung:** TimescaleDB (PostgreSQL-Erweiterung für Zeitreihen). Rohdaten unverändert
aufbewahren, Features daraus neu berechenbar. So kannst du später Signale auf echten
historischen Daten testen, statt nur auf Börsen-Kerzen.

---

## 4. Analyse-Engine — das Herzstück

Kein einzelner Indikator hat eine belastbare Edge. Präzision entsteht durch **Kombination
schwacher Signale unter Berücksichtigung des Marktregimes.**

### 4.1 Feature-Ebene (mehrere Zeitebenen parallel)

Alle Indikatoren werden **inkrementell** berechnet (Online-Update pro neuer Kerze), nicht per
Neuberechnung über das gesamte Fenster — das ist der Unterschied zwischen Millisekunden und
Sekunden pro Tick.

| Kategorie | Features |
|---|---|
| **Trend** | EMA-Fächer (8/21/55/200), ADX, Donchian-Position, lineare Regressionssteigung, Hurst-Exponent |
| **Momentum** | RSI, MACD-Histogramm, Rate of Change, Stochastik über mehrere Perioden |
| **Volatilität** | ATR, realisierte Volatilität, Bollinger-Bandbreite, Parkinson/Garman-Klass-Schätzer |
| **Volumen** | OBV, Volume Profile / POC, VWAP-Abweichung, Volumen-Impuls |
| **Mikrostruktur** | Orderbuch-Imbalance, Bid-Ask-Spread, Tiefe auf N Ebenen, Trade-Flow-Imbalance (aggressive Käufer vs. Verkäufer) |
| **Marktweit** | Funding Rate, Open-Interest-Änderung, Korrelation zu BTC, Marktbreite |
| **Zeitlich** | Tageszeit, Wochentag, Session (Asien/Europa/US) — Volatilität ist stark tageszeitabhängig |

**Mehrere Zeitebenen gleichzeitig:** Der 4h-Trend bestimmt die erlaubte Handelsrichtung, das
15m-Signal den Einstiegszeitpunkt, das 1m-Orderbuch die Ausführung. Ein Kaufsignal gegen den
übergeordneten Trend wird abgeschwächt oder verworfen.

### 4.2 Regime-Erkennung

Derselbe Indikator funktioniert in einem Trendmarkt und schadet in einem Seitwärtsmarkt.
Deshalb wird zuerst der Marktzustand klassifiziert:

- **Klassifikation:** Trend (auf/ab) · Seitwärts · Hochvolatile Expansion · Kompression
- **Methoden:** ADX + Volatilitäts-Perzentil als robuste Basis; optional Hidden-Markov-Modell
  oder Gaussian-Mixture-Clustering auf Volatilitäts-/Return-Features
- **Wirkung:** Jedes Signalmodell bekommt pro Regime ein eigenes Gewicht. Mean-Reversion-Signale
  werden im Trendregime heruntergewichtet, Breakout-Signale im Seitwärtsregime.

### 4.3 Signalmodelle

Mehrere unabhängige Modelle, jedes liefert einen Wert in `[-1, +1]`:

1. **Trendfolge** — Donchian-Breakout + EMA-Ausrichtung, ATR-normiert
2. **Mean Reversion** — Abweichung vom VWAP/Bollinger in Kompressionsregimen
3. **Momentum-Persistenz** — Cross-Sectional: die stärksten N von M Assets kaufen
4. **Mikrostruktur** — Orderbuch- und Trade-Flow-Imbalance für kurzfristige Richtung
5. **Volatilitäts-Breakout** — Positionsaufbau bei Ausbruch aus Kompression

### 4.4 Ensemble & Konfidenz

Die Modellausgaben werden **nicht** einfach gemittelt:

- **Gewichtung nach Regime** (siehe 4.2) und nach rollierender Trefferleistung der letzten
  N Trades pro Modell — Modelle, die aktuell funktionieren, bekommen mehr Gewicht
- **Meta-Labeling** (Ansatz nach López de Prado): Ein zweites Modell (Gradient Boosting)
  bewertet nicht *ob* gekauft wird, sondern *wie wahrscheinlich das primäre Signal richtig
  liegt*. Ausgabe ist ein Konfidenzwert.
- **Triple-Barrier-Labeling** für das Training: Ein Trade gilt als erfolgreich, wenn er das
  Gewinnziel vor dem Stop und vor Ablauf des Zeitfensters erreicht — realistischer als
  "Preis nach X Kerzen".
- **Schwellenwert:** Nur bei Konfidenz über einem Mindestwert wird gehandelt. Kein Signal ist
  eine gültige und häufige Entscheidung — Nichthandeln kostet nichts außer Gelegenheit.

**Ausgabe der Analyse-Engine:** `Signal(direction, expected_edge, confidence, regime, horizon)`
— nicht nur "kaufen", sondern *wie stark, wie sicher, für wie lange*. Genau das braucht die
nächste Schicht.

---

## 5. Portfolio- & Risk-Engine

Übersetzt Signale in konkrete Zielpositionen. Hier entsteht ein großer Teil der tatsächlichen
Performance — Positionsgrößen wirken stärker als Einstiegszeitpunkte.

**Positionsgröße:**
- **Volatilitäts-Targeting** als Basis: Jede Position wird so dimensioniert, dass sie den
  gleichen Risikobeitrag liefert (Größe ∝ 1/ATR). Ein ruhiges Asset bekommt mehr Kapital
  als ein wildes.
- **Skalierung mit Konfidenz:** `Größe = Basisrisiko × Konfidenz`. Starke Signale bekommen
  mehr Kapital, schwache weniger.
- **Fraktionales Kelly** (max. ¼ Kelly) als Obergrenze — volles Kelly ist mathematisch
  optimal, aber praktisch zu schwankungsanfällig.

**Portfolio-Ebene:**
- Korrelationsmatrix über alle offenen Positionen; korrelierte Positionen zählen zusammen
  auf das Risikobudget (5 Altcoins sind eine Position, nicht fünf)
- Gesamt-Exposure-Limit und Limit pro Asset
- Rebalancing statt Vollausstieg: Signaländerungen passen die Zielgröße an, statt zu schließen
  und neu zu kaufen — spart Gebühren

**Kapitalschutz-Layer (Vetorecht über allem):**

| Regel | Startwert |
|---|---|
| Risiko pro Position | 1 % des Kontos |
| Gesamtrisiko offen | max. 5 % |
| Täglicher Verlust-Stopp | −3 % → Handelspause bis zum nächsten Tag |
| Gesamt-Drawdown-Stopp | −15 % → Stopp, manuelle Freigabe |
| Order-Rate-Limit | max. N Orders/Stunde (fängt Schleifen-Bugs) |
| Sanity-Check pro Order | Größe, Preis und Wert in plausibler Spanne |

Diese Werte stehen als harte Grenzen im Code, nicht in der Strategie-Konfiguration. Sie sind
kein Misstrauen gegen die Strategie, sondern gegen Bugs und Börsenausfälle — beides gab es
schon bei jedem System, das lange genug lief.

---

## 6. Execution Engine — Präzision am Punkt des Geldes

Bei 500 Trades im Jahr entscheiden 0,1 % Ausführungsqualität pro Trade über 50 % Jahresertrag.

- **Order-Typ nach Dringlichkeit:** Post-Only-Limit für geduldige Einstiege (Maker-Gebühr,
  oft negativ = Rabatt), Market nur bei Stop-Auslösung
- **Slicing:** Große Orders werden in Teilorders zerlegt (TWAP oder volumenabhängig), damit sie
  das Orderbuch nicht selbst bewegen
- **Adaptives Limit:** Limitpreis wird nach X Sekunden ohne Fill schrittweise nachgezogen —
  balanciert Gebührenvorteil gegen Nichtausführungsrisiko
- **Idempotenz:** Jede Order bekommt eine deterministische Client Order ID. Ein Retry nach
  Timeout kann so niemals eine Doppelorder erzeugen — der häufigste teure Bug in Trading-Bots.
- **Reconciliation:** Alle N Sekunden Abgleich zwischen erwarteter und tatsächlicher Position
  an der Börse. Bei Abweichung: Alarm und Handelspause, bis geklärt.
- **Slippage-Messung:** Für jeden Fill wird die Differenz zum erwarteten Preis geloggt. Diese
  Werte fließen zurück ins Backtest-Kostenmodell — der Backtest wird dadurch mit der Zeit
  immer realistischer.

---

## 7. 24/7-Infrastruktur

Der Teil, der aus einem Skript ein System macht.

**Betrieb:**
- Deployment als Docker-Compose-Stack auf einem VPS (Hetzner/Contabo, ~5–15 €/Monat) in
  Börsennähe (Frankfurt oder Tokio, je nach Börse)
- Systemd/Docker mit `restart: always`, Healthcheck-Endpunkten pro Dienst
- Konfiguration über Umgebungsvariablen und Config-Datei, Secrets nie im Repo

**Ausfallsicherheit:**
- **Watchdog-Prozess:** Überwacht Heartbeats aller Dienste. Bleibt ein Heartbeat aus →
  Neustart des Dienstes → bei wiederholtem Fehlschlag: Positionen sichern und alarmieren.
- **Auto-Reconnect** mit exponentiellem Backoff für alle WebSockets; REST-Fallback aktiviert
  sich automatisch, solange der Stream tot ist
- **Zustandswiederherstellung beim Start:** Der Bot liest zuerst den echten Kontostand und
  alle offenen Orders von der Börse und gleicht sie mit dem lokalen State ab. Bei Konflikt
  gewinnt die Börse. Erst danach beginnt der Handel.
- **Fail-safe statt fail-open:** Wenn der Zustand nicht sicher bekannt ist, wird nicht
  gehandelt — es wird alarmiert und gewartet.
- **Rate-Limit-Verwaltung:** Zentrale Token-Bucket-Kontrolle über alle API-Aufrufe; ein
  Banning der IP durch die Börse ist ein vermeidbarer Ausfall.
- **Backup:** Datenbank-Snapshot täglich, verschlüsselt off-site

**Sicherheit:**
- API-Key ausschließlich mit Handelsrecht — **Auszahlungen deaktiviert**, IP-Whitelist auf
  den VPS. Selbst bei komplett kompromittiertem Server kann so kein Guthaben abfließen.
- Getrenntes Börsen-Unterkonto nur für den Bot
- Secrets über eine `.env`-Datei außerhalb des Repos oder einen Secret-Manager

**Updates ohne Handelsunterbrechung:** Neue Version startet parallel, übernimmt nach
Zustandsübergabe, alte Version fährt geordnet herunter. Ein Deployment darf niemals eine
offene Position ohne Stop-Loss zurücklassen.

---

## 8. Monitoring & Selbstheilung

Autonomie heißt nicht "blind laufen lassen", sondern: das System meldet sich, wenn es zählt.

- **Metriken** (Prometheus + Grafana): Equity-Kurve live, offene Positionen, Latenz pro
  Pipeline-Stufe, Feed-Gesundheit, Slippage pro Trade, Signalverteilung, API-Fehlerraten
- **Alerts** (Telegram-Bot): sofort bei Kapitalschutz-Auslösung, Feed-Ausfall, Order-Fehlern,
  Reconciliation-Abweichung; täglicher Ergebnisbericht um 00:00 UTC
- **Fernsteuerung** über denselben Telegram-Bot: Status abfragen, Positionen ansehen,
  pausieren, Kill-Switch auslösen — vom Handy aus
- **Selbstheilung:** Feed-Reconnect, Dienst-Neustart, automatische Nachladung fehlender Daten,
  Wiederaufnahme nach Börsen-Wartungsfenster — alles ohne dich

---

## 9. Validierung & kontinuierliche Verbesserung

Damit "präzise" messbar bleibt und nicht Meinung ist.

**Backtest-Engine (event-getrieben, nicht vektorisiert):**
- Ausführung frühestens auf der nächsten Kerze — verhindert Handel mit Zukunftswissen
- Kostenmodell mit echten Maker/Taker-Gebühren, Spread und gemessener Slippage aus dem Livebetrieb
- Kennzahlen: CAGR, Max Drawdown, Sharpe, Sortino, Calmar, Profit Factor, Trefferquote,
  Turnover — immer gegen Buy & Hold als Referenz
- Selbsttest der Engine: Eine Zufallsstrategie muss exakt die Gebühren als Verlust zeigen.
  Zeigt sie Gewinn, hat die Engine einen Bug — dieser Test läuft in der CI mit.

**Walk-Forward statt Einmal-Optimierung:** Parameter auf Fenster A bestimmen, auf dem
folgenden Fenster B messen, Fenster vorschieben. Nur die Out-of-Sample-Ergebnisse zählen.
Zusätzlich Parametersensitivität prüfen: Bricht das Ergebnis bei ±20 % Parameteränderung
zusammen, ist die Konfiguration an die Vergangenheit angepasst und im Livebetrieb wertlos.

**Shadow-Mode:** Neue Modelle laufen zuerst live mit — sie erzeugen Signale und werden
bewertet, führen aber keine Orders aus. Erst wenn die Shadow-Performance stimmt, werden sie
scharf geschaltet. So testest du auf echten Marktdaten ohne Kapitalrisiko.

**Modell-Drift-Erkennung:** Laufender Vergleich der Live-Signalqualität mit der erwarteten.
Fällt die rollierende Trefferleistung unter einen Schwellenwert, wird das Modell automatisch
heruntergewichtet und du bekommst einen Alert. Regelmäßiges Neutrainieren auf dem jeweils
aktuellen Datenfenster.

---

## 10. Umsetzungs-Roadmap

Aufeinander aufbauende Sprints. Jeder Sprint hinterlässt etwas Lauffähiges.

| Sprint | Dauer | Inhalt | Ergebnis |
|---|---|---|---|
| **S1** | 1 Wo | Repo, Docker, CI, Config, Logging, TimescaleDB | Gerüst steht |
| **S2** | 1–2 Wo | Data Layer: WebSocket + REST, Normalisierung, Qualitätschecks, Persistenz | Live-Daten fließen und werden gespeichert |
| **S3** | 1 Wo | Feature Engine: inkrementelle Indikatoren, Multi-Timeframe | Feature-Vektoren in Echtzeit |
| **S4** | 2 Wo | Backtest-Engine mit Kostenmodell + Selbsttest | Strategien messbar |
| **S5** | 2 Wo | Signalmodelle + Regime-Detektor + Ensemble | Analyse-Engine liefert Signale mit Konfidenz |
| **S6** | 1 Wo | Portfolio- & Risk-Engine, Kapitalschutz-Layer | Signale werden zu Zielpositionen |
| **S7** | 1–2 Wo | Execution Engine: Idempotenz, Slicing, Reconciliation | Orders werden präzise ausgeführt |
| **S8** | 1 Wo | 24/7-Infrastruktur: Watchdog, Recovery, Alerting, Telegram-Steuerung | System läuft unbeaufsichtigt |
| **S9** | 4+ Wo | Paper-Trading auf Testnet, parallel Shadow-Mode | Live-Verhalten verifiziert |
| **S10** | fortlaufend | Live-Start, schrittweise Kapitalerhöhung, Meta-Modell, weitere Strategien | Produktivbetrieb |

**Bauzeit bis zum unbeaufsichtigten Dauerbetrieb: ca. 10–12 Wochen** aktive Entwicklung,
danach die Paper-Phase parallel zur Weiterentwicklung.

**Sinnvolle Reihenfolge beim Kapitaleinsatz:** klein starten und in Stufen erhöhen, sobald das
Live-Verhalten dem Shadow-/Paper-Verhalten entspricht. Nicht aus Vorsicht, sondern weil
Ausführungsqualität und Slippage sich mit der Ordergröße ändern — die Zahlen aus 200 € gelten
nicht automatisch für 20.000 €.

---

## 11. Tech-Stack

| Bereich | Wahl | Begründung |
|---|---|---|
| Sprache | **Python 3.12** (`asyncio`) | Bestes Ökosystem für Datenanalyse und Börsen-APIs; asyncio passt zu vielen parallelen Streams |
| Performance-Kern | **Rust/Cython** bei Bedarf | Nur falls Indikatorberechnung zum Flaschenhals wird — erst messen, dann optimieren |
| Börsenzugang | `ccxt` + native WebSocket-Clients | Börsenwechsel ohne Umbau; native Streams für Latenz |
| Daten | `polars`, `numpy`, `TimescaleDB` | polars ist deutlich schneller als pandas bei großen Zeitreihen |
| ML | `scikit-learn`, `LightGBM` | Gradient Boosting schlägt Deep Learning bei tabellarischen Finanzdaten fast immer |
| Validierung | `pydantic`, `pytest`, `hypothesis` | Property-Based-Tests für Risk- und Execution-Layer |
| Betrieb | `Docker Compose`, `Prometheus`, `Grafana` | Reproduzierbar, beobachtbar |
| Steuerung | Telegram-Bot | Kontrolle und Alerts vom Handy |

**Markt-Empfehlung:** Krypto Spot. 24/7 (passt zum Ziel), kostenlose historische Daten in
hoher Auflösung, offene APIs mit WebSockets, Testnets zum gefahrlosen Üben, kleine
Mindestordergrößen. Aktien schließen abends und am Wochenende und haben teurere Datenanbindung.

---

## 12. Rechtlicher Rahmen (Deutschland)

Kurz, aber zu klären, bevor Kapital fließt:
- **Steuer:** Jeder Trade ist ein steuerlich relevanter Vorgang. Der Bot schreibt von Anfang an
  ein vollständiges Trade-Log (UTC-Zeitstempel, Symbol, Menge, Preis, Gebühr, Order-ID) und
  exportiert es maschinenlesbar. Bei hoher Frequenz und größerem Kapital: Steuerberater fragen.
- **Eigenhandel ist erlaubnisfrei.** Fremdes Kapital verwalten wäre BaFin-erlaubnispflichtig.
- **Börsen-AGB:** API-Handel ist bei allen großen Börsen ausdrücklich erlaubt; Rate-Limits einhalten.

---

## 13. Nächster Schritt

Ich beginne mit **Sprint 1 + 2**: Projektgerüst, Docker-Setup, Konfiguration, Logging und die
komplette Datenschicht mit Live-WebSocket-Anbindung, Qualitätsprüfung und Persistenz — die
Basis, auf der alles andere aufsetzt.

Offen von dir: Börse/Markt bestätigen (Vorschlag: Binance oder Bybit, Krypto Spot) und ob
der Bot später auf einem eigenen VPS laufen soll (empfohlen) oder anderswo.
