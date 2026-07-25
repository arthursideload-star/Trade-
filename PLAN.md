# Entwicklungsplan: Autonomer Trading-Bot

Status: Entwurf (Phase 0)
Letzte Aktualisierung: 2026-07-25

---

## 0. Realitätscheck (bitte zuerst lesen)

Bevor eine Zeile Code entsteht, müssen ein paar Dinge klar sein — sonst baut man 3 Monate
an etwas, das strukturell kein Geld verdienen kann.

**Was ein Trading-Bot ist:** Eine Software, die eine statistische Hypothese über einen Markt
automatisiert ausführt. Der Bot ist der einfache Teil. Die Hypothese (die "Edge") ist der
schwere Teil — und die kann man nicht programmieren, nur finden und testen.

**Was er nicht ist:** Passives Einkommen. Ein laufender Bot bedeutet:
- Kapital ist permanent Marktrisiko ausgesetzt (Totalverlust ist möglich)
- laufende Wartung: APIs ändern sich, Börsen fallen aus, Strategien verfallen ("Alpha Decay")
- Überwachung: ein Bug in einer Order-Schleife kann in Minuten das Konto leeren
- Steuerpflicht: jeder einzelne Trade ist ein steuerlich relevanter Vorgang

**Nüchterne Erwartung:** Die überwiegende Mehrheit privater Trading-Bots verliert Geld —
meist nicht wegen schlechter Software, sondern wegen (a) Gebühren/Slippage, die im Backtest
fehlten, (b) Overfitting an historische Daten, (c) fehlendem Risikomanagement. Die ersten
2–3 Strategien wegzuwerfen ist der Normalfall, nicht das Scheitern.

**Konsequenz für den Plan:** Jede Phase hat ein *Gate*. Wird das Gate nicht bestanden, geht es
nicht weiter zu echtem Geld. Das ist die wichtigste Eigenschaft dieses Plans.

---

## 1. Entscheidungen, die vor Phase 1 fallen müssen

Diese vier Fragen bestimmen praktisch die gesamte Architektur:

| Frage | Optionen | Empfehlung für den Start |
|---|---|---|
| **Markt** | Krypto (Spot), Aktien/ETF, Futures, Forex | **Krypto Spot** — 24/7, gute APIs, kostenlose Historie, kleine Mindestgrößen, Testnets vorhanden |
| **Zeithorizont** | HFT (ms), Intraday (min), Swing (h–Tage), Position (Wochen) | **Swing, 1h–4h Kerzen** — keine Latenz-Konkurrenz gegen Profis, weniger Gebühren, Bugs sind nicht sofort fatal |
| **Startkapital** | — | Betrag, dessen **Totalverlust dich nicht trifft**. Für die Live-Phase: 200–500 €. Mehr bringt in der Lernphase nichts. |
| **Strategie-Typ** | Trendfolge, Mean Reversion, Arbitrage, Market Making, ML-basiert | **Trendfolge** — robust, wenig Parameter, gut verstanden, verzeiht Latenz. ML kommt frühestens in Phase 6. |

> **Warum kein HFT/Arbitrage:** Dort konkurrierst du mit Firmen, die Server im selben
> Rechenzentrum wie die Börse stehen haben. Das ist kein fairer Kampf.

> **Warum kein Market Making zum Start:** Funktioniert, ist aber Inventar-Risiko-Management
> auf hohem Niveau und braucht sehr gute Ausführungs-Infrastruktur.

**Offene Punkte für dich:** Markt und Startkapital bestätigen. Der restliche Plan geht ab hier
von *Krypto Spot, Swing-Trading, Python* aus und ist bei anderer Wahl in den Details anzupassen
(die Architektur bleibt gleich).

---

## 2. Zielarchitektur

Kernprinzip: **Dieselbe Strategie-Logik läuft in Backtest, Paper-Trading und Live.** Wenn
Backtest und Live unterschiedlichen Code benutzen, sind Backtest-Ergebnisse wertlos. Der
einzige Unterschied ist der ausgetauschte Broker-Adapter.

```
                  ┌──────────────────────────────────┐
                  │            Strategy               │
                  │  on_bar(state) -> Signal          │
                  │  (reine Funktion, kein I/O)       │
                  └───────────────┬──────────────────┘
                                  │ Signal(BUY/SELL/FLAT, Stärke)
                  ┌───────────────▼──────────────────┐
                  │         Risk Manager              │
                  │  Positionsgröße, Limits, Kill-    │
                  │  Switch — hat Vetorecht           │
                  └───────────────┬──────────────────┘
                                  │ Order(Symbol, Menge, Typ)
                  ┌───────────────▼──────────────────┐
                  │      Execution / Broker-Port      │  ← Interface
                  └───┬───────────┬───────────────┬──┘
                      │           │               │
              ┌───────▼──┐  ┌─────▼──────┐  ┌────▼─────┐
              │ Backtest │  │   Paper    │  │   Live   │
              │ Simulator│  │  (Testnet) │  │ (Exchange)│
              └──────────┘  └────────────┘  └──────────┘

  Querschnitt: Market Data Feed · Portfolio/State Store · Logging · Monitoring · Alerting
```

