# Datenquellen des Metall-Assistenten

Stand: 2026-07-26. Vollständiger Katalog aller Quellen, an die der Bot angebunden ist.
Maschinenlesbare Fassung: `metals/sources/registry.py`. Aktuellen Zustand prüfen mit:

```bash
python -m metals sources -v      # alle Quellen mit Details
python -m metals check           # was gerade erreichbar ist und was fehlt
```

## Grundsatz

**Alle sieben Datenkategorien sind ohne einen einzigen API-Schlüssel abgedeckt.** Der
Assistent funktioniert ab dem ersten Tag. Schlüssel verbessern Auflösung und
Zuverlässigkeit, sie sind keine Voraussetzung.

Jede Quelle ist mit einer **Fallback-Kette** verbunden (`metals/sources/http.try_sources`):
Fällt die bevorzugte aus, übernimmt die nächste, und die Empfehlungskarte nennt, welche
tatsächlich geantwortet hat. Ein kostenloses Kontingent, das um 14:00 UTC erschöpft ist,
darf den Assistenten nicht stumm schalten.

---

## 1. Preis- und Kerzendaten

### Twelve Data — bevorzugt
- **URL:** https://api.twelvedata.com
- **Schlüssel:** `TWELVEDATA_API_KEY` (kostenlos registrieren auf twelvedata.com)
- **Liefert:** XAU/USD und XAG/USD Kerzen in allen Zeitebenen, DXY
- **Limit:** 800 Credits/Tag, 8 Anfragen/Minute (kostenlos)
- **Latenz:** Echtzeit
- **Hinweis:** Eine vollständige Multi-Zeitebenen-Analyse beider Metalle kostet etwa 8–10
  Credits. Das Tagesbudget reicht, ist aber nicht unbegrenzt — der Code cached deshalb
  aggressiv (Standard 60 Sekunden).

### Yahoo Finance Chart-Endpoint — Fallback ohne Schlüssel
- **URL:** https://query1.finance.yahoo.com/v8/finance/chart
- **Schlüssel:** keiner
- **Liefert:** GC=F (Gold-Futures), SI=F (Silber-Futures), DX-Y.NYB (Dollarindex),
  GLD/SLV/GDX, ^TNX (Renditen)
- **Latenz:** Echtzeit
- **Vorbehalt:** Inoffiziell und nicht unterstützt. Das Antwortformat hat sich in der
  Vergangenheit geändert und wird das wieder tun. Ausgezeichnet als kostenlose Gegenprobe
  und als Fallback — aber der Assistent darf sich für eine Sizing-Entscheidung nicht allein
  darauf stützen.

### Finnhub
- **URL:** https://finnhub.io/api/v1
- **Schlüssel:** `FINNHUB_API_KEY` (kostenlos)
- **Liefert:** Forex-Kerzen, Marktnachrichten, Wirtschaftskalender, WebSocket
- **Limit:** 60 Anfragen/Minute (kostenlos)
- **Vorbehalt:** Die Metall-Abdeckung läuft über den Forex-Feed, und die genaue
  Symbolschreibweise variiert je nach Venue-Präfix. Symbol einmal auflösen und speichern,
  nicht pro Aufruf raten.

### Stooq — Tagesdaten, kein Schlüssel
- **URL:** https://stooq.com/q/d/l/
- **Liefert:** XAUUSD und XAGUSD Tageshistorie, lange Zeitreihen
- **Vorbehalt:** Nur Tagesauflösung. Gut für Saisonalität und Regime-Arbeit, nutzlos für
  einen Intraday-Einstieg.

### gold-api.com — einfachster Fallback
- **URL:** https://api.gold-api.com/price/XAU
- **Schlüssel:** keiner
- **Liefert:** Spot-Preis Gold und Silber
- **Vorbehalt:** Eine Zahl, keine Historie, kein Bid/Ask. Wertvoll genau deshalb: Es kann
  wenig schiefgehen.

### Alpha Vantage
- **Schlüssel:** `ALPHAVANTAGE_API_KEY` (kostenlos)
- **Limit:** **25 Anfragen pro Tag** — reicht für ein tägliches Briefing und nicht mehr
- **Empfehlung:** Für das aufheben, was es am besten kann (News-Sentiment), nicht für Kerzen.

### GoldAPI.io / MetalpriceAPI
- **Schlüssel:** `GOLDAPI_KEY` / `METALPRICE_API_KEY`
- **Liefert:** Spot mit Bid/Ask, LBMA-AM-Fix-Historie
- **Einsatz:** Als Preis-Gegenprobe gegen den Kerzen-Anbieter.

