# Projektregeln für Claude

## Arbeitsweise mit dem Nutzer

**Immer nachfragen statt annehmen.** Dauerhafte Anweisung des Nutzers (25.07.2026):
Wenn bei einer Aufgabe etwas unklar ist — Marktwahl, Kapital, Prioritäten, technische
Entscheidungen, Zielsetzung — wird gefragt, nicht geraten.

Konkret:
- Offene Fragen werden gesammelt und am Ende der Aufgabe gestellt, damit die eigentliche
  Arbeit nicht blockiert wird.
- Wenn eine Frage die Arbeit blockiert (falsche Annahme würde alles wertlos machen), wird
  sofort gefragt.
- Getroffene Annahmen werden explizit genannt, nicht stillschweigend gesetzt.

## Sprache

Kommunikation und Dokumentation auf Deutsch. Code, Variablennamen, Commit-Messages und
Log-Ausgaben auf Englisch.

## Git

- Entwicklung auf `claude/trading-bot-plan-4uj86r`
- Keine Pull Requests ohne ausdrückliche Aufforderung

## Inhaltliche Grundsätze für dieses Projekt

- **Quellen kennzeichnen.** Bei recherchierten Zahlen unterscheiden zwischen akademischen
  Quellen, Regulierungsdaten und Anbieter-Backtests. Marketingzahlen nicht als Fakten führen.
- **Keine Ertragsversprechen.** Erwartungswerte und Risiken werden nüchtern dargestellt.
- **Risikolimits gehören in den Code**, nicht in Konfigurationsdateien — Änderungen sollen
  einen Commit erfordern.
- **Backtest, Paper und Live nutzen identischen Code.** Nur der Exchange-Adapter wird getauscht.