### Komponenten im Einzelnen

1. **Market Data Feed** — Historische Daten (CSV/Parquet, lokal gecached) und Live-Daten
   (WebSocket, mit REST-Fallback). Ein einheitliches `Bar`-Format für beides.
2. **Strategy** — Bekommt Marktzustand, gibt ein Signal zurück. **Kein Netzwerk, keine
   Datenbank, keine Uhr** — dadurch deterministisch und testbar.
3. **Risk Manager** — Die wichtigste Komponente. Übersetzt Signale in Ordergrößen und darf
   jede Order ablehnen. Details in Abschnitt 4.
4. **Execution Engine** — Order-Platzierung, Retry-Logik, Idempotenz (Client Order IDs!),
   Abgleich zwischen erwarteter und tatsächlicher Position ("Reconciliation").
5. **Portfolio/State Store** — SQLite. Muss einen Neustart überleben: Beim Hochfahren wird
   der tatsächliche Kontostand von der Börse gelesen und mit dem lokalen Zustand abgeglichen.
6. **Observability** — Strukturierte Logs, tägliche Performance-Zusammenfassung, Alerts
   (Telegram/Discord/E-Mail) bei Fehlern und Limit-Verletzungen.

### Tech-Stack

- **Python 3.12** — Ökosystem für Backtesting und Datenanalyse ist konkurrenzlos
- `pandas` / `numpy` / `polars` — Datenverarbeitung
- `ccxt` — einheitlicher Zugang zu ~100 Krypto-Börsen (Wechsel ohne Code-Umbau)
- `pydantic` — Konfiguration und Validierung
- `pytest` + `hypothesis` — Tests, inkl. Property-Based-Tests für den Risk Manager
- `SQLite` — Zustand und Trade-Historie
- `structlog` — strukturiertes Logging
- **Docker** — reproduzierbarer Betrieb
- **VPS** (Hetzner ~5 €/Monat) — nicht der Laptop; der Bot muss 24/7 laufen

---

## 3. Phasenplan

### Phase 0 — Fundament (ca. 1 Woche)
- Repo-Struktur, Dependency-Management (`uv` oder `poetry`), Linting, CI
- Datenanbindung: historische OHLCV-Daten herunterladen und lokal cachen
- Datenqualitäts-Checks: Lücken, Duplikate, Zeitzonen, Splits/Ausreißer
- **Gate:** Zwei Jahre saubere Stundenkerzen für 3–5 Symbole liegen reproduzierbar lokal vor.

### Phase 1 — Backtest-Engine (2–3 Wochen)
Der kritischste Teil. Ein zu optimistischer Backtest ist schlimmer als gar keiner.
- Event-getriebene Schleife (**keine** vektorisierte Abkürzung — die verführt zu Look-Ahead-Bias)
- Realistisches Kostenmodell: Maker/Taker-Gebühren, Spread, **Slippage**, Funding-Kosten
- Ausführungsannahme: Orders werden auf der Eröffnung der *nächsten* Kerze gefüllt, nie
  auf dem Schlusskurs derselben — sonst handelst du mit Wissen aus der Zukunft
- Kennzahlen: CAGR, Max Drawdown, Sharpe, Sortino, Trefferquote, Profit Factor,
  durchschnittliche Haltedauer, Turnover
- **Gate:** Eine bewusst unrentable Test-Strategie (z. B. Zufallssignale) zeigt im Backtest
  korrekt einen Verlust in Höhe der Gebühren. Wenn Zufall profitabel aussieht, ist die
  Engine kaputt.

### Phase 2 — Erste Strategie (2 Wochen)
- Bewusst simpel: z. B. Donchian-Breakout oder Dual Moving Average Crossover mit
  ATR-basiertem Stop. **Maximal 3 Parameter.**
- Testen über mehrere Symbole und mehrere Marktregime (Bullenmarkt, Bärenmarkt, Seitwärts)
- **Walk-Forward-Analyse** statt einmaliger Optimierung: Parameter auf Zeitfenster A
  optimieren, auf dem *folgenden* Fenster B testen, Fenster vorschieben, wiederholen.
  Nur die Out-of-Sample-Ergebnisse zählen.
