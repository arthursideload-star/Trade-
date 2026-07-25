---
name: forex-data
description: Holt Forex-Kerzendaten (OHLC) von Twelve Data fuer die Paare EUR/USD, GBP/USD, USD/JPY, USD/CHF, AUD/USD, EUR/GBP und EUR/JPY in den Zeitebenen 5m, 15m, 1h und 4h. Verwenden, sobald eine Analyse, Empfehlung oder Chartbetrachtung fuer ein Waehrungspaar ansteht, etwa bei "Analysiere EUR/USD", "Wie steht GBP/USD", "Kurse holen" oder wenn Indikatoren, Trend, Level oder Setups berechnet werden sollen. Liefert validierte Kerzen aelteste zuerst als JSON.
---

# Forex-Daten (Twelve Data)

Liefert die Rohdaten, auf denen die gesamte Analyse aufbaut. Dieser Skill holt **nur** Kerzen —
er bewertet nichts. Indikatoren, Level und Signale kommen in den Sprints B2 bis B4.

## Wann dieser Skill greift

Immer wenn ein Waehrungspaar betrachtet werden soll — Analyse, Empfehlung, Trendfrage oder
schlicht "Wie steht EUR/USD". Ohne frische Kerzen darf keine Empfehlung entstehen.

## Voraussetzungen

- Python 3.9+ (nur Standardbibliothek, keine Installation noetig)
- Umgebungsvariable `TWELVEDATA_API_KEY` (kostenloser Schluessel: https://twelvedata.com/pricing)

## Aufruf

```bash
# Eine Zeitebene
python skills/forex-data/scripts/fetch_candles.py --symbol EUR/USD --interval 15min

# Top-Down ueber alle vier Zeitebenen in einem Aufruf (4 Credits)
python skills/forex-data/scripts/fetch_candles.py --symbol EUR/USD --interval 5m,15m,1h,4h

# Lesbare Kurzfassung statt JSON
python skills/forex-data/scripts/fetch_candles.py --symbol EUR/USD --interval 1h --format text

# Cache umgehen, wenn der aktuellste Stand zwingend noetig ist
python skills/forex-data/scripts/fetch_candles.py --symbol EUR/USD --interval 15min --no-cache
```

Schreibweisen werden normalisiert: `EURUSD`, `eur/usd` und `EUR/USD` sind gleichwertig,
ebenso `5m` und `5min`.

## Was die Ausgabe garantiert

Vier Zusagen, auf die sich jede spaetere Rechnung verlassen darf:

| Zusage | Bedeutung |
|---|---|
| **Reihenfolge** | Kerzen immer **aelteste zuerst**. Twelve Data liefert von sich aus neueste zuerst — das wuerde jeden Indikator lautlos umdrehen. Das Feld `order` benennt die Richtung ausdruecklich. |
| **Volumen** | `null`, wenn der Feed keins liefert. Forex hat kein Boersenvolumen. Eine `0` saehe aus wie ein echter Messwert und wuerde OBV oder Volumendurchschnitte verfaelschen. |
| **Menge** | Standard 300 Kerzen, damit ein EMA200 Vorlauf hat. Ein Abruf kostet **eine** Credit-Einheit, unabhaengig von der Menge — eine kleinere Vorgabe spart nichts und bricht spaeter. |
| **Pruefung** | OHLC-Beziehungen und doppelte Zeitstempel werden geprueft. Auffaelligkeiten stehen in `warnings`. |

## Warnungen ernst nehmen

Ist `warnings` nicht leer, sind die Daten fehlerhaft. Dann **keine** Empfehlung ableiten,
sondern die Auffaelligkeit benennen und mit `--no-cache` erneut abrufen.

## Grenzen des kostenlosen Tarifs

- **8 Abrufe pro Minute**, 800 Credits pro Tag. Ein Abruf = ein Credit je Zeitebene.
- Ein vollstaendiger Top-Down-Blick auf ein Paar kostet 4 Credits. Bei mehreren Paaren kurz
  hintereinander die Minutengrenze im Blick behalten.
- Antworten werden zwischengespeichert (TTL abhaengig von der Zeitebene), damit eine
  wiederholte Analyse desselben Paars keine Credits verbraucht.
- Bei Ueberschreitung endet das Skript mit Code 2 und einer eindeutigen Meldung.

## Handelszeiten

Forex handelt von Sonntag 22:00 bis Freitag 22:00 UTC. Ausserhalb dieser Zeiten liefert die
API keine neuen Kerzen — das Skript sagt das ausdruecklich und ist kein Fehler.
Beste Zeit fuer Analysen: London/NY-Overlap, etwa 12–16 Uhr UTC.

## Exit-Codes

| Code | Bedeutung |
|---|---|
| 0 | Daten geliefert |
| 1 | Fehler (falsches Paar, fehlender Schluessel, Netzwerk) |
| 2 | Limit erreicht — eine Minute warten |

## Weiterfuehrend

- `references/twelvedata-api.md` — Endpunkte, Antwortformate, Fehlercodes, Credit-Kosten
- `scripts/twelvedata_client.py` — der Client, einzige Stelle mit API-Zugriff im Projekt
