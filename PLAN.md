# Was geplant war, was gebaut wurde, und warum sich das unterscheidet

Diese Datei war bis zum 01.08.2026 ein **Entwicklungsplan** — 307 Zeilen für eine
FastAPI-Web-App mit Lightweight-Charts-Frontend, sieben Forex-Majors, Deployment auf
Render.com und einer Phase B mit automatischem Handel auf Binance-Krypto-Perpetuals.

Davon existiert nichts, und das ist kein Versäumnis, sondern das Ergebnis von
Entscheidungen, die jede für sich richtig waren. Der Plan stand trotzdem unverändert im
Wurzelverzeichnis und beschrieb ein anderes Projekt als das, das hier liegt — inklusive der
Zeile „Offen: Journal-Modul", das seit Tagen fertig ist, und vier offener Fragen, die alle
erledigt oder gegenstandslos sind.

Ein Plan, der etwas anderes beschreibt als der Code daneben, ist keine Dokumentation,
sondern eine Fehlerquelle: Wer ihn liest, fängt an, ein FastAPI-Backend zu suchen. Er ist
deshalb durch diese Seite ersetzt. Der vollständige ursprüngliche Text steht im Git-Verlauf.

---

## Was aus jedem Teil geworden ist

| Ursprünglich geplant | Tatsächlich | Warum |
|---|---|---|
| 7 Forex-Majors (EUR/USD, GBP/USD …) | **nur XAU/USD und XAG/USD** | Entscheidung E18. Ein Instrument gründlich schlägt sieben oberflächlich, und Gold hat eine eigene Mechanik — Kontraktgröße, Hebelgrenze 1:20, Swap-Asymmetrie —, die sich nicht nebenbei mitnehmen lässt |
| FastAPI-Backend | **`python -m metals`, reine Standardbibliothek** | Es gibt keinen Server, weil keiner gebraucht wird. Nichts zu installieren, nichts zu deployen, nichts, das ausfällt |
| Lightweight-Charts-Frontend, mobil | **`web/rechner.html`**, eine Datei | Der Chart lag schon in MT5. Gebraucht wurde ein Rechner, kein zweiter Chart |
| Deployment auf Render.com / Hetzner | **entfällt** | Siehe oben |
| Phase B: autonomer Bot auf Binance, Krypto-Perpetuals | **MQL5-Expert für MT5, Gold** | Der Markt war längst entschieden. Ein Krypto-Bot hätte bei null angefangen und alles Gemessene weggeworfen |
| Trade-Journal als Sprint A5 | **`metals/journal.py` und `metals paper`** | Gebaut, und weiter als geplant: die Papier-Kette rechnet ein Konto fort und protokolliert je Zeile das Kostenmodell und das Regelwerk, mit dem gerechnet wurde |
| „Bauzeit bis zur benutzbaren Web-App: ca. 1,5–2 Wochen" | — | Die Bauzeit war nie das Problem. Die Zeit ging in die Frage, ob irgendetwas davon Geld verdient |

---

## Wo der aktuelle Stand steht

| Frage | Datei |
|---|---|
| Was das Projekt kann, in Befehlen | [README.md](./README.md) |
| Was falsch war und behoben ist (A1–A26) | [docs/REPO-AUDIT.md](./docs/REPO-AUDIT.md) |
| Das Urteil an der vorher festgelegten Stichprobe | [docs/URTEIL.md](./docs/URTEIL.md) |
| Die laufende Papier-Kette mit 400 € | [docs/PAPIER-LAUF.md](./docs/PAPIER-LAUF.md) |
| Welche Entscheidung wann und warum fiel | [docs/ENTSCHEIDUNGEN.md](./docs/ENTSCHEIDUNGEN.md) |
| Architektur des Assistenten | [docs/BOT-PLAN.md](./docs/BOT-PLAN.md) |

---

## Der eine offene Punkt, der zählt

Die alten offenen Fragen O1–O4 — Broker-Wahl, API-Schlüssel, Deployment-Ziel,
Claude-API-Anbindung — sind erledigt oder gegenstandslos. Übrig ist einer, und er wiegt
schwerer als alle vier zusammen:

> **Kein einziges Ergebnis dieses Repositories ist an echter Intraday-Historie geprüft.**
> Alles Gemessene läuft auf `metals/simulate.py` — einer generierten Kursreihe, die
> dokumentierte statistische Eigenschaften von Gold nachbildet, nicht Gold.

Was sich daraus trotzdem übertragen lässt, ist **Arithmetik**: Spread, Margin, Losgröße,
Swap, und dass eine Trefferquote keine Kante ist. Was sich **nicht** überträgt, sind
Aussagen über Verhalten: welche Session besser läuft, ob ein Volatilitätsfilter hilft, wie
hoch der Erwartungswert ist.

Der Lauf, der das entscheidet, braucht eine heruntergeladene Datei und läuft auf dem
Rechner des Nutzers:

```bash
python -m metals dayrange --file XAU_5m_data.csv --tz broker_gmt3 \
    --equity 400 --risk 1
python -m metals backtest --source file --file XAU_5m_data.csv --tz broker_gmt3
```

Quellen für die Datei: [docs/DATENQUELLEN.md](./docs/DATENQUELLEN.md). Jede kostenlose
Live-API kappt Intraday-Historie bei 30–60 Tagen, deshalb muss sie von Hand kommen.
