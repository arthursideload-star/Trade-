# Entwicklungsplan: Trading-Projekt

Status: Phase A — Gold- und Silber-Assistent, Analyse-Engine implementiert
Letzte Aktualisierung: 2026-07-26

> **Aktualisierung 2026-07-26:** Der Marktscope ist auf **Gold (XAU/USD) und Silber
> (XAG/USD)** verengt (Entscheidung E18), und ein eigener **Scalping-Modus** ist dazugekommen
> (E24). Die Zwei-Phasen-Strategie unten gilt unveraendert; nur die gehandelten Instrumente
> haben sich geaendert. Der aktuelle Stand steht in
> [README.md](./README.md), die Fachgrundlagen in
> [docs/GOLD-SILBER.md](./docs/GOLD-SILBER.md) und
> [docs/GOLD-SCALPING.md](./docs/GOLD-SCALPING.md).
>
> Umgesetzt: Datenanbindung, Rechner, Setup-Erkennung (G1-G12 Swing, S1-S6 Scalping),
> Ausstiegsmanagement, Risikoregeln, Backtest-Engine, `/trade`-Command.
> Offen: Journal-Modul, Backtest auf echten historischen Daten.

---

## Zwei-Phasen-Strategie

| Phase | Was | Warum zuerst/danach |
|---|---|---|
| **A** | **Trading-Assistent** — Web-App, die Forex-Charts analysiert und dir Kauf/Verkauf-Empfehlungen gibt. Du handelst manuell auf MT5-Demo. | Lernen, Strategie validieren, kein Kapitalrisiko |
| **B** | **Autonomer Bot** — handelt selbststaendig auf Binance (Krypto-Perpetuals). Basiert auf dem validierten Analyse-Code aus Phase A. | Erst wenn Phase A beweist, dass die Analyse funktioniert |

Phase B uebernimmt die gesamte Analyse-Engine aus Phase A. Der Aufwand ist nicht doppelt,
sondern aufbauend.

---

# Phase A: Trading-Assistent

## A1. Was der Assistent kann

Du oeffnest die Web-App auf dem iPad (oder Handy). Du gibst ein Forex-Paar ein (z.B. EUR/USD).
Der Assistent:

1. **Holt Echtzeit-Daten** direkt von einer Forex-Datenquelle (nicht vom Bildschirm)
2. **Zeigt einen interaktiven Chart** mit Kerzen, Volumen und eingezeichneten Levels
3. **Analysiert gruendlich:**
   - Kerzen-Muster (Hammer, Engulfing, Doji, etc.)
   - Trendrichtung ueber mehrere Zeitebenen (5m, 15m, 1h, 4h)
   - Support/Resistance-Zonen
   - Indikatoren (RSI, MACD, EMA, Bollinger, ADX)
   - Regime: Trend, Seitwaerts oder Volatil
4. **Gibt eine klare Empfehlung:**
   - Richtung: LONG (kaufen) oder SHORT (verkaufen) oder ABWARTEN
   - Konfidenz: 0-100 %
   - Einstiegspreis
   - Stop-Loss (wo du rausgehst bei Verlust)
   - Take-Profit (wo du Gewinn mitnimmst)
   - Risiko/Chance-Verhaeltnis
5. **Erklaert warum** — damit du lernst, nicht nur blind folgst

Du liest die Empfehlung, entscheidest selbst und fuehrst den Trade in MetaTrader 5 aus.

---

## A2. Systemarchitektur

```
┌──────────────────────────────────────────────────────────────┐
│                    WEB-APP (iPad / Handy)                     │
│  Paar-Auswahl · Chart · Analyse-Anzeige · Signal-Karte       │
│  Mobile-first, responsive                                     │
└──────────────────────────┬───────────────────────────────────┘
                           │ HTTP/WebSocket
┌──────────────────────────▼───────────────────────────────────┐
│                    BACKEND (FastAPI)                           │
│  ┌──────────┐  ┌──────────────┐  ┌────────────────────────┐  │
│  │  Data    │  │  Analyse-    │  │  Signal-Generator      │  │
│  │  Service │→ │  Engine      │→ │  (Richtung, Konfidenz, │  │
│  │          │  │              │  │   SL, TP, R:R)         │  │
│  └──────────┘  └──────────────┘  └────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
         │
┌────────▼─────────────────────────────────────────────────────┐
│                    DATENQUELLEN                                │
│  Forex-API (Echtzeit-Kerzen) · Nachrichtenfeeds               │
└──────────────────────────────────────────────────────────────┘
```

