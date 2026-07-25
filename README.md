# Trade-

Autonomer Trading-Bot: läuft 24/7, analysiert den Markt über mehrere Zeitebenen und handelt
selbstständig.

**Aktueller Stand:** Architektur und Roadmap stehen. Implementierung beginnt mit Sprint 1.

## Dokumente

| Dokument | Inhalt |
|---|---|
| **[PLAN.md](./PLAN.md)** | Architektur und Umsetzungs-Roadmap (Sprints S1–S10) |
| **[docs/BOT-PLAN.md](./docs/BOT-PLAN.md)** | Konkreter Bau- und Betriebsplan des Assistenten (Claude als Gehirn, Skills + MCP) |
| **[docs/TRADING-WISSEN.md](./docs/TRADING-WISSEN.md)** | Recherchierte Wissensbasis: Gewinn- und Verlustmechanik, Kerzen, Charts, Setups, Krypto-Signale, Validierung, Risiko, Datenquellen |
| **[CLAUDE.md](./CLAUDE.md)** | Projektregeln für die Zusammenarbeit |

## Systemüberblick

```
Market Data → Feature Engine → Analysis Engine → Risk Engine → Execution → Exchange
              (Multi-TF)       (Regime +          (Sizing)      (Slicing,
                                Ensemble)                        Idempotenz)
```

Backtest, Paper-Trading und Live-Betrieb nutzen identischen Code — getauscht wird nur der
Exchange-Adapter.

## Kernmerkmale

- **24/7-Betrieb** mit Watchdog, Auto-Reconnect und vollständiger Zustandswiederherstellung
  nach Neustart
- **Multi-Timeframe-Analyse** (1m bis 1d) mit Regime-Erkennung und Signal-Ensemble
- **Konfidenzbasierte Positionsgrößen** statt binärer Kauf/Verkauf-Entscheidungen
- **Präzise Ausführung**: adaptive Limit-Orders, Order-Slicing, idempotente Order-IDs,
  laufende Slippage-Messung
- **Fernsteuerung und Alerts** per Telegram

## Stack

Python 3.12 (asyncio) · ccxt · polars · TimescaleDB · LightGBM · Docker · Prometheus/Grafana

## Hinweis

Automatisierter Handel setzt eingesetztes Kapital dem Marktrisiko aus. Es wird ausschließlich
eigenes Kapital gehandelt. Dieses Projekt ist keine Anlageberatung.
