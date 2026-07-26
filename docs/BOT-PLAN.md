# Bau- und Betriebsplan des Trading-Assistenten

Stand: 2026-07-25, aktualisiert 2026-07-26. Dieses Dokument ist so geschrieben, dass ein
**neuer Chat** direkt danach bauen kann. Es verfeinert Phase A aus `PLAN.md` mit der
Entscheidung, **Claude selbst als Gehirn** zu nutzen.

> **Aktualisierung 2026-07-26 (Entscheidung E18):** Der Marktscope für Phase A ist von
> „Forex allgemein" auf **Gold (XAU/USD) und Silber (XAG/USD)** verengt worden. Die
> Architektur unten gilt unverändert; die konkrete Umsetzung liegt im Paket `metals/`, die
> fachliche Grundlage in **[GOLD-SILBER.md](./GOLD-SILBER.md)** und der Quellenkatalog in
> **[DATENQUELLEN.md](./DATENQUELLEN.md)**.
>
> **Stand der Sprints:** B1 bis B5 sind umgesetzt (Daten, Rechner, Muster, Orchestrierung,
> News-Veto + Kalender). Offen ist B6 (Journal).

---

## 1. Die zentrale Entscheidung: Claude als Gehirn — ehrlich erklärt

Der Nutzer möchte Claude (Opus) als Gehirn nutzen, über sein Abo, ohne pro Analyse zu zahlen. Das
geht — aber man muss zwei Dinge sauber trennen:

| Weg | Was es ist | Kosten | Passt für |
|---|---|---|---|
| **Claude-Abo (Claude Code / claude.ai)** | Interaktive Sitzung: du fragst, Claude analysiert | im Abo enthalten, **keine** Extra-Kosten pro Analyse | **Halbautomat** (Phase A) ✅ |
| **Anthropic-API** | Programmatischer Zugriff, den ein Bot 24/7 selbst aufruft | pro Token, Opus ist teuer | Vollautomat (Phase B, später) |

**Wichtig und ehrlich:** Ein Abo gibt **keinen** API-Schlüssel für einen dauerhaft allein
laufenden Bot. Für einen 24/7-Vollautomaten braucht man die API (Kosten pro Token). **Aber** für
genau das, was du willst — ein Assistent, der dir auf Anfrage Charts/News analysiert und
Empfehlungen gibt — ist das Abo der richtige und günstigste Weg.

**Die Umsetzung, die dein Abo nutzt:** Der Assistent wird als **Claude-Code-Skills-Projekt**
gebaut. Du öffnest es auf Handy/iPad in einer Claude-Sitzung, sagst „analysiere EUR/USD", und
Claude Opus liest die Live-Daten über die Skills/MCPs und gibt die vollständige Empfehlung. Genau
dieses Muster gibt es bereits im zweiten Git-Branch (`claude-trading-skills`, 64 fertige Skills) —
wir bauen darauf auf.

---

## 2. Architektur: Hybrid aus deterministischen Skills + Claude + Live-Daten

Reines „Claude guckt auf den Chart und rät" wäre nicht testbar und nicht präzise. Die belastbare
Bauweise ist ein **Hybrid** — die Skills-Sammlung im Repo macht es genau so:

```
┌──────────────────────────────────────────────────────────────┐
│  DU (Handy / iPad)  — "Analysiere EUR/USD"                    │
└───────────────────────────┬──────────────────────────────────┘
                            │
┌───────────────────────────▼──────────────────────────────────┐
│  CLAUDE OPUS (das Gehirn) — orchestriert, deutet Kontext,     │
│  wendet den Top-Down-Workflow an, schreibt die Empfehlung     │
└───┬─────────────┬─────────────┬─────────────┬────────────────┘
    │             │             │             │
┌───▼───┐   ┌─────▼─────┐  ┌────▼─────┐  ┌────▼──────────┐
│ Daten │   │Deterministi-│ │  News-   │  │ Disclosure-/  │
│-Skill │   │sche Rechner │ │  MCP     │  │ "Insider"-MCP │
│(Kurse)│   │(Indikatoren,│ │(weltweite│  │ (öffentliche  │
│Twelve │   │ ATR, Level, │ │ Ereig-   │  │  Filings)     │
│ Data  │   │ Größe, R:R) │ │ nisse)   │  │               │
└───────┘   └─────────────┘  └──────────┘  └───────────────┘
```

- **Deterministische Skills rechnen die harten Zahlen** (Indikatoren, ATR, Support/Resistance,
  Positionsgröße, R:R, Korrelation). Diese sind testbar und immer gleich — kein Raten.
- **Claude ist das Gehirn darüber:** Es liest die Zahlen + News + Muster, wendet den Top-Down-
  Workflow (TRADING-WISSEN.md Teil XXI) an, prüft die Vetos und schreibt die begründete
  Empfehlungskarte (Teil XXVI.3).
- **Vorteil:** Präzision der Zahlen + Urteilskraft und Erklärung von Claude. Das Beste aus beidem.

---

## 3. Die Bausteine im Einzelnen

