# Trade-

Halbautomatischer Trading-Assistent für **Gold (XAU/USD)** und **Silber (XAG/USD)**.
Claude analysiert, du führst die Trades selbst in MetaTrader 5 aus.

**Aktueller Stand:** Analyse-Engine, Scalping-Modus, Backtest und MetaTrader-EA implementiert
und getestet (292 Tests). Nächster Schritt: Backtest auf echter Historie, dann Journal-Modul.

> **Ehrlichkeitshinweis:** Die Strategie hat **keinen nachgewiesenen positiven
> Erwartungswert**. Siehe [docs/BACKTEST-ERGEBNISSE.md](./docs/BACKTEST-ERGEBNISSE.md).
> Belegt ist bislang die Regeldisziplin — korrekte Größen, haltbare Stops, ein Tageslimit
> das greift. Das ist wertvoll und nicht dasselbe wie eine Kante.

## Im Chat

```
/trade
```

Claude analysiert Gold, sagt **hoch / runter / abwarten**, nennt Einstieg, Stop, zwei Ziele
und Positionsgröße — und sagt ausdrücklich, **wann du aufhören sollst**. Definiert in
[.claude/commands/trade.md](./.claude/commands/trade.md).

## In MetaTrader 5

Der Assistent läuft auch direkt als Expert Advisor — gleiche Setups, gleiche Risikoregeln,
**eine einzige Datei** nach `MQL5/Experts` kopieren. Installation und Einstellungen:
**[mt5/README.md](./mt5/README.md)**.

**Auf dem Handy geht ein EA nicht** — die MT5-App hat keine EA-Engine, das gilt für jeden
Expert Advisor. Der Weg, der vom iPad aus funktioniert:
**[mt5/MOBILE-SETUP.md](./mt5/MOBILE-SETUP.md)**. Wenn ein VPS schon da ist, führt
**[mt5/VPS-SETUP.md](./mt5/VPS-SETUP.md)** Schritt für Schritt durch die Einrichtung —
Windows und Linux.

**Startet im Advisor-Modus:** Er zeichnet, rechnet und meldet, platziert aber keine Order.
So kannst du seine Einschätzung mit deiner eigenen vergleichen, bevor er etwas ausgeben
darf. Der Auto-Modus ist eine bewusste Umschaltung, kein Standard.

## Auf der Kommandozeile

```bash
python -m metals stop --equity 10000            # Darf ich gerade handeln?
python -m metals analyse XAUUSD --equity 10000  # Vollständige Top-Down-Analyse
python -m metals check                          # Was ist erreichbar? Welche Session?
python -m metals setups scalp                   # Der Scalping-Katalog S1–S6
python -m metals ratio                          # Gold/Silber-Ratio und Regime
python -m metals rules                          # Risikoregeln und Kontraktspezifikationen
python -m metals minimum XAUUSD --equity 55     # Reicht mein Konto für dieses Metall?
python -m metals backtest --source live         # Backtest, letzte ~60 Tage
python -m metals backtest --source file \
    --file XAU_5m_data.csv --tz broker_gmt3     # Backtest auf echter Historie
```

Für ein Mehrjahresfenster brauchst du eine **heruntergeladene Datei** — jede kostenlose
Live-API kappt Intraday-Historie bei 30–60 Tagen. Quellen und die Zeitzonenfalle:
[docs/DATENQUELLEN.md](./docs/DATENQUELLEN.md).

Keine Installation nötig — reine Standardbibliothek, Python 3.11+.

Ohne API-Schlüssel funktioniert alles über kostenlose Quellen. Schlüssel verbessern
Auflösung und Zuverlässigkeit:

```bash
export TWELVEDATA_API_KEY="..."   # saubere Kerzendaten
export FRED_API_KEY="..."         # stabile Makro-Anbindung
export FINNHUB_API_KEY="..."      # Live-Wirtschaftskalender
```

## Dokumente