---

## 2. Makro — die Ebene, die Gold erklärt

### FRED (St. Louis Fed)
- **Mit Schlüssel:** https://api.stlouisfed.org/fred/series/observations (`FRED_API_KEY`)
- **Ohne Schlüssel:** https://fred.stlouisfed.org/graph/fredgraph.csv

| Serie | Bedeutung für Metalle |
|---|---|
| `DFII10` | 10j TIPS-Realrendite — **der wichtigste Einzeltreiber** |
| `DGS10` | 10j Nominalrendite |
| `T10YIE` | 10j Breakeven-Inflation |
| `DTWEXBGS` | breiter handelsgewichteter Dollar (ehrlicher als DXY, das zu 57 % Euro ist) |
| `VIXCLS` | Volatilitätsindex — Safe-Haven-Nachfrage |
| `T10Y2Y` | Zinskurve 10j–2j |
| `FEDFUNDS` | effektiver Leitzins |

- **Latenz:** täglich, mit Veröffentlichungsverzögerung
- **Einordnung:** Setzt die Neigung für die Woche, nicht den Einstieg für die Stunde.

---

## 3. Positionierung

### CFTC Commitments of Traders
- **URL:** https://publicreporting.cftc.gov/resource/6dca-aqww.json
- **Schlüssel:** keiner (Socrata Open Data)
- **Marktcodes:** Gold `088691`, Silber `084691`
- **Liefert:** Commercial-Netto, Managed-Money-Netto, Open Interest
- **Veröffentlichung:** Freitag 15:30 ET — **für den Stand des vorangegangenen Dienstags**
- **Einordnung:** Bei Erscheinen bereits drei Tage alt. Signale brauchen 4–8 Wochen bis zur
  Auflösung. Positionierungs-Extrem auf Wochenhorizont, **niemals** ein Einstiegssignal.

---

## 4. Physischer Markt

### World Gold Council — Goldhub
- **URL:** https://www.gold.org/goldhub/data/gold-etfs-holdings-and-flows
- **Liefert:** globale Gold-ETF-Bestände in Tonnen, regionale Flüsse, Zentralbankkäufe
- **Vorbehalt:** Als Berichte und Downloads veröffentlicht, nicht als dokumentierte API.
  Wochenkontext, kein automatisierter Feed.

### ETF-Proxy (GLD / SLV über Yahoo)
- **Liefert:** Kurs und Volumen als taggleicher Fluss-Näherungswert
- **Vorbehalt:** Volumen ist ein Näherungswert für Fluss, keine Messung davon.

### Minen als Vorlaufindikator (GDX, SIL, HUI)
- **Vorbehalt:** Minen sind zum Metall gehebelt (1 % Gold ≈ 2–4 % Minen), tragen aber
  zusätzlich Aktienmarkt-Beta. Eine GDX-Bewegung während eines Aktienausverkaufs sagt über
  Gold nichts aus.

### Shanghai Gold Exchange Prämie
- **URL:** https://www.sge.com.cn/
- **Vorbehalt:** Erfordert CNY/USD- und Gramm/Unzen-Umrechnung. 15–30 USD Prämie signalisiert
  starke chinesische Nachfrage; über 100 USD lag historisch eher an Blow-off-Tops.

---

## 5. Nachrichten

**Grundsatz: RSS vor News-APIs.** Kein Schlüssel, kein Kontingent, kein Anbieter — und die
Primärquellen (Fed, EZB) veröffentlichen selbst per RSS.

| Feed | URL | Warum |
|---|---|---|
| **Fed Pressemitteilungen** | federalreserve.gov/feeds/press_all.xml | Primärquelle für die Variable, die Gold bepreist |
| **Fed Reden** | federalreserve.gov/feeds/speeches.xml | Ton-Verschiebungen zeigen sich hier vor der Politik |
| **Kitco** | kitco.com/news/category/mining/rss | Metall-spezifische Redaktion |
| **GoldSeek** | news.goldseek.com/newsRSS.xml | Physischer Markt; strukturell bullish, entsprechend gewichten |
| **Mining.com** | mining.com/feed/ | Angebotsseite; bewegt Silber stärker als Gold |
| **EZB** | ecb.europa.eu/rss/press.html | Wirkt über EUR/USD auf den Dollarindex |