---

## A3. Tech-Stack

| Bereich | Wahl | Begruendung |
|---|---|---|
| **Backend** | Python 3.12 + FastAPI | Schnell, async, gutes Oekosystem fuer Datenanalyse |
| **Frontend** | HTML/CSS/JS (vanilla, mobile-first) | Kein Framework noetig fuer MVP, laeuft ueberall |
| **Charts** | Lightweight Charts (TradingView Open Source) | Professionelle Kerzen-Charts, laeuft im Browser |
| **Daten** | Twelve Data API (kostenloser Tier) | 800 Credits/Tag, Echtzeit-Forex, REST + WebSocket |
| **Indikatoren** | pandas-ta | Umfangreiche Indikator-Bibliothek, gut getestet |
| **Datenbank** | SQLite (MVP) → PostgreSQL (spaeter) | Fuer den Anfang reicht SQLite, kein Server noetig |
| **Deployment** | Docker auf VPS oder kostenloser Tier | Ueberall erreichbar, auch vom iPad |

---

## A4. Datenquelle fuer Forex

MetaTrader-5-Demokonten liefern fuer Forex in der Regel **Echtzeitdaten** (kein 15-Minuten-
Delay). Das Delay betrifft Aktienkurse auf kostenlosen Plattformen, nicht Forex bei MT5-Brokern.

Fuer die Web-App brauchen wir eine eigene Datenquelle, unabhaengig von MT5:

| Quelle | Echtzeit | Kostenlos | Limit |
|---|---|---|---|
| **Twelve Data** | Ja | Ja (Free Tier) | 800 Credits/Tag, 8 Calls/Min |
| **Finnhub** | Ja | Ja (Free Tier) | 60 Calls/Min |
| **Alpha Vantage** | Ja | Ja | 25 Calls/Tag (zu wenig) |
| **OANDA API** | Ja | Practice-Konto | Registrierung noetig |

**Gewaehlt: Twelve Data** als primaere Quelle. Grosszuegiger Free Tier, gute Dokumentation,
REST + WebSocket, alle Forex-Paare.

Fallback: Finnhub als zweite Quelle, falls Twelve Data ausfaellt oder das Limit erreicht ist.

---

## A5. Analyse-Engine (Kern — wird in Phase B wiederverwendet)

### Zeitebenen

| Zeitebene | Rolle |
|---|---|
| **5m** | Einstiegs-Timing, kurzfristige Muster |
| **15m** | Primaeres Signal-Zeitfenster |
| **1h** | Trendbestaetigung |
| **4h** | Uebergeordneter Trend, erlaubte Handelsrichtung |

### Indikatoren (minimaler, robuster Satz)

| Kategorie | Indikatoren | Zweck |
|---|---|---|
| **Trend** | EMA 21/55/200, ADX | Richtung und Staerke |
| **Momentum** | RSI(14), MACD(12,26,9), Stochastik | Ueberkauft/ueberverkauft, Divergenzen |
| **Volatilitaet** | ATR(14), Bollinger Bands(20,2) | Bandbreite, Ausbruchserkennung |
| **Volumen** | OBV, Volumen-Durchschnitt | Bestaetigung von Bewegungen |
| **Struktur** | Donchian Channel, Pivot Points | Support/Resistance-Levels |

### Kerzen-Muster

Automatische Erkennung der wichtigsten Muster mit Kontext-Bewertung:

- **Umkehr:** Hammer, Shooting Star, Engulfing, Morning/Evening Star, Doji an Extremen
- **Fortsetzung:** Three White Soldiers, Three Black Crows, Rising/Falling Three Methods
- **Kontext-Regel:** Ein Muster zaehlt nur, wenn es an einem relevanten Level (S/R, EMA,
  Bollinger-Band) auftritt. Isolierte Muster werden nicht gewertet.

### Regime-Erkennung

| Regime | Erkennungskriterien | Konsequenz |
|---|---|---|
| **Aufwaertstrend** | ADX > 25, EMA 21 > 55 > 200 | Nur Long-Signale |
| **Abwaertstrend** | ADX > 25, EMA 21 < 55 < 200 | Nur Short-Signale |
| **Seitwaerts** | ADX < 20, Preis in Bollinger-Range | Vorsicht, Range-Trades moeglich |
| **Volatil** | ATR > 1,5× Durchschnitt | Kleinere Positionen empfehlen |

### Signal-Bewertung

Jeder Faktor liefert einen Score. Das Ensemble bildet eine Gesamtbewertung:

```
Gesamtscore = Σ (Faktor_Score × Gewicht × Regime_Multiplikator)

Faktoren:
  Trend-Ausrichtung (4h/1h/15m)    Gewicht: 30 %
  Momentum-Bestaetigung             Gewicht: 20 %
  Kerzen-Muster am Level            Gewicht: 15 %
  Volumen-Bestaetigung              Gewicht: 15 %
  Support/Resistance-Naehe          Gewicht: 20 %
```

**Ausgabe:**

| Feld | Beispiel |
|---|---|
| Richtung | LONG |
| Konfidenz | 74 % |
| Einstieg | 1.0842 |
| Stop-Loss | 1.0810 (−32 Pips, −0,30 %) |
| Take-Profit | 1.0906 (+64 Pips, +0,59 %) |
| R:R | 1:2,0 |
| Regime | Aufwaertstrend |
| Begruendung | "4h und 1h Trend aufwaerts, 15m Hammer an EMA 55, RSI dreht aus ueberverkauft, Volumen steigt" |

---

## A6. Frontend — Mobile-First Web-App

### Hauptansicht (iPad/Handy)

```
┌────────────────────────────────────────┐
│  [EUR/USD ▼]  [15m ▼]   [Analysieren] │  ← Paar + Zeitebene waehlbar
├────────────────────────────────────────┤
│                                        │
│         Kerzen-Chart                   │  ← Interaktiv, S/R-Linien,
│         (Lightweight Charts)           │     EMA eingezeichnet
│                                        │
├────────────────────────────────────────┤
│  ┌──────────────────────────────────┐  │
│  │  ▲ LONG        Konfidenz: 74 %  │  │  ← Signal-Karte
│  │  Einstieg: 1.0842               │  │     Gruen = Long
│  │  Stop-Loss: 1.0810 (32 Pips)    │  │     Rot = Short
│  │  Take-Profit: 1.0906 (64 Pips)  │  │     Grau = Abwarten
│  │  R:R: 1:2.0                     │  │
│  └──────────────────────────────────┘  │
├────────────────────────────────────────┤
│  Begruendung:                          │
│  4h/1h Trend aufwaerts, 15m Hammer     │  ← Erklaerung, damit du lernst
│  an EMA 55, RSI dreht, Vol. steigt     │
├────────────────────────────────────────┤
│  Indikatoren:                          │
│  RSI: 38 ↑  MACD: bullish cross       │  ← Detail-Bereich
│  ADX: 31    EMA: 21>55>200             │
│  ATR: 12 Pips  Regime: Trend ↑         │
└────────────────────────────────────────┘
```

### Unterstuetzte Forex-Paare (Start)

Die liquidesten Paare mit den engsten Spreads:

| Paar | Typ |
|---|---|
| EUR/USD | Major |
| GBP/USD | Major |
| USD/JPY | Major |
| USD/CHF | Major |
| AUD/USD | Major |
| EUR/GBP | Cross |
| EUR/JPY | Cross |

