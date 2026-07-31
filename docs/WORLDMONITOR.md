# World Monitor als Datenquelle

**Stand: 31.07.2026.** Der Bot kann World Monitor als Informationsquelle nutzen.
Diese Seite sagt, was das bringt, was es nicht bringt, und warum die Anbindung
über die Netz-API läuft und nicht über den Quellcode.

---

## Was World Monitor ist

[worldmonitor.app](https://www.worldmonitor.app) von Elie Habib, AGPL-3.0-only. Ein
Echtzeit-Lagebild, das über 65 Anbieter bündelt: Nachrichten, Geopolitik, Finanzmärkte,
Energie, Klima, Lieferketten. Es gibt eine Commodity- und eine Finance-Variante, einen
MCP-Server, eine REST-API und SDKs.

Der vollständige Quellcode liegt in diesem Repository auf dem Branch
`claude/worldmonitor-installation-ehv8dc` — rund 5.055 Dateien.

---

## Warum die API und nicht der Quellcode

Der Bot spricht mit `https://api.worldmonitor.app` (`metals/sources/worldmonitor.py`,
reine Standardbibliothek über `metals/sources/http.py`). Aus dem eingecheckten Baum wird
**nichts** importiert. Drei Gründe, und alle drei sind nachprüfbar:

1. **Es läuft nicht.** World Monitor ist eine TypeScript-Anwendung auf Vercel und Convex.
   In diesem Python-Paket lässt sich davon keine Zeile ausführen. Das Paket kommt ohne
   Installation aus, und dabei bleibt es.
2. **Die Lizenz.** AGPL-3.0 greift auf ein *verbundenes Werk*. Ein Aufruf einer
   öffentlichen HTTP-API über das Netz erzeugt kein solches; Quellcode einbinden und
   dagegen linken würde eine Frage aufwerfen, die dieses Projekt nicht braucht.
3. **5.055 Dateien einer Web-App in einem Handels-Repository** sind genau das, wonach
   `docs/REPO-AUDIT.md` sucht.

Der Branch bleibt bestehen. Es geht nichts verloren — er wird nur nicht in den
Arbeitsbranch gezogen.

---

## Was der Bot davon hat — und was nicht

Das ist der wichtigere Teil. World Monitor sieht so aus, als könnte es den Papier-Lauf
speisen: Es hat einen Goldkurs und einen Wirtschaftskalender, also fast alles, was eine
Sitzung braucht. **Es kann es nicht.**

| Was eine Sitzung braucht | Liefert World Monitor? |
|---|---|
| Goldkurs | Ja — aber `GC=F`, der Frontmonat-Future, nicht Spot |
| **Spread (Ask − Bid)** | **Nein.** Der Quote hat weder Bid noch Ask |
| **Tageshoch / Tagestief** | **Nein.** Nur Preis und Veränderung, kein OHLC |
| Intraday-Historie | Nein |
| **Sperrzeiten für R4** | **Nein.** Der Kalender ist auf den *Tag* datiert, ohne Uhrzeit |
| Welche Tage eine Veröffentlichung tragen | Ja — und das ist der nützliche Teil |
| COT-Positionierung | Ja, doppelt zu `metals/sources/cot.py` |
| EUR/USD-Referenzkurs | Ja — und das ist die eine Zahl, die die Kette bisher annimmt |

Die beiden fett markierten Lücken sind die entscheidenden:

- **Kein Spread.** Auditbefund [A19](./REPO-AUDIT.md) hat gemessen, dass der Spread in
  einer Tagessitzung über das *Vorzeichen* des Erwartungswerts entscheidet: +0,1141 R bei
  0,34 $/oz gegen −0,0647 R bei 1,04 $. Eine Quelle ohne Bid/Ask kann diese Zahl nicht
  liefern, und geraten wird sie seit A19 nicht mehr.
- **Kein Tageshoch/-tief.** Die Tagesspanne *ist* die Strategie.

Deshalb steht in `metals/sources/worldmonitor.py` eine Funktion namens
`cannot_run_a_session()`. Sie gibt einen Satz zurück, und sie steht dort für den Fall,
dass jemand — inklusive mir in einem halben Jahr — auf die naheliegende Idee kommt.

Der Fehlermodus wäre nämlich kein Absturz: Die Antwort lässt sich sauber auswerten und
ergibt einen völlig plausiblen Preis. Man würde es erst merken, wenn der Spread längst
erfunden ist.

---

## Was tatsächlich nutzbar ist

**1. „Ist heute ein CPI-Tag?"** `high_impact_days()` liefert die Tage, die eine
hochwirksame Veröffentlichung tragen. Gröber als R4 — R4 braucht eine Minute, das hier
kennt einen Tag. Beantwortet nicht „jetzt aussteigen", sondern „sollte diese Sitzung
überhaupt laufen".

**2. Der EUR/USD-Referenzkurs.** Die gesamte Papier-Kette rechnet Dollar-Ergebnisse mit
einer **Konstanten von 1,08** in Euro um (`ASSUMED_EUR_USD`). Jede Euro-Zahl im Journal
hängt daran. `get-ecb-fx-rates` könnte die Konstante durch eine Ablesung ersetzen.

**3. Zweitmeinung bei COT und FRED.** Wenn die Primärquelle ausfällt.

---

## Zugang

Die REST-API braucht einen Schlüssel — es gibt **keine** anonyme Stufe:

```bash
export WORLDMONITOR_API_KEY=wm_xxx      # von worldmonitor.app/pro
python -m metals check                  # zeigt, ob er erkannt wird
```

`tools/list` des MCP-Servers ist ohne Schlüssel abrufbar, `tools/call` nicht.

---

## Was hier nicht geprüft werden konnte

**Kein einziger Aufruf in `metals/sources/worldmonitor.py` ist gegen den echten Dienst
gelaufen.** Der Container, in dem er entstanden ist, erreicht `worldmonitor.app` nicht —
der Proxy antwortet mit 403, wie bei jeder anderen Kursquelle auch:

```
curl https://worldmonitor.app/openapi.yaml
curl: (56) CONNECT tunnel failed, response 403
```

Geschrieben ist die Auswertung gegen die veröffentlichten OpenAPI-Schemata und gegen den
Handler-Quellcode im eingecheckten Baum. Getestet ist sie offline gegen nachgebaute
Antwortformen (`tests/test_worldmonitor.py`, 23 Tests).

**Der erste echte Aufruf ist der eigentliche Test.** Und das Wahrscheinlichste, was dabei
schiefgeht, sind Feldnamen. Besonders bei `get-ecb-fx-rates`: Dessen Antwortform ließ sich
aus dem OpenAPI-Beispiel nicht festnageln, deshalb sucht `_find_usd_rate()` den Kurs
absichtlich in mehreren möglichen Strukturen. Ein falscher Wechselkurs würde jede
Euro-Zahl im Journal stillschweigend umskalieren.

---

## Ein Fehler in den übernommenen Daten

Beim Einbau ist ein falsches Datum aufgefallen, und es ist erwähnenswert, weil es zeigt,
wie man mit übernommenen Daten umgehen sollte.

Worldmonitors Kalender-Seeder (`scripts/seed-economic-calendar.mjs`) führt eine
Rückfallliste der EZB-Sitzungstermine. Der erste Eintrag für 2026 ist der **30.01.2026**.
Das ist ein **Freitag** — der EZB-Rat verkündet donnerstags. Der tatsächliche erste
Zinsentscheid 2026 war der **05.02.2026** (EZB-Pressemitteilung `ecb.mp260205`).

Gefunden hat das kein Mensch, sondern ein Test, der auf jedem Datum der Liste den
Wochentag prüft. Der Test bleibt drin. Übernommene Daten werden hier gegen eine
Eigenschaft geprüft, die sie erfüllen müssen — nicht deshalb geglaubt, weil sie aus einem
gepflegten Projekt stammen.

Siehe [REPO-AUDIT.md, A20](./REPO-AUDIT.md).