### GDELT 2.0
- **URL:** https://api.gdeltproject.org/api/v2/doc/doc
- **Schlüssel:** keiner
- **Liefert:** weltweite Nachrichtenmenge und Tonalität nach Stichwort, sprachübergreifend
- **Einordnung:** Beantwortet „ist irgendwo auf der Welt etwas passiert". Misst
  Berichterstattungsmenge, nicht Marktwirkung — ein Ausschlag ist ein Grund hinzusehen,
  kein Grund zu handeln.
- **Wichtig:** GDELT allein zählt im Code **nicht** als erreichbare Nachrichtenebene. Ein
  Durchlauf, in dem nur GDELT antwortet, hat kein Bild von einem FOMC-Statement.

### Marketaux / NewsAPI
- `MARKETAUX_API_KEY`: 100 Anfragen/Tag, entitäts-getaggt mit Richtungs-Sentiment
- `NEWSAPI_KEY`: **kostenlose Stufe ist 24 Stunden verzögert** — für Handelsentscheidungen
  damit unbrauchbar. Nur der Vollständigkeit halber gelistet und bewusst nachrangig.

---

## 6. Wirtschaftskalender

### Finnhub Economic Calendar
- **URL:** https://finnhub.io/api/v1/calendar/economic (`FINNHUB_API_KEY`)
- **Liefert:** Termine mit Impact-Bewertung, Ist, Prognose, Vorwert
- **Vorbehalt:** Der Kalenderzugriff ist zwischen Tarifstufen gewandert. Bei 403 greift
  automatisch der eingebaute Kalender.

### Eingebauter berechneter Kalender
- **Quelle:** lokal berechnet aus den Veröffentlichungsregeln
- **Deckt ab:** NFP (erster Freitag 08:30 ET), CPI-Fenster (10.–15.), Erstanträge
  (donnerstags 08:30 ET)
- **Ausdrückliche Grenzen** (`StaticCalendar.caveats`):
  - Kennt keine Sondersitzung, keine Terminverschiebung, keinen Shutdown — also genau die
    Fälle, in denen ein Veto am wichtigsten wäre
  - CPI/PPI sind ohne Live-Feed **Fenster**, keine Zeitpunkte
  - Nicht-US-Ereignisse (EZB, BoE, China) fehlen und bewegen Metalle
- **Rolle:** Untergrenze für das News-Veto, kein Ersatz für einen Live-Feed.

---

## 7. Fundamentaldaten

| Quelle | Liefert | Frequenz |
|---|---|---|
| **WGC Gold Demand Trends** | Angebot/Nachfrage nach Segment, Zentralbankkäufe | quartalsweise |
| **Silver Institute World Silver Survey** | Silber-Bilanz, Industrienachfrage nach Sektor | jährlich |
| **LBMA** | offizieller Auktions-Benchmark | täglich (Historie lizenzpflichtig) |

---

## Einrichtung

### Ohne Schlüssel starten
Funktioniert sofort. Alle Kategorien abgedeckt über Yahoo, Stooq, FRED-CSV, CFTC, RSS,
GDELT und den eingebauten Kalender.

### Schlüssel setzen (empfohlene Reihenfolge)

```bash
export TWELVEDATA_API_KEY="..."    # 1. Priorität: saubere Kerzendaten
export FRED_API_KEY="..."          # 2. stabile Makro-Anbindung
export FINNHUB_API_KEY="..."       # 3. Live-Kalender + zweiter Kerzen-Anbieter
```

Dann prüfen:

```bash
python -m metals check
```

Die Ausgabe zeigt aktive Quellen, blockierte Quellen mit der benötigten Umgebungsvariable,
abgedeckte und fehlende Kategorien sowie eine Live-Erreichbarkeitsprüfung.

### Nicht in git

API-Schlüssel gehören **nicht** ins Repository. Sie werden ausschließlich über
Umgebungsvariablen gelesen; es gibt bewusst keine Konfigurationsdatei für sie.

---

## Prioritätslogik

Bei widersprechenden Quellen gilt:

1. **Regulierungs- und Börsendaten** (CFTC, CME, Fed) schlagen alles.
2. **Bezahlte/keyed Anbieter** schlagen inoffizielle Endpunkte.
3. **Zwei unabhängige Preisquellen** werden gegengeprüft (`cross_check`): Weichen sie um
   mehr als 0,5 % ab, wird gewarnt statt gerechnet. Spot und Futures unterscheiden sich
   legitim um die Basis — eine größere Lücke bedeutet meist einen veralteten Feed oder einen
   anderen Kontraktmonat.
4. **Anbieter-Backtests und Prognosen** sind keine Datenquelle. Sie stehen in
   `docs/GOLD-SILBER.md` mit Quellenkennzeichnung und fließen nicht in Entscheidungen ein.