- **Gate:** Positive Erwartung *nach Kosten* über mindestens 3 unabhängige
  Out-of-Sample-Perioden. Nicht bestanden → zurück zur Hypothese, nicht Parameter feintunen.

> ⚠️ **Die Overfitting-Falle:** Wer lange genug an Parametern dreht, findet immer eine
> Kombination, die historisch großartig aussieht. Sie funktioniert in der Zukunft nicht.
> Faustregel: Wenn die Ergebnisse bei kleiner Parameteränderung (±20 %) zusammenbrechen,
> ist die Strategie überangepasst und wertlos.

### Phase 3 — Risk Layer (1 Woche)
Wird *vor* dem ersten Live-Trade gebaut, nicht danach. Siehe Abschnitt 4.
- **Gate:** Property-Based-Tests belegen, dass kein Signal — auch kein fehlerhaftes,
  extremes oder widersprüchliches — die harten Limits verletzen kann.

### Phase 4 — Paper-Trading (mindestens 4–8 Wochen, live mitlaufend)
- Gleicher Code, Broker-Adapter zeigt auf das Exchange-Testnet
- Läuft 24/7 auf dem VPS unter realen Bedingungen: Netzausfälle, API-Rate-Limits,
  Börsen-Wartungsfenster, Neustarts
- Täglich wird der Paper-Ertrag mit dem Backtest-Ertrag auf denselben Daten verglichen
- **Gate:** Zwei Bedingungen, beide müssen erfüllt sein:
  1. 30 Tage Dauerbetrieb ohne manuellen Eingriff
  2. Abweichung zwischen Paper- und Backtest-Ergebnis unter ~20 % — größere Lücken bedeuten,
     dass der Backtest die Realität falsch modelliert (meist Slippage)

### Phase 5 — Live mit Minimalkapital (mindestens 8 Wochen)
- Startkapital wie in Abschnitt 1 definiert. Kein Aufstocken bei Zwischengewinnen.
- Getrennter, API-Key mit **auf Trading beschränkten Rechten — Auszahlungen deaktiviert**,
  IP-Whitelist auf den VPS
- Manueller Kill-Switch (ein Kommando, das alle Positionen schließt und den Bot stoppt)
- Wöchentliches Review: läuft es wie im Paper-Trading?
- **Gate:** 8 Wochen ohne kritischen Vorfall und Ergebnis im Rahmen der Paper-Erwartung.

### Phase 6 — Skalierung & Diversifikation (fortlaufend)
Erst ab hier lohnt Aufwand für mehr Ertrag:
- Kapital schrittweise erhöhen (in Stufen, nie verdoppeln)
- Mehrere unkorrelierte Strategien parallel — der größte einzelne Hebel für ruhigere
  Ergebnisse, deutlich wirksamer als eine Strategie weiter zu optimieren
- Portfolio-Ebene: Risikobudget über Strategien verteilen
- Optional ML-basierte Signale — aber erst, wenn die klassische Pipeline nachweislich trägt

### Phase 7 — Betrieb als Dauerzustand
- Monatliches Performance-Review gegen eine Benchmark (Buy & Hold!)
- Automatische Degradations-Erkennung: Wenn der Live-Drawdown den historischen
  Maximum-Drawdown überschreitet, pausiert der Bot selbstständig
- Steuerreporting-Export

---

## 4. Risikomanagement (nicht verhandelbar)

Diese Regeln stehen als harte Grenzen im Code, nicht in der Strategie-Konfiguration. Sie
sind der Unterschied zwischen "Strategie funktionierte nicht" und "Konto ist leer".

| Regel | Wert (Startpunkt) | Zweck |
|---|---|---|
| Risiko pro Trade | max. 1 % des Kontos | Eine Verlustserie von 10 Trades kostet ~10 %, nicht alles |
| Positionsgröße | über ATR/Volatilität berechnet | Gleiches Risiko unabhängig davon, wie wild das Asset schwankt |
| Max. Positionen gleichzeitig | 3–5 | Begrenzt Klumpenrisiko |
| Täglicher Verlust-Stopp | −3 % → Bot pausiert bis nächster Tag | Stoppt Fehlerkaskaden |
| Gesamt-Drawdown-Stopp | −15 % → Bot stoppt, manuelle Freigabe nötig | Letzte Reißleine |
| Hebel | keiner (Spot) | Hebel tötet Anfängerkonten, nicht schlechte Strategien |
| Order-Rate-Limit | max. N Orders/Stunde | Fängt Endlosschleifen-Bugs ab |
| Sanity-Check pro Order | Größe > 0, < X % des Kontos, Preis in plausibler Spanne | Fängt Vorzeichen- und Einheitenfehler ab |