### 3.1 Daten-Skill (Kurse)
- **Quelle:** Twelve Data (Free Tier, 800 Credits/Tag) — Forex-Kerzen in mehreren Zeitebenen.
  Fallback: Finnhub.
- **Funktion:** holt OHLCV für ein Paar über 5m/15m/1h/4h, liefert saubere Kerzendaten an die
  Rechner.

### 3.2 Analyse-Rechner (deterministisch, Python)
Aus TRADING-WISSEN.md abgeleitet, je ein Rechner:
- **Trend/Regime:** EMA-Fächer, ADX, Regime-Klassifikation (Teil V, XXVII, IV.1).
- **Indikatoren:** RSI, MACD, Stochastik, Bollinger, ATR (Teil XXVII).
- **Level:** Support/Resistance, Fib-Golden-Pocket, Pivot Points, Volume-Näherung (Teil IV, XV, XIX).
- **Kerzen/Muster:** kontinuierliche Kerzen-Features + Musterprüfung **nur am Level** (Teil III, XIV).
- **Fehlausbruch-Signatur:** Sweep + Rückschluss + Volumendivergenz (Teil XVI.9, XVIII).
- **Positionsgröße & R:R:** 1 % Kontorisiko, ATR-normiert, Mindest-R:R 1:2 (Teil IX, XXII, XXIX).
- **Korrelation:** rollierende Matrix, Risikobudget-Bündelung (Teil XIII.3).

