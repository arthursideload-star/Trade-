# Twelve Data — API-Referenz für dieses Projekt

Quelle: offizielle Dokumentation unter https://twelvedata.com/docs
Stand der Notizen: 2026-07-25. Nur die für den Forex-Assistenten relevanten Teile.

---

## Endpunkt `time_series`

```
GET https://api.twelvedata.com/time_series
```

| Parameter | Wert im Projekt | Bemerkung |
|---|---|---|
| `symbol` | `EUR/USD` | Schrägstrich-Schreibweise, Grossbuchstaben |
| `interval` | `5min`, `15min`, `1h`, `4h` | API-Schreibweise, nicht `5m`/`15m` |
| `outputsize` | `300` | 1–5000. Kostet unabhängig von der Menge **einen** Credit |
| `order` | `ASC` | Ohne diesen Parameter antwortet die API **neueste zuerst** |
| `timezone` | `UTC` | Alle Zeitstempel im Projekt sind UTC |
| `apikey` | aus `TWELVEDATA_API_KEY` | Nie im Code, nie im Commit |

### Erfolgreiche Antwort

```json
{
  "meta": {
    "symbol": "EUR/USD",
    "interval": "15min",
    "currency_base": "Euro",
    "currency_quote": "US Dollar",
    "type": "Physical Currency"
  },
  "values": [
    {
      "datetime": "2026-07-25 14:30:00",
      "open": "1.08420",
      "high": "1.08455",
      "low": "1.08401",
      "close": "1.08447"
    }
  ],
  "status": "ok"
}
```

**Zwei Fallstricke, die im Client abgefangen sind:**

1. **Preise kommen als Zeichenketten**, nicht als Zahlen. Ohne Umwandlung vergleicht man
   Text statt Kursen — `"1.09" < "1.1"` ist als Text wahr, als Zahl falsch.
2. **`volume` fehlt bei Forex** in der Regel ganz. Es gibt kein zentrales Börsenvolumen für
   Devisen. Der Client setzt dann `null`, nicht `0`.

### Fehlerantwort

Kommt mit HTTP 200 und `status: "error"` — ein reiner Statuscode-Check greift also zu kurz.

```json
{ "code": 429, "message": "You have run out of API credits", "status": "error" }
```

| Code | Bedeutung | Reaktion im Client |
|---|---|---|
| 400 | Ungültiger Parameter | `TwelveDataError` |
| 401 | Schlüssel fehlt oder ist falsch | `TwelveDataError` |
| 403 | Nicht im Tarif enthalten | `TwelveDataError` |
| 429 | Limit erreicht | `RateLimitError`, Exit-Code 2 |
| 404 | Symbol unbekannt | `TwelveDataError` |

---

## Limits im kostenlosen Tarif

| Grenze | Wert |
|---|---|
| Credits pro Tag | 800 |
| Abrufe pro Minute | 8 |
| Credit je `time_series`-Abruf | 1 |
| WebSocket | im kostenlosen Tarif nicht enthalten |

**Rechnung für den Betrieb:** Ein Top-Down-Blick auf ein Paar (5m/15m/1h/4h) kostet
4 Credits. 800 Credits pro Tag reichen damit für etwa 200 vollständige Analysen — für einen
Halbautomaten reichlich. Die Minutengrenze von 8 ist die engere Grenze: mehr als zwei Paare
unmittelbar hintereinander laufen dagegen.

Der Cache in `scripts/cache.py` entschärft beides, weil eine wiederholte Analyse desselben
Paars innerhalb der TTL ohne Abruf auskommt.

---

## Handelszeiten

Forex: Sonntag 22:00 bis Freitag 22:00 UTC. Ausserhalb liefert `values` keine neuen Kerzen.
Der Client wirft dann einen Fehler, der die Handelszeiten ausdrücklich nennt — sonst wird ein
geschlossener Markt leicht als Fehlkonfiguration missverstanden.

---

## Bewusst nicht genutzt

| Endpunkt | Grund |
|---|---|
| `/technical_indicators` | Indikatoren werden ab Sprint B2 selbst gerechnet — testbar und nachvollziehbar, statt einer fremden Blackbox |
| `/price` | Der letzte Schlusskurs aus `time_series` genügt; ein zusätzlicher Abruf kostet einen weiteren Credit |
| WebSocket | Nicht im kostenlosen Tarif |

---

## Ausweichquelle

`BOT-PLAN.md` nennt Finnhub als Fallback (60 Abrufe/Minute, kostenlos). Noch nicht angebunden.
Sinnvoll, sobald das Tageslimit im Betrieb tatsächlich zum Engpass wird — die Schnittstelle
`fetch_candles()` bliebe dabei unverändert, nur der Client dahinter käme hinzu.