| Dokument | Inhalt |
|---|---|
| **[docs/GOLD-SILBER.md](./docs/GOLD-SILBER.md)** | Wissensbasis Edelmetalle: Treiber, Sessions, Setups G1–G12, Risiko, typische Fehler |
| **[docs/GOLD-SCALPING.md](./docs/GOLD-SCALPING.md)** | Scalping: Setups S1–S6, Ausstiege, wann aufhören, Backtest-Methodik |
| **[docs/BACKTEST-ERGEBNISSE.md](./docs/BACKTEST-ERGEBNISSE.md)** | Gemessene Ergebnisse aus 100 Marktläufen — mit Einordnung, was sie belegen und was nicht |
| **[mt5/README.md](./mt5/README.md)** | Expert Advisor für MetaTrader 5: Installation, Einstellungen, Strategietester |
| **[mt5/MOBILE-SETUP.md](./mt5/MOBILE-SETUP.md)** | Warum ein EA auf dem Handy nicht geht, und wie es vom iPad aus trotzdem funktioniert |
| **[mt5/VPS-SETUP.md](./mt5/VPS-SETUP.md)** | VPS in 30–60 Minuten einrichten (Windows und Linux), EA installieren, erster Demo-Abend |
| **[docs/DATENQUELLEN.md](./docs/DATENQUELLEN.md)** | Katalog aller angebundenen Datenquellen mit Limits und Vorbehalten |
| **[docs/TRADING-WISSEN.md](./docs/TRADING-WISSEN.md)** | Allgemeine Trading-Wissensbasis (36 Teile) |
| **[docs/BOT-PLAN.md](./docs/BOT-PLAN.md)** | Bau- und Betriebsplan des Assistenten |
| **[docs/ENTSCHEIDUNGEN.md](./docs/ENTSCHEIDUNGEN.md)** | Entscheidungsprotokoll E1–E40 mit Begründungen |
| **[PLAN.md](./PLAN.md)** | Architektur und Roadmap |
| **[CLAUDE.md](./CLAUDE.md)** | Projektregeln für die Zusammenarbeit |

## Architektur

```
Datenquellen  →  Deterministische Rechner  →  Setup-Erkennung  →  Veto-Ebene  →  Sizing
(28 Quellen +    (indicators, levels,         (setups G1–G12,     (News, R2,     (risk.py,
 Datei-Import)    patterns)                    scalping S1–S6)     Session)       exits.py)
                                    ↓                                  ↓
                       Claude liest, ordnet ein, erklärt      metals/backtest.py
                                    ↓                          (prüft dieselben Regeln)
                        Empfehlungskarte  →  du entscheidest  →  MT5
                                                                  ↑
                                              mt5/GoldScalpAssistant.mq5
                                              (dieselben Setups, dieselben Limits)
```

Die Rechner liefern die harten Zahlen, Claude liefert Einordnung und Begründung. Die
Veto-Ebene läuft **zuletzt** und kann die Konfidenz nur senken — keine technische Confluence
darf sich an einer Nachrichtensperre oder einem Tagesverlustlimit vorbeiargumentieren.

## Warum Gold und Silber

Große, institutionell dominierte Bewegungen mit lesbarer Struktur; ein dominanter
Makrotreiber (Realzins und Dollar) statt zwanzig Volkswirtschaften; und mit der
Gold/Silber-Ratio ein eigenes Regime-Signal.

Dieselbe Volatilität macht allerdings jeden Größenfehler entsprechend teurer. Deshalb sind
sechs metallspezifische Regeln (M1–M6) zusätzlich zu R1–R8 fest im Code verankert — unter
anderem ein Mindest-Stop von 1,0 × ATR, ein gemeinsames Risikobudget für beide Metalle und
Flat-Stellung vor dem Wochenende.

## Risikoregeln

Hart im Code, nicht in Konfiguration — eine Änderung erfordert einen Commit:

| | |
|---|---|
| R1–R8 | 1 % pro Trade, −3 % Tagesstopp, CRV ≥ 1:2, News-Sperre, kein Martingale, Stop vor Größe |
| M1–M6 | Mindest-Stop 1,0 × ATR, Puffer jenseits des Levels, Spread-Grenze, gemeinsames Metall-Budget, Wochenend-Flat, keine Stops auf runden Zahlen |

`python -m metals rules` zeigt alle mit Begründung.

## Tests

```bash
python -m unittest discover -s tests -t . -p "test_*.py"
```

292 Tests, vollständig offline — die HTTP-Schicht ist injizierbar, jede Quelle wird gegen
aufgezeichnete Antwortformate geprüft, und der Backtest hat einen Regressionstest gegen
Lookahead. Der MQL5-EA lässt sich hier nicht kompilieren — seine Zeitzonen-Arithmetik ist
deshalb wörtlich nach Python portiert und wird stündlich über vier Jahre gegen die
getestete Implementierung geprüft, dazu jedes Risikolimit gegen sein Python-Gegenstück.

## Hinweis

Dieses Projekt ist keine Anlageberatung und macht keine Ertragsversprechen. Gehandelt wird
ausschließlich eigenes Kapital, in Phase A ausschließlich auf einem Demokonto. Höhere
Volatilität erhöht die Streuung der Ergebnisse, nicht ihren Erwartungswert — der kommt aus
der Regeltreue.