Erweiterbar, aber zum Start reichen die Majors — dort sind die Spreads am engsten
und die technische Analyse am zuverlaessigsten.

---

## A7. Umsetzungs-Roadmap Phase A

| Sprint | Dauer | Inhalt | Ergebnis |
|---|---|---|---|
| **A1** | 2-3 Tage | Projekt-Setup, FastAPI-Backend, Twelve Data Anbindung, erste Kerzen-Daten | Backend liefert Forex-Daten |
| **A2** | 2-3 Tage | Analyse-Engine: Indikatoren, Regime, Kerzen-Muster, Signal-Generator | Backend liefert Analyse + Signal |
| **A3** | 2-3 Tage | Frontend: Chart (Lightweight Charts), Signal-Anzeige, mobile Layout | Web-App benutzbar auf iPad |
| **A4** | 2-3 Tage | Multi-Timeframe-Analyse, Signal-Ensemble, Begruendungstexte | Vollstaendige Analyse laeuft |
| **A5** | 1 Woche | Trade-Journal (Empfehlung loggen, Ergebnis nachtragen), Performance-Tracking | Messbar, ob die Signale funktionieren |
| **A6** | fortlaufend | Optimierung anhand der Journal-Daten, weitere Paare, Nachrichtenintegration | Kontinuierliche Verbesserung |

**Bauzeit bis zur benutzbaren Web-App: ca. 1,5-2 Wochen.**

---

## A8. Deployment & Zugang

Die Web-App muss vom iPad und Handy erreichbar sein. Optionen:

| Option | Kosten | Vorteil |
|---|---|---|
| **Render.com Free Tier** | 0 € | Reicht fuer MVP, schlaeft nach Inaktivitaet ein |
| **Hetzner VPS** | ~4 €/Monat | Immer an, volle Kontrolle |
| **Railway.app** | Free Tier | Einfaches Deployment |

Fuer den Start reicht ein kostenloser Tier. Sobald die App taeglich genutzt wird,
lohnt sich ein guenstiger VPS.

---

## A9. Was die App NICHT macht

Klare Grenzen, damit keine Missverstaendnisse entstehen:

- **Keine automatischen Orders** — du entscheidest und klickst selbst in MT5
- **Keine Gewinngarantie** — die App gibt Empfehlungen, keine Vorhersagen
- **Kein Bildschirm-Lesen** — die App holt Daten direkt von der Quelle
- **Kein Echtgeld noetig** — funktioniert komplett mit MT5-Demo
- **Kein Martingale/Grid** — Empfehlungen haben immer einen festen Stop-Loss

---

# Phase B: Autonomer Bot (spaeter)

Phase B wird gestartet, wenn:
1. Die Analyse-Engine aus Phase A nachweislich funktioniert (Trade-Journal zeigt positive Ergebnisse)
2. Genug Startkapital vorhanden ist (mindestens 30 €, besser 100-200 €)
3. Du dich mit den Maerkten sicher fuehlst

Phase B uebernimmt die komplette Analyse-Engine und baut darauf auf:
- Automatische Order-Ausfuehrung auf Binance (Krypto-Perpetuals, 1x Hebel)
- 24/7-Betrieb mit Watchdog und Telegram-Steuerung
- Alle Sicherheitsregeln aus dem urspruenglichen Plan (V1-V7)

Die Details fuer Phase B stehen im Git-Verlauf (vorherige Version von PLAN.md)
und werden aktualisiert, wenn Phase B beginnt.

---

## Offene Fragen

| # | Frage | Status |
|---|---|---|
| O1 | Welchen MT5-Broker nutzt du fuer die Demo? (Betrifft Datenqualitaet) | offen |
| O2 | Twelve Data API-Key — muss erstellt werden (kostenlos) | zu klaeren |
| O3 | Wo soll die App deployed werden? (Free Tier reicht zum Start) | offen |
| O4 | Soll Claude-API fuer KI-Analyse integriert werden? (Kostet Geld) | offen |
