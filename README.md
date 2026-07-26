# Trade-

Halbautomatischer Trading-Assistent für **Gold (XAU/USD)** und **Silber (XAG/USD)**.
Claude analysiert, du führst die Trades selbst in MetaTrader 5 aus.

**Aktueller Stand:** Analyse-Engine implementiert und getestet (191 Tests). Wissensbasis und
Datenquellen-Anbindung stehen. Nächster Schritt: Journal-Modul.

## Schnellstart

```bash
python -m metals check                          # Was ist erreichbar? Welche Session?
python -m metals analyse XAUUSD --equity 10000  # Vollständige Top-Down-Analyse
python -m metals ratio                          # Gold/Silber-Ratio und Regime
python -m metals rules                          # Risikoregeln und Kontraktspezifikationen
```

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
| **[docs/DATENQUELLEN.md](./docs/DATENQUELLEN.md)** | Katalog aller angebundenen Datenquellen mit Limits und Vorbehalten |
| **[docs/TRADING-WISSEN.md](./docs/TRADING-WISSEN.md)** | Allgemeine Trading-Wissensbasis (36 Teile) |
| **[docs/BOT-PLAN.md](./docs/BOT-PLAN.md)** | Bau- und Betriebsplan des Assistenten |
| **[docs/ENTSCHEIDUNGEN.md](./docs/ENTSCHEIDUNGEN.md)** | Entscheidungsprotokoll E1–E23 mit Begründungen |
| **[PLAN.md](./PLAN.md)** | Architektur und Roadmap |
| **[CLAUDE.md](./CLAUDE.md)** | Projektregeln für die Zusammenarbeit |

## Architektur

```
Datenquellen  →  Deterministische Rechner  →  Setup-Erkennung  →  Veto-Ebene  →  Sizing
(28 Quellen,     (metals/indicators.py,       (metals/setups.py)  (News, R2,     (metals/risk.py)
 7 Kategorien)    levels.py, patterns.py)                          Session)
                                    ↓
                          Claude liest, ordnet ein, erklärt
                                    ↓
                        Empfehlungskarte  →  du entscheidest  →  MT5
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

191 Tests, vollständig offline — die HTTP-Schicht ist injizierbar, jede Quelle wird gegen
aufgezeichnete Antwortformate geprüft.

## Hinweis

Dieses Projekt ist keine Anlageberatung und macht keine Ertragsversprechen. Gehandelt wird
ausschließlich eigenes Kapital, in Phase A ausschließlich auf einem Demokonto. Höhere
Volatilität erhöht die Streuung der Ergebnisse, nicht ihren Erwartungswert — der kommt aus
der Regeltreue.
