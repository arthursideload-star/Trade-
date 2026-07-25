# Trade-

Trading-Assistent für Forex. Claude analysiert auf Anfrage ein Währungspaar und gibt eine
begründete Empfehlung — gehandelt wird manuell auf einem MT5-Demokonto.

**Aktueller Stand:** Phase A, Sprints B1–B4 abgeschlossen — von der Datenanbindung bis zur
Empfehlungskarte. Es fehlen nur noch News-Veto (B5) und Trade-Journal (B6).

## Zwei Phasen

| Phase | Was | Stand |
|---|---|---|
| **A** | Halbautomat: Claude als Gehirn, Analyse auf Anfrage, du klickst die Trades selbst | in Arbeit |
| **B** | Vollautomat: handelt selbstständig, plus Dashboard | später, erst wenn A sich bewährt hat |

## Sprints (Phase A)

| Sprint | Inhalt | Stand |
|---|---|---|
| **B1** | Projektgerüst als Skills-Projekt, Twelve-Data-Anbindung, erste Kerzen | fertig |
| **B2** | Deterministische Rechner: Trend/Regime, Indikatoren, Level, ATR, Größe, R:R | fertig |
| **B3** | Kerzen-, Muster- und Fehlausbruch-Erkennung, ausschließlich am Level | fertig |
| **B4** | Top-Down-Orchestrierung durch Claude, Empfehlungskarte | fertig |
| **B5** | News-Anbindung und News-Veto, Wirtschaftskalender | offen |
| **B6** | Trade-Journal und wöchentliche Auswertung | offen |

## Aufbau

```
skills/forex-data/       Kerzendaten von Twelve Data (B1)
skills/forex-analysis/    Indikatoren, Regime, Level, Muster, Sizing, R1–R8 (B2+B3)
skills/forex-signal/      Signal-Score und Empfehlungskarte (B4)
backend/                  Optionales Dashboard (Phase A.5), nutzt denselben Client
docs/                     Pläne und Wissensbasis
```

Jeder Skill folgt derselben Form: `SKILL.md` (wann/wie Claude ihn nutzt), `scripts/` (reine
Standardbibliothek, keine Installation nötig), `scripts/tests/` und `references/`.

Es gibt genau **eine** Stelle mit API-Zugriff: `skills/forex-data/scripts/twelvedata_client.py`.
Alles andere rechnet auf den Kerzen, die von dort kommen. Die Risikoregeln R1–R8 stehen als
Konstanten im Code (`skills/forex-analysis/scripts/risk_rules.py`), nicht in Konfigurationsdateien.

## Einrichtung

```bash
cp .env.example .env          # TWELVEDATA_API_KEY eintragen
export TWELVEDATA_API_KEY=... # oder direkt in der Umgebung setzen
```

Kerzen holen — ohne jede Installation:

```bash
python skills/forex-data/scripts/fetch_candles.py --symbol EUR/USD --interval 5m,15m,1h,4h
```

Vollständige Empfehlung für ein Paar:

```bash
python skills/forex-signal/scripts/recommend.py --symbol EUR/USD --account 10000 --format text
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