### 3.3 News-MCP (weltweite Ereignisse)
- **Zweck:** Der Assistent liest weltweite Nachrichten. Geopolitik (z. B. „Krieg gestoppt"),
  Zentralbank-Aussagen, Makrodaten bewegen Forex stark und schnell (Teil XXIV).
- **Einsatz:** (a) **Veto** um Hochimpakt-Ereignisse (NFP/CPI/FOMC → nicht handeln),
  (b) **Kontext** für die Richtung („Risk-on/Risk-off" nach großen Ereignissen).
- **Hinweis zur Session:** MCP-Server, die eine Autorisierung brauchen, verbinden sich **nur in
  deiner interaktiven Claude-Sitzung** (du autorisierst sie einmal). In der automatischen
  Build-Session hier sind sie nicht nutzbar — das ist normal und kein Fehler.

### 3.4 Disclosure-/„Insider"-MCP — mit wichtiger rechtlicher Klarstellung
- **Klarstellung, damit hier nichts schiefgeht:** Auf **echten** Insiderinformationen (material,
  nicht-öffentlich) zu handeln ist **illegal**. Was diese Tools liefern, ist etwas anderes und
  **legal**: **öffentliche Pflichtmeldungen** — z. B. Trades von US-Abgeordneten/Senatoren
  (STOCK-Act-Offenlegung), SEC Form 4 (Insider-Käufe von Vorständen), 13F (institutionelle
  Bestände). Das ist öffentlich verfügbar und darf genutzt werden.
- **Relevanz:** Diese Daten sind **aktienbezogen** (US-Titel). Für EUR/USD-Forex kaum relevant,
  aber wertvoll, sobald wir Aktien/Krypto mit aufnehmen (Marktscope, siehe offene Frage).

### 3.5 Trade-Journal-Skill
- Protokolliert jede Empfehlung + Ergebnis nach dem Schema aus Teil XXX.3 (inkl. MAE/MFE,
  Prozess-Note). Misst, ob die Signale wirklich funktionieren — die Brücke zu Phase B.

---

## 4. Harte Risiko-Regeln (im Code, nicht verhandelbar)

Direkt aus TRADING-WISSEN.md und den Projektgrundsätzen (CLAUDE.md: Risikolimits im Code):

| # | Regel |
|---|---|
| R1 | Risiko pro Trade max. 1 % des (Demo-)Kontos |
| R2 | Tages-Verlust-Limit −3 % → für den Tag keine neuen Empfehlungen |
| R3 | Mindest-R:R 1:2, sonst „kein Trade" |
| R4 | Kein Signal um Hochimpakt-News (< 30 Min) — News-Veto |
| R5 | Kein Signal in dünnen Sitzungen (Asien-Nachmittag, Freitagabend) |
| R6 | Nie Größe nach Verlust erhöhen (kein Martingale/Grid) |
| R7 | Jede Empfehlung hat einen definierten Stop (Invalidierung) |
| R8 | Stop wird aus der Struktur bestimmt, Größe folgt daraus — nie umgekehrt |

---

## 5. Bau-Plan (Sprints für den neuen Chat)

| Sprint | Inhalt | Ergebnis | Stand |
|---|---|---|---|
| **B1** | Projektgerüst; Datenquellen-Anbindung mit Fallback-Ketten; erste Kerzen | Daten fließen | ✅ `metals/sources/` |
| **B2** | Deterministische Rechner (Trend/Regime, Indikatoren, Level, ATR, Größe, R:R) | Zahlen stehen | ✅ `metals/indicators.py`, `levels.py`, `risk.py` |
| **B3** | Kerzen-/Muster- und Fehlausbruch-Erkennung, alles nur am Level | Setups erkannt | ✅ `metals/patterns.py`, `setups.py` (G1–G12) |
| **B4** | Top-Down-Orchestrierung + Empfehlungskarte | Erste echte Empfehlung | ✅ `metals/analyze.py` |
| **B5** | News-Anbindung + News-Veto; Wirtschaftskalender | Kontext + Schutz | ✅ `metals/sources/news.py`, `calendar.py` |
| **B6** | Trade-Journal + wöchentliche Auswertung (Erwartungswert, Prozess-Treue) | Messbarkeit | **offen** |
| **B7** | (optional) Disclosure-MCP, wenn Aktien/Krypto dazukommen | erweiterte Signale | zurückgestellt |

**Anmerkung zu B5:** Statt eines autorisierungspflichtigen MCP-Servers werden RSS-Feeds der
Primärquellen (Fed, EZB) plus GDELT genutzt. Das braucht keinen Schlüssel, keine
Autorisierung und keine Sitzungsbindung — und die Fed veröffentlicht ihre Statements selbst
per RSS, also ist es zugleich die direktere Quelle.

**Wichtig für den neuen Chat:** Zuerst den Branch `claude-trading-skills` als Vorlage ansehen —
vieles (Position-Sizer, Technical-Analyst, Backtest-Expert) ist dort schon implementiert und kann
adaptiert statt neu gebaut werden.

---

## 6. Betriebs-Plan (wie du ihn täglich nutzt)

1. **Broker-Demo offen** (MT5, PuPrime oder später IC Markets) — zum Ausführen der Trades.
2. **Claude-Sitzung öffnen** (Handy/iPad), Projekt geladen.
3. **Fragen:** „Analysiere Gold" oder „Analysiere Silber".
4. Claude liefert die **Empfehlungskarte**: Richtung, Konfidenz, Einstieg, Stop, Ziel, R:R,
   Begründung, Warnungen, Datenqualität — und wie das Setup typischerweise scheitert.
5. **Du entscheidest** und führst den Trade **manuell in MT5** aus.
6. **Journal:** Ergebnis eintragen (Claude hilft dabei).
7. **Wöchentlich:** Auswertung — funktioniert es? (Erwartungswert, Prozess-Treue).

Bester Zeitpunkt: **London/NY-Overlap** — engste Spreads, klarste Bewegungen. Der genaue
UTC-Zeitraum verschiebt sich mit der Sommerzeit und wird im Code berechnet
(`python -m metals check` zeigt die aktuelle Session). News-Tage meiden.

**Vor dem ersten Silber-Trade:** Kontraktgröße in der MT5-Symbolspezifikation prüfen. Sie
beträgt bei den meisten Brokern 5.000 Unzen, bei manchen 1.000 — das ist ein Faktor 5 in der
Positionsgröße (offener Punkt O14).

---

## 7. Was ich ergänzt habe (weil es dem Bot noch fehlte)

- **News-Integration als Veto UND Kontext**, nicht nur als Anzeige — weltweite Ereignisse steuern
  aktiv die Konfidenz.
- **Rechtliche Klarstellung „Insider"** — nur öffentliche Disclosures, kein illegales MNPI-Trading.
- **Hybrid-Architektur** — deterministische Rechner unter Claude, damit die Zahlen testbar bleiben
  und nicht „geraten" werden.
- **Klartrennung Abo vs. API** — damit die Kostenerwartung stimmt (Halbautomat = Abo; Vollautomat
  = API, später).
- **Nutzung des vorhandenen Skills-Repos** als Baukasten statt Neubau.

---

## 8. Bestätigte Roadmap (Nutzer-Entscheidungen)

- **Phase A (jetzt):** **Gold und Silber** (E18, zuvor Forex allgemein), Halbautomat als
  **Chat/Skills-Projekt**. Du klickst die Trades selbst in MT5. Kein echtes Geld,
  PuPrime-Demo.
- **Phase A.5 (optional):** kleines **gehostetes Dashboard** für den Überblick, wenn gewünscht.
- **Phase B (mit Startkapital):** **Vollautomat** 24/7, der möglichst täglich automatisch handelt,
  **plus Website/Dashboard**. Braucht dann Anthropic-API (Claude im Loop) oder einen
  deterministischen Bot — Entscheidung zu Phase-B-Start. Broker für echtes Geld dann festlegen
  (Empfehlung: IC Markets, Tier-1).

## 9. Offene Punkte

- **Kontraktgröße XAGUSD** beim eigenen Broker prüfen (O14) — vor dem ersten Silber-Trade.
- **Twelve-Data-API-Key** (kostenlos) anlegen. Ohne ihn läuft alles über Yahoo/Stooq; mit ihm
  ist die Kerzenqualität besser.
- **Journal-Modul** (Sprint B6) implementieren.
- **Live-Erreichbarkeit** der Endpunkte im interaktiven Chat prüfen: `python -m metals check`.
  In der automatischen Build-Session ist das wegen der Netzwerk-Policy nicht möglich.
- **Setup-Konfidenzen kalibrieren**, sobald 30+ Trades pro Setup im Journal stehen. Bis dahin
  sind es begründete Schätzungen, keine Messwerte.
- Aktien/Krypto-Marktscope erst nach bewährtem Metall-Halbautomaten.