**Kill-Switch:** Sowohl automatisch (bei Limitverletzung, API-Fehlerserie, Datenausfall) als
auch manuell auslösbar. Beim Auslösen: alle offenen Orders stornieren, Positionen glattstellen,
Alert senden, Prozess beenden.

**Fail-safe statt fail-open:** Wenn der Bot seinen eigenen Zustand nicht sicher kennt
(Verbindungsabbruch mitten in einer Order, widersprüchliche Positionsdaten), wird **nicht
gehandelt**. Er alarmiert und wartet auf einen Menschen.

---

## 5. Häufigste Fehlerquellen (Checkliste gegen sich selbst)

| Fehler | Symptom | Gegenmaßnahme |
|---|---|---|
| Look-Ahead-Bias | Backtest unrealistisch gut | Ausführung erst auf nächster Kerze; Indikatoren nur aus abgeschlossenen Kerzen |
| Survivorship Bias | Nur heute existierende Coins/Aktien getestet | Delistete Assets in die Historie aufnehmen |
| Overfitting | Top-Backtest, schwaches Live-Ergebnis | Walk-Forward; wenige Parameter; Parametersensitivität prüfen |
| Kosten unterschätzt | Paper schlechter als Backtest | Slippage konservativ ansetzen, mit Live-Fills nachkalibrieren |
| Doppelte Orders | Position größer als geplant | Idempotente Client Order IDs, Reconciliation beim Start |
| Zeitzonenfehler | Signale zur falschen Stunde | Alles intern in UTC, nur bei der Anzeige umrechnen |
| Zustandsverlust beim Neustart | Bot vergisst offene Positionen | Zustand persistent; beim Start Abgleich gegen Börsenkonto |
| Kein Vergleichsmaßstab | "10 % Gewinn!" während der Markt 40 % stieg | Immer gegen Buy & Hold messen |

---

## 6. Recht und Steuern (Deutschland)

Kein Rechtsrat, aber die Punkte, die du klären musst:

- **Steuerpflicht:** Krypto-Gewinne fallen unter private Veräußerungsgeschäfte (§ 23 EStG);
  bei hoher Handelsfrequenz kann das Finanzamt gewerblichen Handel annehmen — das ändert
  die Besteuerung grundlegend. Bei nennenswertem Kapital: Steuerberater fragen, bevor der
  Bot live geht.
- **Dokumentationspflicht:** Jeder Trade muss nachvollziehbar sein. Der Bot schreibt von
  Anfang an ein vollständiges, unveränderliches Trade-Log (Zeitstempel UTC, Symbol, Menge,
  Preis, Gebühr, Order-ID).
- **Eigenhandel für andere = Erlaubnispflicht.** Solange du ausschließlich eigenes Geld
  handelst, unproblematisch. Fremdes Geld verwalten ist BaFin-erlaubnispflichtig — dort
  hört Hobby auf.
- **Börsen-AGB:** API-Handel ist bei den großen Börsen erlaubt; Rate-Limits einhalten.

---

## 7. Zeit- und Kostenrahmen

| Phase | Dauer | Kosten |
|---|---|---|
| 0–3 (Entwicklung) | 6–8 Wochen | 0 € |
| 4 (Paper) | 4–8 Wochen | ~5 €/Monat VPS |
| 5 (Live klein) | 8+ Wochen | VPS + Risikokapital 200–500 € |
| 6+ (Betrieb) | dauerhaft | VPS + laufende Wartung |

**Realistisch bis zum ersten echten Trade: 4–5 Monate.** Wer schneller live geht, überspringt
genau die Gates, die vor Verlusten schützen.

---

## 8. Abbruchkriterien

Ein Plan ohne Ausstieg ist eine Falle. Der Bot wird abgeschaltet, wenn:
- der Gesamt-Drawdown 15 % erreicht (Stopp und Analyse, nicht "aussitzen")
- er über 6 Monate live schlechter läuft als Buy & Hold *nach Kosten und Steuern*
- die Strategie in zwei aufeinanderfolgenden Quartals-Reviews ihre Out-of-Sample-Kennzahlen
  nicht mehr erreicht (Alpha Decay)
- der Wartungsaufwand den Ertrag übersteigt

---

## 9. Nächste Schritte

1. **Du entscheidest:** Markt (Empfehlung: Krypto Spot) und Risikokapital.
2. **Ich baue Phase 0:** Repo-Struktur, Datenanbindung, Datenqualitäts-Checks, CI.
3. **Danach Phase 1:** Backtest-Engine mit realistischem Kostenmodell — inklusive des
   Zufallsstrategie-Tests, der beweist, dass die Engine nicht lügt.

Sag Bescheid, womit ich anfangen soll.
