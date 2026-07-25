# Bau- und Betriebsplan des Trading-Assistenten

Stand: 2026-07-25. Dieses Dokument ist so geschrieben, dass ein **neuer Chat** direkt danach
bauen kann. Es verfeinert Phase A aus `PLAN.md` mit der Entscheidung, **Claude selbst als Gehirn**
zu nutzen.

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
| **B1** | Projektgerüst als Claude-Code-Skills-Projekt; Twelve-Data-Anbindung; erste Kerzen | Daten fließen | **fertig** — `skills/forex-data/` |
| **B2** | Deterministische Rechner (Trend/Regime, Indikatoren, Level, ATR, Größe, R:R) | Zahlen stehen | **fertig** — `skills/forex-analysis/` |
| **B3** | Kerzen-/Muster- und Fehlausbruch-Erkennung, alles nur am Level | Setups erkannt | **fertig** — `skills/forex-analysis/patterns.py` |
| **B4** | Top-Down-Orchestrierung durch Claude + Empfehlungskarte (Teil XXVI.3) | Erste echte Empfehlung | **fertig** — `skills/forex-signal/` |
| **B5** | News-MCP-Anbindung + News-Veto; Wirtschaftskalender | Kontext + Schutz | offen |
| **B6** | Trade-Journal + wöchentliche Auswertung (Erwartungswert, Prozess-Treue) | Messbarkeit | offen |
| **B7** | (optional) Disclosure-MCP, wenn Aktien/Krypto dazukommen | erweiterte Signale | offen |

**Wichtig für den neuen Chat:** Zuerst den Branch `claude-trading-skills` als Vorlage ansehen —
vieles (Position-Sizer, Technical-Analyst, Backtest-Expert) ist dort schon implementiert und kann
adaptiert statt neu gebaut werden.

**Gefunden in B1:** Der Vorlage-Branch heißt hier `claude/trading-skills-repo-4q0qo9` und enthält
70 Skills. Übernommene Konventionen: `skills/<name>/SKILL.md` mit `scripts/`, `scripts/tests/` und
`references/`; Skripte nur mit Standardbibliothek; JSON nach stdout, Diagnose nach stderr.

**Umgesetzt in B2–B4:** Alle Rechner in reinem Python (kein `ta-lib` — die C-Bibliothek wäre in
der iPad-Sitzung nicht da). Struktur:
- `skills/forex-analysis/` (B2+B3): `indicators.py` (EMA/RSI/MACD/ATR/ADX/Bollinger/Stochastik,
  Wilder-Glättung), `regime.py`, `levels.py`, `patterns.py` (Muster **nur am Level** + Fehlausbruch),
  `position_sizing.py` (R1/R3/R7/R8), `risk_rules.py` (R1–R8 als Gate), `analyze.py` (CLI).
- `skills/forex-signal/` (B4): `signal_score.py` (Gewichte aus PLAN.md A5, Volumen-Gewicht
  umverteilt statt genullt), `recommend.py` (Empfehlungskarte).
- Stop und Ziel kommen aus der Struktur; R:R ist gemessen und kann R3 verletzen.
- R2 (Tagesverlust) und R4 (News) bleiben `need_input`, bis B5 den News-Feed anbindet — bewusst
  **nicht** „ok", damit eine ungeprüfte Regel nie wie eine bestandene aussieht.
- 252 Tests grün.

---

## 6. Betriebs-Plan (wie du ihn täglich nutzt)

1. **Broker-Demo offen** (MT5, PuPrime oder später IC Markets) — zum Ausführen der Trades.
2. **Claude-Sitzung öffnen** (Handy/iPad), Projekt geladen.
3. **Fragen:** „Analysiere EUR/USD" (oder ein anderes Paar).
4. Claude liefert die **Empfehlungskarte**: Richtung, Konfidenz, Einstieg, Stop, Ziel, R:R,
   Begründung, Warnungen.
5. **Du entscheidest** und führst den Trade **manuell in MT5** aus.
6. **Journal:** Ergebnis eintragen (Claude hilft dabei).
7. **Wöchentlich:** Auswertung — funktioniert es? (Erwartungswert, Prozess-Treue).

Bester Zeitpunkt: **London/NY-Overlap (ca. 12–16 Uhr UTC)** — engste Spreads, klarste Bewegungen
(Teil XIII.2). News-Tage meiden (Teil XXIV).

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

- **Phase A (jetzt):** **nur Forex**, Halbautomat als **Chat/Skills-Projekt**. Du klickst die
  Trades selbst in MT5. Kein echtes Geld, PuPrime-Demo.
- **Phase A.5 (optional):** kleines **gehostetes Dashboard** für den Überblick, wenn gewünscht.
- **Phase B (mit Startkapital):** **Vollautomat** 24/7, der möglichst täglich automatisch handelt,
  **plus Website/Dashboard**. Braucht dann Anthropic-API (Claude im Loop) oder einen
  deterministischen Bot — Entscheidung zu Phase-B-Start. Broker für echtes Geld dann festlegen
  (Empfehlung: IC Markets, Tier-1).

## 9. Offene Punkte für den neuen Chat

- ~~Twelve-Data-API-Key (kostenlos) anlegen.~~ Erledigt in B1, liegt in `.env` (nicht im Git).
- Konkrete MCP-Namen/Autorisierung der beiden hinzugefügten Server (News, Disclosure) — in der
  interaktiven Sitzung freigeben.
- Aktien/Krypto-Marktscope erst nach bewährtem Forex-Halbautomaten.
