# Trade-

Trading-Assistent für Forex. Claude analysiert auf Anfrage ein Währungspaar und gibt eine
begründete Empfehlung — gehandelt wird manuell auf einem MT5-Demokonto.

**Aktueller Stand:** Phase A, Sprint B1 abgeschlossen — die Datenanbindung steht.

## Zwei Phasen

| Phase | Was | Stand |
|---|---|---|
| **A** | Halbautomat: Claude als Gehirn, Analyse auf Anfrage, du klickst die Trades selbst | in Arbeit |
| **B** | Vollautomat: handelt selbstständig, plus Dashboard | später, erst wenn A sich bewährt hat |

## Sprints (Phase A)

| Sprint | Inhalt | Stand |
|---|---|---|
| **B1** | Projektgerüst als Skills-Projekt, Twelve-Data-Anbindung, erste Kerzen | fertig |
| **B2** | Deterministische Rechner: Trend/Regime, Indikatoren, Level, ATR, Größe, R:R | offen |
| **B3** | Kerzen-, Muster- und Fehlausbruch-Erkennung, ausschließlich am Level | offen |
| **B4** | Top-Down-Orchestrierung durch Claude, Empfehlungskarte | offen |
| **B5** | News-Anbindung und News-Veto, Wirtschaftskalender | offen |
| **B6** | Trade-Journal und wöchentliche Auswertung | offen |

## Aufbau

```
skills/forex-data/       Kerzendaten von Twelve Data (Sprint B1)
  SKILL.md               Wann und wie Claude den Skill nutzt
  scripts/               Standardbibliothek, keine Installation nötig
  references/            API-Referenz, Limits, Fallstricke
backend/                 Optionales Dashboard (Phase A.5), nutzt denselben Client
docs/                    Pläne und Wissensbasis
```

Es gibt genau **eine** Stelle mit API-Zugriff: `skills/forex-data/scripts/twelvedata_client.py`.
Das Dashboard greift darauf zu, statt eine zweite Anbindung zu pflegen.

## Einrichtung

```bash
cp .env.example .env          # TWELVEDATA_API_KEY eintragen
export TWELVEDATA_API_KEY=... # oder direkt in der Umgebung setzen
```

Kerzen holen — ohne jede Installation:

```bash
python skills/forex-data/scripts/fetch_candles.py --symbol EUR/USD --interval 5m,15m,1h,4h
```

Tests:

```bash
pip install pytest
python -m pytest
```

Optionales Dashboard:

```bash
pip install -r requirements.txt
uvicorn backend.main:app --reload
```

## Dokumente

| Dokument | Inhalt |
|---|---|
| **[docs/BOT-PLAN.md](./docs/BOT-PLAN.md)** | Maßgeblicher Bau- und Betriebsplan: Claude als Gehirn, Skills, Risikoregeln, Sprints |
| **[PLAN.md](./PLAN.md)** | Architektur und Roadmap beider Phasen |
| **[docs/TRADING-WISSEN.md](./docs/TRADING-WISSEN.md)** | Wissensbasis: Kerzen, Setups, Risiko, Validierung, Datenquellen |
| **[docs/ENTSCHEIDUNGEN.md](./docs/ENTSCHEIDUNGEN.md)** | Getroffene Projektentscheidungen |
| **[CLAUDE.md](./CLAUDE.md)** | Projektregeln für die Zusammenarbeit |

## Risikoregeln

Die harten Grenzen (R1–R8 in [docs/BOT-PLAN.md](./docs/BOT-PLAN.md)) stehen im Code, nicht in
Konfigurationsdateien — eine Änderung soll einen Commit erfordern. Sie greifen ab Sprint B2,
sobald Positionsgrößen berechnet werden.

## Hinweis

Handel setzt eingesetztes Kapital dem Marktrisiko aus. Dieses Projekt gibt Empfehlungen,
keine Vorhersagen, und ist keine Anlageberatung.
