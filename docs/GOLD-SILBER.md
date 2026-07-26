# Gold und Silber — Wissensbasis für den Trading-Assistenten

Stand: 2026-07-26. Dieses Dokument ist die inhaltliche Grundlage für den auf Edelmetalle
spezialisierten Assistenten. Es ergänzt `docs/TRADING-WISSEN.md` (allgemeines Trading-Wissen)
um alles, was speziell für **XAU/USD** und **XAG/USD** gilt.

**Umsetzung im Code:** Fast jeder Abschnitt hier hat eine Entsprechung im Python-Paket
`metals/`. Wo das so ist, steht die Datei dabei. Das ist Absicht — Wissen, das nirgends im
Code landet, wird im Eifer des Gefechts nicht angewendet.

## Quellenkennzeichnung

Nach Projektregel werden Zahlen nach Herkunft unterschieden:

| Kennzeichen | Bedeutung |
|---|---|
| **[REG]** | Regulierungs- oder Börsendaten (CFTC, CME, LBMA, Fed/FRED) — belastbar |
| **[INST]** | Branchenverbände und Forschung (World Gold Council, Silver Institute) — belastbar, aber Interessenlage beachten |
| **[BROKER]** | Broker- und Bildungsseiten — Größenordnungen, keine Messwerte |
| **[EIGEN]** | Eigene Herleitung oder Berechnung in diesem Projekt |

Wo eine Zahl aus Broker-Marketing stammt, steht das ausdrücklich dabei. Solche Zahlen werden
im Code nur als Plausibilitätsgrenzen verwendet, nie als Entscheidungsgrundlage.

---

# Teil I — Warum Gold und Silber, und was daran anders ist

## I.1 Der Charakter der beiden Märkte

Gold ist kein Unternehmen. Es hat keine Gewinne, keine Dividende, keinen Cashflow. Damit
fällt die gesamte fundamentale Bewertungslehre weg, die man auf Aktien anwendet. Was übrig
bleibt, ist eine einzige ökonomische Frage:

> **Was kostet es, etwas zu halten, das nichts abwirft?**

Die Antwort auf diese Frage ist der **reale Zins** — Nominalzins minus erwartete Inflation.
Steigt er, wird Gold teurer im Halten und fällt tendenziell. Fällt er, passiert das Gegenteil.
Das ist der Kern. Alles andere — Geopolitik, Zentralbankkäufe, ETF-Flüsse — moduliert diesen
Kern, ersetzt ihn aber nicht.

Silber ist etwas anderes. Etwa die Hälfte bis über 50 % der Silbernachfrage ist industriell
**[INST]** — Photovoltaik, Elektronik, Elektrofahrzeuge. Silber ist damit ein Zwitter: halb
Edelmetall, halb Industriemetall. Das erklärt sein Verhalten:

- Es folgt Gold in die gleiche Richtung, aber weiter (höheres Beta).
- Es reagiert zusätzlich auf Konjunktur und Industrienachfrage, was Gold nicht tut.
- Es hat **keinen** Zentralbank-Käufer als Boden. Wenn Gold von Notenbankkäufen gestützt
  wird, steht Silber ohne dieses Netz da **[BROKER]**.

## I.2 Warum sich diese beiden für einen Assistenten eignen

Die Begründung ist nüchtern und hat Vor- und Nachteile:

**Dafür:**
- **Große, saubere Bewegungen.** Gold bewegt sich normal 60–100 USD pro Unze am Tag,
  an Nachrichtentagen 150–300 **[BROKER]**. Das ist deutlich mehr als bei den meisten
  Währungspaaren und gibt Struktur, die auf dem Chart lesbar ist.
- **Institutionell dominiert.** Zentralbanken, Staatsfonds, Makro-Hedgefonds. Das erzeugt
  klare Spuren an Levels statt Zufallsrauschen.
- **Ein einziger Haupttreiber.** Realzins und Dollar erklären den Großteil der Bewegung.
  Man muss nicht zwanzig Volkswirtschaften verfolgen, sondern eine.
- **Zwei Instrumente, eine Analyse.** Wer Gold verstanden hat, versteht Silber zu 80 %.
  Das Verhältnis der beiden (Teil V) liefert obendrein ein eigenes Signal.

**Dagegen — und das gehört ehrlich dazu:**
- **Dieselbe Volatilität, die Chancen erzeugt, zerstört Konten.** Ein Prozent Kontorisiko
  bei Gold bedeutet bei realistischem Stop eine sehr kleine Position. Wer stattdessen die
  Positionsgröße nimmt, die sich „richtig anfühlt", riskiert schnell 5–10 %.
- **Gold jagt Stops.** Der Markt braucht Liquidität, um sich zu bewegen, und holt sie sich
  dort, wo sie liegt — hinter offensichtlichen Levels. Docht-Bewegungen durch ein Level und
  zurück sind bei Gold nicht die Ausnahme, sondern das Normalverhalten (Teil XI.3).
- **Wochenend-Gaps.** Lücken von 5 USD oder mehr treten in etwa 35 % der Wochen auf, von
  10 USD oder mehr in etwa 18 % **[BROKER]**. Ein Stop schützt gegen ein Gap nicht.
- **Kein „Verfall" der Volatilität.** Anders als bei ruhigen Währungspaaren gibt es keine
  Phase, in der Gold sich beruhigt und man nachlässig werden darf.

## I.3 Der eine Satz, der alles zusammenfasst

> Gold und Silber sind keine schnelleren Währungspaare. Sie sind Instrumente mit dem
> Zwei- bis Fünffachen der üblichen Tagesrange, in denen dieselbe Fehlerquote das
> Zwei- bis Fünffache kostet.

Deshalb sind im Code zusätzlich zu den allgemeinen Regeln R1–R8 sechs metallspezifische
Regeln M1–M6 fest verdrahtet (Teil XV.4).

---

# Teil II — Kontraktspezifikationen und Handelsmechanik

*Code: `metals/specs.py`*

## II.1 Die Pip-Falle — das Wichtigste zuerst

Bei Gold ist das Wort „Pip" **mehrdeutig**, und diese Mehrdeutigkeit ist ein dokumentierter
Weg, eine Position um den Faktor 10 zu groß zu handeln.

| Konvention | 1 „Pip" | Wert pro Standardlot |
|---|---|---|
| Konvention A (verbreitet) | 0,01 USD/oz | 1,00 USD |
| Konvention B (ebenfalls verbreitet) | 0,10 USD/oz | 10,00 USD |

Beide Konventionen finden sich in Broker-Dokumentation und Lehrmaterial. Wer eine Formel
aus Quelle A mit einer Zahl aus Quelle B kombiniert, rechnet um den Faktor 10 falsch.

**Lösung in diesem Projekt:** Es wird **nie in Pips gerechnet.** Die kanonische Einheit ist
durchgehend **USD pro Feinunze**. Die Umrechnung in Lots passiert genau einmal, in
`metals/risk.py`, und nutzt ausschließlich die Kontraktgröße in Unzen.

## II.2 Spot-CFD (was MT5 bei PU Prime / IC Markets quotiert)

| | XAUUSD | XAGUSD |
|---|---|---|
| 1 Standardlot | 100 Feinunzen | **5.000 Feinunzen** (bei manchen Brokern 1.000!) |
| Bewegung 1,00 USD/oz | 100 USD/Lot | 5.000 USD/Lot |
| Kleinste Notierung | 0,01 | 0,001 |
| Spread London/NY (typisch) | 0,15–0,30 USD/oz **[BROKER]** | 0,015–0,030 USD/oz **[BROKER]** |
| Spread bei Rollover/News | 0,50–1,50 USD/oz und mehr **[BROKER]** | entsprechend |

> **Vor dem ersten Trade prüfen:** Die Kontraktgröße von Silber unterscheidet sich zwischen
> Brokern um den Faktor 5. Steht in MT5 unter *Marktübersicht → Rechtsklick auf das Symbol →
> Spezifikation*. Der Code warnt bei jeder Silber-Positionsberechnung ausdrücklich darauf hin.

**PU Prime konkret [BROKER]:** durchschnittlicher Gold-Spread laut Anbieter 3,0 Pips
(Standard-Konto) bzw. 0,8 Pips (Prime-Konto) — in ihrer Zählweise. Kontraktgröße Gold
100 Unzen, kleinste Preisänderung 0,01. Hebel bis 1:1000. Swap-Beispiel des Anbieters:
–4,85 USD für ein Standardlot XAUUSD über Nacht. Diese Zahlen stammen aus Anbieterangaben
und gehören auf der eigenen Plattform überprüft.

## II.3 COMEX-Futures (wo der Preis tatsächlich entsteht)

Auch wer nur CFDs handelt, sollte die Futures kennen — der Spot-Preis wird dort gemacht
**[REG]**:

| Kontrakt | Größe | Tick | Tickwert |
|---|---|---|---|
| GC (Gold) | 100 oz | 0,10 USD/oz | 10 USD |
| MGC (Micro Gold) | 10 oz | 0,10 USD/oz | 1 USD |
| SI (Silber) | 5.000 oz | 0,005 USD/oz | 25 USD |
| SIL (Micro Silber) | 1.000 oz | 0,005 USD/oz | 5 USD |

Initial Margin bei Gold rund 10.000 USD pro Kontrakt **[BROKER/REG]** — genau deshalb ist
der CFD für kleine Konten überhaupt erst zugänglich.

## II.4 Swap, Rollover und der Mittwoch

- **Rollover** findet bei den meisten Brokern zwischen 21:00 und 23:00 UTC statt. In diesem
  Fenster weiten sich Spreads auf ein Vielfaches, die Liquidität dünnt aus **[BROKER]**.
- **Mittwoch** wird der dreifache Swap berechnet, um das Wochenende abzudecken.
- **Konsequenz im Code:** Das Rollover-Fenster ist als `Quality.AVOID` klassifiziert
  (`metals/sessions.py`), Regel R5 blockiert dort jede Empfehlung.

---

# Teil III — Was den Goldpreis bewegt

*Code: `metals/sources/macro.py`*

## III.1 Rangliste der Treiber

Nach Erklärungskraft geordnet:

### 1. Realzinsen (der stärkste Einzeltreiber)

Die 10-jährige TIPS-Rendite (FRED-Serie `DFII10` **[REG]**) ist der direkte Maßstab für die
Opportunitätskosten von Gold.

- Die inverse Beziehung hielt von 2003 bis etwa 2022 sehr stabil, rollierende
  12-Monats-Korrelation im Mittel etwa **–0,73** **[BROKER, unter Bezug auf Marktdaten]**.
- Über längere Zeiträume gemessen liegt sie eher bei **–0,45**.
- Realzinsen unter etwa 1,5 % gelten als unterstützend, unter 0,5 % als deutlich
  unterstützend.

**Wichtig:** Diese Beziehung ist stark, aber nicht mechanisch, und sie hat sich in den
Jahren seit 2022 zeitweise entkoppelt. Genau diese Entkopplung ist selbst ein Signal —
siehe III.4.

### 2. US-Dollar

Gold ist in Dollar notiert. Ein stärkerer Dollar macht es für alle anderen Käufer teurer.

- Langfristige Korrelation DXY↔Gold rund **–0,80 bis –0,85** über 20 Jahre **[BROKER]**.
- World Gold Council nennt je nach Messperiode **–0,5 bis –0,8** **[INST]**.
- Rollierende 60-Tage-Korrelation typisch **–0,70 bis –0,85** **[BROKER]**.
- Im Fed-Straffungszyklus 2022 zeitweise bis **–0,95** — extrem eng, weil ein einziger
  Makrotreiber (die Realzinsrichtung) beides dominierte **[BROKER]**.

**Messmethodik-Hinweis:** DXY besteht zu rund 57 % aus dem Euro. Der breitere handelsgewichtete
Dollarindex (FRED `DTWEXBGS` **[REG]**) ist das ehrlichere Maß und wird im Code bevorzugt.

### 3. Zentralbankkäufe

Struktureller, nicht taktischer Treiber:

- Zentralbanken kauften im ersten Quartal 2026 netto **244 Tonnen** — über dem Vorquartal
  und über dem Fünfjahresschnitt **[INST, World Gold Council]**.
- **89 %** der befragten Reservemanager erwarten, dass die globalen Zentralbankbestände in
  den nächsten 12 Monaten steigen; **45 %** von 76 befragten Zentralbanken planen selbst
  Zukäufe — ein Rekordwert **[INST]**.
- Die People's Bank of China ist der größte Einzelkäufer, Bestand rund **2.322 Tonnen**
  (Stand Mai 2026) **[BROKER, unter Bezug auf offizielle Meldungen]**.

**Handelsrelevanz:** Zentralbankkäufe erzeugen keinen Einstieg. Sie erklären, warum Gold
manchmal steigt, obwohl Realzinsen und Dollar dagegen sprechen — und damit, warum ein
makro-basierter Short nicht funktioniert.

### 4. ETF-Flüsse

- Bestände der Gold-ETFs erreichten mit rund **3.932 Tonnen** einen Monatsend-Rekord,
  AUM rund **526 Mrd. USD** bei Beständen von **4.047 t** zum Ende eines Folgemonats
  **[INST, World Gold Council]**.
- ETF-Flüsse sind eher *bestätigend* als *führend*: Sie zeigen, dass westliche
  Finanzinvestoren einer Bewegung folgen, sie starten sie selten.

### 5. Geopolitik und Risikoneigung

- Gold reagiert positiv auf VIX-Anstiege, der US-Dollar ebenfalls; Bitcoin verhält sich
  dabei wie ein Risiko-Asset, nicht wie ein sicherer Hafen **[akademisch, mehrere Studien
  in Review of Financial Economics / Financial Innovation]**.
- In der Rangfolge der Safe-Haven-Eigenschaft gegenüber dem S&P 500 stehen Yen und
  Schweizer Franken vor Euro und Gold, Bitcoin zuletzt **[akademisch]**.

**Was das praktisch heißt:** Gold ist ein *guter*, nicht der *beste* sichere Hafen. Bei
einem Schock steigt es meist — aber verlässlicher steigen Yen und Franken.

### 6. Inflationserwartung

Die 10-jährige Breakeven-Inflationsrate (FRED `T10YIE` **[REG]**) ist die Differenz zwischen
Nominal- und Realrendite. Sie ist der Grund, warum „Gold als Inflationsschutz" eine wahre,
aber unbrauchbar langsame Aussage ist: Über Jahrzehnte stimmt sie, über Monate nicht.

## III.2 Der Drei-Schichten-Blick

Ein belastbares Gold-Bild braucht drei gleichzeitig laufende Ebenen **[BROKER, deckt sich
mit der Praxis]**:

| Ebene | Horizont | Quelle | Frage |
|---|---|---|---|
| **Makro** | Tage bis Wochen | DXY, Realzinsen, Fed-Erwartung | In welche Richtung lehnen? |
| **Struktur** | Tag | H4/D1-Chart, Levels | Wo sind die Wendepunkte? |
| **Auslöser** | Minuten | M5/M15 an einer Zone | Wann genau einsteigen? |

Der Assistent bildet genau das ab (`metals/analyze.py`): Makro setzt die Neigung, H4/H1 die
Struktur, M15 den Auslöser. Keine Ebene darf die andere überstimmen.

## III.3 Was Gold *nicht* bewegt

Ebenso wichtig:

- **Schmucknachfrage im Wochenrhythmus.** Sie ist real, aber viel zu träge für Trading.
- **Minenproduktion.** Das jährliche Angebot ist winzig gegenüber den oberirdischen
  Beständen. Gold ist ein Bestands-, kein Flussmarkt. (Bei Silber ist das anders — Teil IV.)
- **Einzelne Schlagzeilen ohne Zinsbezug.** Eine Nachricht bewegt Gold, wenn sie die
  Zinserwartung oder die Risikoneigung verändert. Sonst nicht.

## III.4 Wenn die Beziehung bricht — das wertvollste Makrosignal

*Code: `metals/sources/macro.correlation_check`*

Die nützlichste Makro-Beobachtung ist oft, dass die übliche Beziehung **aufgehört hat zu
funktionieren**.

Konkret: Steigen Realzinsen *und* Dollar gleichzeitig — das Lehrbuch-Umfeld gegen Gold — und
Gold hält sich trotzdem, dann kauft etwas außerhalb des Modells. Die üblichen Kandidaten sind
Zentralbanken und geopolitische Nachfrage. In dieser Lage ist der Makro-Short **schwächer**,
als die Zahlen suggerieren, und ein Short-Setup verdient weniger Konfidenz, nicht mehr.

Der Code prüft das und schreibt eine ausdrückliche Warnung in die Empfehlung.

---

# Teil IV — Was den Silberpreis bewegt

## IV.1 Alles von Gold, plus zwei Dinge

Silber teilt Goldes Treiber (Realzins, Dollar, Risikoneigung) und hat zwei eigene:

### Industrienachfrage

Über 50 % der Silbernachfrage ist industriell **[INST]**. Die Wachstumstreiber:

- **Photovoltaik.** Jede Solarzelle enthält Silber. Der Ausbau ist die größte einzelne
  Nachfragequelle der letzten Jahre.
- **Elektronik.** Silber hat die höchste elektrische Leitfähigkeit aller Elemente.
- **Elektrofahrzeuge.** Deutlich mehr Silber pro Fahrzeug als bei Verbrennern.

Konsequenz: Silber reagiert auf Konjunkturdaten und auf Nachrichten aus diesen Branchen —
Gold tut das nicht.

### Strukturelles Angebotsdefizit

2026 ist das **sechste Jahr in Folge** mit einem Defizit **[INST/Branchenberichte]**. Die
Lagerbestände fielen von rund 290 Mio. Unzen Anfang 2024 auf unter 210 Mio. Unzen im Oktober
2025 **[Branchenberichte unter Bezug auf LBMA- und COMEX-Lagerdaten]**.

## IV.2 Die physischen Anspannungssignale

*Code: `metals/sources/registry.py`, Kategorie PHYSICAL*

Diese Signale gibt es bei Silber in einer Schärfe, die Gold nicht kennt:

| Signal | Was es bedeutet | Warnstufe |
|---|---|---|
| **Backwardation** | Spot teurer als Termin — Käufer zahlen Aufpreis für sofortige Lieferung | akute Knappheit |
| **Leihsätze (Lease Rates)** | Kosten, physisches Silber zu leihen. Spitzen bis **39 %** in London wurden 2026 berichtet **[Branchenberichte]** | extrem |
| **Shanghai-Prämie** | SGE-Preis über London. 2026 wurden **12–13 %** berichtet **[Branchenberichte]** | außergewöhnlich hoch |
| **Lagerbestandsabbau** | Lieferbares Metall wird knapp | strukturell |

Bank of America hob die Silberprognose 2026 auf **65 USD** an, unter Verweis auf anhaltende
Backwardation und Leihsatz-Spitzen **[Anbieteranalyse — Prognose, kein Fakt]**.

> **Einordnung, die dazugehört:** Der „Silver Squeeze" ist ein wiederkehrendes Narrativ mit
> einer langen Geschichte enttäuschter Erwartungen. Die Knappheitsdaten sind real und aus
> Börsen- und Verbandsquellen belegbar. Die daraus abgeleiteten Preisprognosen sind es nicht.
> Für den Assistenten heißt das: Knappheitssignale erhöhen die Konfidenz von **Long**-Setups
> bei Silber leicht. Sie sind kein eigenständiger Einstiegsgrund.

## IV.3 Silber vs. Gold — die praktischen Unterschiede

| | Gold | Silber |
|---|---|---|
| Tagesbewegung | ~1 % normal | ~2–3 % bei gleichem Anlass **[BROKER]** |
| Zentralbank-Boden | ja | **nein** |
| Industrienachfrage | vernachlässigbar | über 50 % |
| Spread relativ zur Range | eng | **weiter** |
| Fehlausbrüche | häufig | **häufiger** |
| Liquidität | sehr hoch | deutlich geringer |

**Fazit für die Praxis:** Silber gibt bei gleicher Idee mehr Bewegung — und mehr Möglichkeiten,
vorher ausgestoppt zu werden. Wer Silber handelt, muss die Position kleiner wählen, nicht
größer, obwohl die Versuchung genau umgekehrt ist.

---

# Teil V — Die Gold-Silber-Ratio

*Code: `metals/gsr.py`*

## V.1 Definition und Geschichte

Die Ratio ist Goldpreis geteilt durch Silberpreis: wie viele Unzen Silber eine Unze Gold
kaufen.

| Zeitpunkt | Wert | Kontext |
|---|---|---|
| Langfristmittel | 50–60, teils 65–70 genannt | je nach Messfenster **[Branchenquellen]** |
| Februar 1991 | ~100 | Extrem |
| Juli 2019 | ~93 | Extrem |
| 2020 | **>120** | Rekord |
| April 2025 | ~105 | Extrem |
| Anfang 2026 | ~57 | zurück ins Mittel |

## V.2 Der eigentliche Nutzen: Regime-Erkennung

Das ist der Teil, der wirklich handelbar ist:

| Ratio | Bedeutet | Regime | Folge für Setups |
|---|---|---|---|
| **steigend** | Gold führt | **defensiv** — sichere Häfen, Zentralbanken, Risk-off | Gold-Trendsetups zuverlässiger, Silber-Ausbrüche scheitern öfter |
| **fallend** | Silber führt | **zyklisch** — Industrie, Risikoneigung, Reflation | Silber läuft weiter, gibt aber auch mehr zurück |

Der Assistent nutzt das als **Instrumentenwahl**: Bei gleicher Richtungsmeinung sagt die
Ratio, welches Metall die Meinung mit besserem Verhältnis von Ertrag zu Risiko ausdrückt.

## V.3 Der klassische Ratio-Trade — und warum er hier nicht gehandelt wird

Der Lehrbuch-Trade: Ratio über 80 → Silber kaufen, Gold verkaufen; unter 60 umgekehrt
**[Branchenquellen]**.

**Warum dieses Projekt ihn nicht handelt:**

1. **Der Horizont passt nicht zum Stop.** Die Ratio blieb nach dem 2020-Hoch über ein Jahr
   auf Extremwerten **[Branchenquellen]**. Kein 1-%-Risiko-Stop überlebt das.
2. **Zwei Positionen, zwei Spreads, zwei Swaps.** Bei monatelanger Haltedauer summieren sich
   die Finanzierungskosten zu einem erheblichen Teil des erwarteten Ertrags.
3. **Auf einen Spread lässt sich kein sinnvoller Stop legen,** dessen historische Extreme
   über ein Jahr anhielten.

Der Code nennt genau diese Gründe, wenn die Ratio ein Extrem erreicht — statt den Trade
kommentarlos vorzuschlagen oder ihn stillschweigend zu verschweigen.

## V.4 Positionierungs-Divergenz

*Code: `metals/sources/cot.gold_silver_positioning_divergence`*

Wenn Spekulanten in Gold und Silber gegensätzlich positioniert sind (Perzentil-Abstand über
40), treibt etwas Metallspezifisches — meist Industrie oder ein Angebotsengpass bei Silber.
Dann gilt die Annahme „beide Metalle sind eine Position" nicht mehr, und sie dürfen nicht
gemeinsam gesizet werden.

---

# Teil VI — Sessions, Uhrzeiten und Fixings

*Code: `metals/sessions.py`*

## VI.1 Handelszeiten

Gold und Silber handeln 24 Stunden an 5 Tagen: Sonntag 22:00 UTC bis Freitag 22:00 UTC, mit
täglicher Unterbrechung zwischen 22:00 und 23:00 UTC **[BROKER]**. Die genaue Grenze
unterscheidet sich brokerabhängig um bis zu eine Stunde.

## VI.2 Die Fenster, die zählen

Alle Zeiten in **Ortszeit der jeweiligen Börse** — im Code wird daraus dynamisch UTC
berechnet, weil London und New York ihre Sommerzeit unabhängig voneinander umstellen.

| Fenster | Zeit | Bedeutung für Metalle |
|---|---|---|
| **Asiatische Range** | 00:00 UTC bis London-Open | Dünn. Die hier gebaute Range ist die Liquidität, die London abholt. |
| **London Killzone** | 07:00–10:00 London | Höchste Trefferquote für den Sweep-Reversal (Setup G1). |
| **LBMA-Fixing AM** | ~10:30 London | Institutionelle Orders bündeln sich. Kurze, scharfe Bewegungen. |
| **COMEX-Open** | 08:20 New York | Verlässliches Liquiditäts-Sweep-Fenster, besonders bei Silber. |
| **New York Killzone** | 08:00–11:00 NY | Größte Stundenranges des Tages bei Gold. 08:30 = Datenfenster. |
| **London/NY-Overlap** | 13:00–17:00 London | **Beste Zeit.** Engste Spreads, klarste Struktur. |
| **„Silver Bullet"** | 10:00–11:00 NY | Algorithmischer Fluss bricht hier auffällig oft die Struktur. |
| **LBMA-Fixing PM** | 15:00 London | Der Benchmark, gegen den abgerechnet wird. |
| **COMEX-Settlement** | 13:30 NY | Offizielles Tagessettlement. |
| **Rollover** | 21:00–23:00 UTC | **Nicht handeln.** Spreads vervielfachen sich. |

## VI.3 Die Sommerzeit-Falle

London und New York stellen an unterschiedlichen Tagen um:

- **EU:** letzter Sonntag im März bis letzter Sonntag im Oktober
- **USA:** zweiter Sonntag im März bis erster Sonntag im November

Zwischen diesen Terminen verschiebt sich der Overlap um eine Stunde. Wer die UTC-Zeiten
fest verdrahtet, handelt zweimal jährlich für Wochen im falschen Fenster. Der Code berechnet
die Umstellung selbst (`eu_dst_active`, `us_dst_active` in `metals/sessions.py`) — ohne
tzdata-Abhängigkeit, damit es in jedem Container läuft, und mit Tests auf die
Umstellungstermine.

## VI.4 Wochentage

| Tag | Charakteristik |
|---|---|
| Montag | Wochenend-Gap wird verarbeitet. Dünner, Ausbrüche scheitern öfter. |
| Dienstag | Sauberster Trendtag. Der COT-Stichtag liegt hier. |
| Mittwoch | FOMC-Statements. **Dreifacher Swap** bei Übernachthaltung. |
| Donnerstag | Erstanträge 08:30 NY, EZB-Entscheide. |
| Freitag | NFP am Monatsersten. Ab Nachmittag Positionsglattstellung, danach Gap-Risiko. |

---

# Teil VII — Volatilität und ATR

*Code: `metals/specs.py` (Referenzprofile), `metals/indicators.py` (Messung)*

## VII.1 Größenordnungen

**Diese Werte sind Referenzrahmen [BROKER/EIGEN], keine Messwerte.** Der Code misst ATR
immer aus Live-Kerzen und nutzt die Tabelle nur, um eine implausible Messung zu erkennen.

| Zeitebene | Gold ATR(14) in USD/oz | Silber ATR(14) in USD/oz |
|---|---|---|
| M5 | 0,5 – 3,0 | 0,010 – 0,090 |
| M15 | 1,0 – 6,0 | 0,020 – 0,170 |
| H1 | 2,0 – 12,0 | 0,045 – 0,350 |
| H4 | 5,0 – 30,0 | 0,110 – 0,850 |
| D1 | 12,0 – 80,0 | 0,250 – 2,200 |

Tagesrange Gold: ruhig ~35, normal ~80, Nachrichtentag bis 300 USD/oz **[BROKER]**.

## VII.2 Warum ATR in Prozent das ehrlichere Maß ist

Gold bei 4,00 USD/oz ATR und Silber bei 0,11 USD/oz ATR sehen absolut völlig verschieden
aus — in Prozent des Preises sind sie ähnlich. Alle Regime-Logik im Code arbeitet deshalb mit
`atr_percent` (`metals/indicators.py`), nicht mit absoluten Werten.

Das hat einen zweiten Vorteil: Wenn Gold von 2.000 auf 4.500 USD steigt, veralten absolute
ATR-Tabellen. Prozentwerte nicht.

## VII.3 Volatilität und Positionsgröße

Die praktische Konsequenz, die viele überrascht:

> **Höhere Volatilität heißt kleinere Position, nicht mehr Gewinn.**

Weil der Stop bei höherer Volatilität weiter weg muss (Regel M1: mindestens 1,0 × ATR), und
weil die Positionsgröße aus dem Stop folgt (Regel R8), sinkt die Losgröße genau dann, wenn
der Markt am aufregendsten aussieht. Das ist kein Fehler des Systems, sondern sein Zweck.

---

# Teil VIII — Saisonalität

*Code: `metals/seasonality.py`*

## VIII.1 Vorwarnung

Saisonalität in Metallen ist ein **schwacher, instabiler Effekt auf kleiner Stichprobe.**
50 Jahre Monatsdaten sind 50 Beobachtungen pro Monat. Die veröffentlichten Studien
widersprechen sich: Manche nennen Januar als stärksten Monat, andere September, andere August
— je nach Messfenster **[verschiedene Anbieterquellen]**.

**Gewichtung im Code: 5 %.** Es bricht Gleichstände. Mehr nicht.

## VIII.2 Was die Quellen sagen

**Starke Monate für Gold:**
- Januar: durchweg unter den stärksten. Genannt werden Durchschnitte von +1,6 % bis +1,9 %,
  positive Jahre in etwa 65–70 % der Fälle **[verschiedene Anbieterquellen]**.
- September: in einer 50-Jahres-Auswertung mit +2,1 % der stärkste Monat **[Anbieterquelle]**.
- August, November, Dezember: mild positiv.

**Schwache Monate:**
- März (–0,6 %), Juni (–0,4 %), April (–0,3 %) in derselben 50-Jahres-Auswertung
  **[Anbieterquelle]**.
- Oktober: schwach in den Langfristdaten, obwohl das Narrativ der indischen Festsaison
  Gegenteiliges nahelegt — die physische Nachfrage ist zu diesem Zeitpunkt bereits eingepreist.

**Genannter Saisonzyklus:** Anstieg ab etwa 6. Juli bis zu einem Hoch um den 21. Februar
des Folgejahres, mit durchschnittlichen Gewinnen von 6,96 % bzw. 11,27 % je nach Messung
**[Anbieterquelle]**.

## VIII.3 Die Geschichten dahinter sind haltbarer als die Statistik

- Indische Hochzeits- und Festsaison bündelt physische Nachfrage im Herbst.
- Chinesisches Neujahr zieht Nachfrage in Januar/Februar.
- Westliches Portfolio-Rebalancing im Januar; der „Januar-Effekt" folgt auf steuerbedingte
  Verkäufe im Dezember.
- Sommer ist dünn: Handelsräume unbesetzt, Ranges enger, Ausbrüche scheitern häufiger.

Die letzte Beobachtung ist die praktisch nützlichste: **Von Mitte Juni bis Mitte August
funktionieren Range-Setups besser und Ausbruch-Setups schlechter** — das ist im Code als
`summer_doldrums` abgebildet.

---

# Teil IX — COT-Positionierung

*Code: `metals/sources/cot.py`*

## IX.1 Was der Bericht ist

Die CFTC veröffentlicht wöchentlich den Commitments-of-Traders-Bericht **[REG]**. Er teilt
die Futures-Positionen nach Gruppen auf:

- **Commercials / Producer-Merchant:** Minen, Banken, Verarbeiter. Sichern physische
  Produktion ab, sind deshalb strukturell netto short. **Keine Richtungswette.**
- **Managed Money:** Hedgefonds und CTAs. Das ist die spekulative Positionierung.
- **Open Interest:** Gesamtzahl offener Kontrakte.

## IX.2 Die entscheidende Einschränkung

> **Veröffentlichung: Freitag 15:30 ET — für den Stand des vorangegangenen Dienstags.**

Der Bericht ist bei Erscheinen bereits drei Tage alt und bis zum folgenden Donnerstag eine
Woche. COT-Signale brauchen typischerweise **4–8 Wochen** bis zur Auflösung
**[Branchenquellen]**.

**Das ist kein Einstiegssignal. Es ist eine Neigung über Wochen.** Der Code schreibt das
Alter des Berichts in jede Ausgabe.

## IX.3 Extremwerte

Häufig genannte absolute Schwellen **[Branchenquellen]**:

| Metall | Commercial-Short-Extrem | Managed-Money-Long-Extrem |
|---|---|---|
| Gold | unter –250.000 Kontrakte | über +200.000 Kontrakte |
| Silber | unter –60.000 Kontrakte | über +40.000 Kontrakte |

**Warum der Code trotzdem primär mit Perzentilen arbeitet:** Das Open Interest ist über die
Jahrzehnte gewachsen. Eine Kontraktzahl, die 2010 extrem war, ist heute gewöhnlich. Der Code
bewertet die aktuelle Position deshalb im **Perzentil ihres eigenen Zweijahresbereichs** und
führt die absoluten Schwellen nur als Zusatzbeleg.

## IX.4 Lesart

- **Managed Money über dem 90. Perzentil:** Wer kaufen wollte, hat gekauft. Der Grenzkäufer
  fehlt. Rückschläge werden durch Liquidation verstärkt. → contrarian bearish.
- **Unter dem 10. Perzentil:** Spekulative Positionierung ausgewaschen. Historisch häufiger
  Vorbote von Aufwärtsbewegungen. → contrarian bullish.

---

# Teil X — Korrelationen und Cross-Asset

## X.1 Die Matrix

| Paar | Normale Beziehung | Bemerkung |
|---|---|---|
| Gold ↔ DXY | stark negativ (–0,7 bis –0,85) | der mechanische Zusammenhang **[BROKER/INST]** |
| Gold ↔ Realzins (DFII10) | negativ (–0,45 bis –0,73) | der ökonomische Kern **[BROKER]** |
| Gold ↔ VIX | positiv bei Stress | Safe-Haven-Bid **[akademisch]** |
| Gold ↔ Silber | stark positiv | Silber mit höherem Beta |
| Gold ↔ Bitcoin | instabil | Bitcoin verhält sich bei Stress wie ein Risiko-Asset **[akademisch]** |
| Gold ↔ Aktien | wechselnd | keine stabile Beziehung |
| Silber ↔ Kupfer | positiv | über den Industriekanal |
| Gold ↔ GDX (Minen) | positiv, verstärkt | 1 % Gold ≈ 2–4 % Minen **[Branchenquellen]** |

## X.2 Minen als Frühindikator — mit Vorbehalt

Minenaktien enthalten Erwartungen an künftige Gewinne und laufen dem Metall gelegentlich
voraus **[Branchenquellen]**. Beobachtete Divergenzen — Minen auf Kaufsignal bei
gleichzeitigem Verkaufsdruck im Spot — werden als Vorbote einer Erholung gelesen.

**Der Vorbehalt, der immer dazugehört:** Minen tragen zusätzlich Aktienmarkt-Beta. Eine
GDX-Bewegung während eines allgemeinen Aktienausverkaufs sagt über Gold **nichts** aus.
Der Indikator ist nur bei ruhigem Aktienmarkt lesbar.

## X.3 Wenn Korrelationen brechen

*Code: `metals/sources/macro.correlation_check`*

Eine Gold/Dollar-Korrelation, die ins Positive dreht, ist kein Rauschen. Sie bedeutet meist,
dass ein dritter Faktor beide dominiert. Modelle, die auf der normalen Beziehung aufbauen,
liegen dann falsch — und der Code senkt die Konfidenz makro-basierter Richtungsaussagen
ausdrücklich, statt sie unverändert weiterzugeben.

---

# Teil XI — Technische Struktur bei Metallen

## XI.1 Runde Zahlen

*Code: `metals/levels.round_number_levels`*

Gold respektiert runde Zahlen zuverlässiger als fast jedes andere technische Level. Der
Grund ist banal und robust: Dort liegen tatsächlich Orders. Menschen und Algorithmen
bündeln Aufträge bei Preisen, die man aussprechen kann.

| Metall | Haupt-Raster | Zwischen | Fein |
|---|---|---|---|
| Gold | 100 | 50 | 10 |
| Silber | 5 | 1 | 0,50 |

**Praxis [BROKER, deckt sich mit der Erfahrung]:**
- Am stärksten auf D1 und H4; für den Einstieg auf M15 die Reaktion abwarten.
- **Stops nie exakt auf eine runde Zahl legen.** Empfohlen wird ein Puffer — im Code als
  Regel M6 mit ausdrücklicher Warnung umgesetzt.
- Nach dem dritten Test in einer Session wird ein Level nicht mehr verteidigt, sondern
  akkumuliert. Der Code senkt die Konfidenz des Rejection-Setups G4 in diesem Fall.

## XI.2 Prior-Day- und Session-Levels

Levels, gegen die institutionelle Desks messen und die deshalb als Magnet wirken:

- Vortageshoch / -tief / -schluss
- Vorwochenhoch / -tief
- Hoch und Tief der asiatischen Session
- LBMA-Fixing-Niveaus

## XI.3 Der Docht — das Kernverhalten von Gold

Dies ist der Abschnitt, dessen Missverständnis die meisten Konten kostet.

> **Gold braucht Liquidität, um sich zu bewegen. Liquidität liegt hinter offensichtlichen
> Levels in Form von Stop-Orders. Also holt der Markt sie sich dort ab, bevor er sich
> bewegt.**

Beobachtbare Folgen **[BROKER, konsistent über viele Quellen]**:

- Lange Dochte durch Levels und zurück sind Normalverhalten, nicht Ausnahme.
- Wer den Stop genau am Swing-Tief platziert, finanziert den Einstieg anderer.
- Ein Ausbruch, der nicht *schließt*, ist kein Ausbruch.

**Was daraus im Code folgt:**

1. **Regel M2:** Stop liegt 0,25 × ATR **jenseits** des strukturellen Levels, nie darauf.
2. **Sweep-Erkennung** (`metals/patterns.detect_sweep`) verlangt zwingend den **Schluss
   zurück** innerhalb weniger Kerzen. Ohne Rückschluss ist es ein Ausbruch — der genau
   entgegengesetzte Trade.
3. **Regel M1:** Stop mindestens 1,0 × ATR. Enger ist Rauschen, nicht Risiko.

Der Preis dafür ist eine kleinere Position. Das ist der richtige Preis.

## XI.4 Kerzenmuster bei Metallen

Die üblichen Muster gelten, mit zwei Anpassungen:

**Anpassung 1 — Dochtschwellen relativ zu ATR statt zum Körper.** Eine Gold-Kerze kann
gleichzeitig einen großen Körper *und* einen großen Docht haben und trotzdem eine saubere
Ablehnung sein. Die Regel „Docht muss doppelt so lang sein wie der Körper" feuert bei Gold
ständig. Im Code wird die Dochtlänge gegen ATR gemessen (`metals/patterns.pin_bar`).

**Anpassung 2 — Muster zählen nur an einem Level.** Ein Pin Bar mitten in der Range ist
Rauschen. Derselbe Pin Bar am Vortageshoch ist Information. Jeder Detektor im Code nimmt ein
Level entgegen und **halbiert** die Bewertung, wenn das Muster im freien Raum feuert
(`_level_adjust`).

**Engulfing:** Der Code verlangt den Schluss jenseits des **Extrems** der Vorkerze, nicht
nur jenseits ihres Körpers. Die schwächere Definition feuert bei Metallen zu oft, um
brauchbar zu sein.

**Marubozu:** Bei Gold typischerweise die Signatur einer nachrichtengetriebenen Neubewertung,
nicht von Akkumulation. Wird deshalb als *Momentum* ausgegeben, nicht als Umkehr.

## XI.5 Fair Value Gaps

Drei-Kerzen-Ungleichgewicht: Das Extrem von Kerze 1 und das Gegenextrem von Kerze 3
überlappen nicht. Metalle füllen diese Zonen oft genug, um sie als Einstiegszonen zu nutzen.

**Wichtige Unterscheidung:** Gaps aus Nachrichten-Spikes werden gefüllt *und durchlaufen*
deutlich häufiger als Gaps aus normalem Session-Fluss. Ein Gap, das eine echte Neubewertung
markiert, ist keine Einstiegszone.

## XI.6 Wochenend-Gaps

- Gaps ≥ 5 USD in ~35 % der Wochen, ≥ 10 USD in ~18 % **[BROKER]**.
- Gaps wirken oft als temporärer Support/Resistance und werden häufig gefüllt.
- **Ein Stop schützt nicht gegen ein Gap.** Deshalb Regel M5: Freitag ab 19:00 UTC flat.

---

# Teil XII — Indikator-Einstellungen für Metalle

*Code: `metals/indicators.py`*

## XII.1 RSI

Die Standard-Schwellen 30/70 sind für Gold **zu eng**. Empfohlen werden **25/75** für
volatile Goldmärkte **[BROKER]**; genannt werden auch 20/80. Der gemeinsame Nenner aller
Quellen ist: weiter als der Standard.

- Periode 14 als Basis.
- Kürzere Perioden (7–9) in hoher Volatilität, längere in ruhigen Phasen **[BROKER]**.
- **Divergenz nur an einem HTF-Level handeln.** Divergenz im freien Raum ist bei Metallen
  das teuerste Signal überhaupt — Gold kann eine Divergenz in einem starken Trend wochenlang
  halten. Setup G9 verlangt deshalb zwingend einen Strukturbruch als Bestätigung.

## XII.2 Gleitende Durchschnitte

Aus einer Auswertung über 8.693 Trades **[Anbieterquelle — kein akademischer Backtest, aber
mit offengelegten Zahlen]**:

| System | Zeitebene | Trades | Trefferquote | Profitfaktor | Erwartungswert |
|---|---|---|---|---|---|
| EMA 21/50 | D1 | — | 38,1 % | **1,85** | — |
| EMA 9/21 | D1 | 74 | 32,4 % | 0,96 | negativ |
| EMA 9/21 | H1 | 296 | 37,2 % | 1,18 | +0,115 R |
| RSI Mean Reversion (gefiltert) | — | 10 | — | — | +0,800 R |

**Was daraus zu lernen ist — wichtiger als die Zahlen selbst:**

1. **Langsamere Systeme auf höheren Zeitebenen schlagen schnellere.** 21/50 mit weniger
   Signalen hat höheren Profitfaktor und geringeren Drawdown als 9/21.
2. **Niedrige Trefferquote ist normal und kein Problem.** 38 % Treffer bei Profitfaktor 1,85
   ist ein funktionierendes System. Wer Trefferquote optimiert, zerstört den Erwartungswert.
3. **10 Trades sind keine Stichprobe.** Der beeindruckendste Wert der Tabelle (+0,800 R)
   steht auf 10 Beobachtungen und ist damit statistisch bedeutungslos. Genau so entstehen
   überangepasste Strategien.

Standardeinstellungen im Code: EMA 20/50/200 für die Trendstruktur, EMA 20 auf H1 als
Pullback-Ziel.

## XII.3 ADX

- Über 25: Trend vorhanden → Trendsetups (G3, G10).
- Unter 18: Range → Reversal-Setups (G4, G6, G7).
- Dazwischen: kein klares Regime, nur die stärksten Setups.

## XII.4 Bollinger / Keltner Squeeze

Bänder innerhalb des Keltner-Kanals = Volatilitätskompression. Bei Metallen feuert das
seltener als bei Forex, löst sich aber heftiger auf, weil die Auflösung meist mit einem
Makro-Auslöser zusammenfällt.

**Einstieg erst beim Schluss außerhalb des Bandes**, nicht bei der Berührung. Ein Squeeze
kann sich lösen, drehen und erneut lösen.

## XII.5 Volumen und VWAP

**Ehrlichkeitshinweis:** Spot-Metall-CFD-Feeds liefern **Tick-Volumen**, nicht echtes
gehandeltes Volumen. Tick-Volumen korreliert gut genug mit echtem Volumen, um relativ
brauchbar zu sein — die absolute Zahl ist zwischen Brokern **nicht vergleichbar**.

Daraus folgt im Code: VWAP wird berechnet, wenn Volumen vorliegt, und gibt sonst `None`
zurück statt eines stillschweigend falschen ungewichteten Mittels.

**Volume Profile / POC:** Genannt wird, dass der Point of Control innerhalb von 48 Stunden
in etwa 70 % der Fälle wieder angelaufen wird **[Anbieterquelle — nicht unabhängig
verifizierbar, als Größenordnung behandeln]**.

---

# Teil XIII — Die Setups G1 bis G12

*Code: `metals/setups.py` — Katalog und Detektoren*

Jedes Setup nennt ausdrücklich **wie es scheitert**. Das ist kein schmückendes Beiwerk: Beim
Journal-Review ist die Unterscheidung zwischen „Setup hat nicht funktioniert" und „Setup
falsch ausgeführt" die einzige, die zu einer Verbesserung führt.

## G1 — London Sweep Reversal ★ Kernsetup

**Idee:** Die asiatische Session baut eine enge Range. Stops sammeln sich über dem Hoch und
unter dem Tief. Beim London-Open greift der Markt durch eine Seite, holt die Stops und dreht
dann in die Gegenrichtung für die Session.

Genannt wird eine Häufigkeit von **3–4 erkennbaren Fällen pro Woche** bei Gold, mit den
höchsten Trefferquoten zwischen 02:00 und 05:00 ET **[Anbieterquellen]**. Typische Zielräume
werden mit 150–400 Pips angegeben **[Anbieterquellen — Pip-Konvention dort unklar, deshalb
im Code nicht verwendet]**.

- **Zeitebenen:** Kontext H4/H1, Auslöser M15/M5
- **Einstieg:** Sweep über/unter die asiatische Range, **Schluss zurück** innerhalb von
  drei M15-Kerzen, dann Market Structure Shift abwarten. Einstieg auf dem Retest des
  entstandenen FVG oder Order Blocks — **nicht auf der Sweep-Kerze selbst.**
- **Stop:** 0,25 × ATR(14) M15 jenseits des Sweep-Extrems
- **Ziel:** Gegenseite der asiatischen Range, dann Vortageshoch/-tief
- **Scheitert wenn:** Der Sweep **nicht** zurückschließt — dann war es ein echter Ausbruch
  und der Trend läuft durch das Level. Der Schluss ist die Unterscheidung. Wer vor dem
  Rückschluss einsteigt, macht aus einem guten Setup ein schlechtes.

## G2 — New York Killzone Continuation

**Idee:** London setzt eine Richtung, New York fügt Volumen hinzu und verlängert sie.

- **Einstieg:** Klare London-Richtung. Zwischen 08:00 und 11:00 NY Pullback auf die
  M15-EMA20 in Kombination mit einem Level, dort Ablehnungskerze.
- **Scheitert wenn:** New York London umkehrt statt verlängert — passiert an Datentagen und
  um das 15:00-London-Fixing. Ein Blick in den Kalender vorher entfernt die meisten Verluste.

## G3 — Trend Pullback at Level ★ Kernsetup

Das haltbarste und langweiligste Setup im Buch.

- **Einstieg:** H4-Trend bestätigt durch EMA20 > EMA50 > EMA200 (oder umgekehrt) und
  ADX > 20. Pullback in eine Confluence-Zone mit H1-EMA20 oder EMA50. Ablehnungskerze auf M15.
- **Stop:** 0,25 × ATR(14) H1 jenseits der Zone
- **Scheitert wenn:** Der Pullback ist der Beginn einer Umkehr statt einer Pause. Warnzeichen:
  Der Pullback dauert länger als der vorangegangene Impuls, oder er bricht das vorherige
  Swing-Tief im Aufwärtstrend.

## G4 — Round Number Rejection

- **Einstieg:** Ausgedehnte Bewegung (mindestens 2 × ATR H1 ohne nennenswerten Pullback) in
  ein Hauptlevel. Pin Bar oder Engulfing auf M15 mit Schluss weg vom Level.
- **Stop:** 0,25 × ATR jenseits des Ablehnungsdochts — **nie auf der runden Zahl.**
- **Scheitert wenn:** Ab dem dritten Test in einer Session wird das Level akkumuliert, nicht
  verteidigt. Der Code senkt die Konfidenz dann automatisch.

## G5 — Asian Range Breakout

Der direkte Konkurrent zu G1.

- **Einstieg:** Asiatische Range enger als 0,6 × ihres 20-Tage-Durchschnitts. M15-Schluss
  jenseits der Range mit Volumen über 1,5 × Durchschnitt, **kein** Rückschluss auf der
  Folgekerze.
- **Scheitert wenn:** Es war G1 in Verkleidung. Die Unterscheidung im Voraus ist ehrlich
  gesagt schwer. Das unterscheidende Kriterium ist der Makro-Hintergrund: Ausbrüche halten,
  wenn Realzins und Dollar in Goldes Richtung laufen, und scheitern, wenn nicht. **Ohne
  Makro-Bild jeden Ausbruch als möglichen Sweep behandeln und den Retest abwarten.**

## G6 — Prior Day Extreme Sweep

- **Einstieg:** Preis überschreitet Vortageshoch/-tief, schließt innerhalb von zwei
  H1-Kerzen zurück, MSS auf M15.
- **Scheitert wenn:** An einem Trendtag bricht das Vortagesextrem und kommt nicht zurück.
  Prüfung, ob die letzten drei Tage höhere Hochs machten, filtert die meisten Fälle.

## G7 — Failed Breakout Reversal

- **Einstieg:** Schluss jenseits eines mindestens zweimal gehaltenen Levels, dann Rückschluss
  innerhalb von drei Kerzen. Einstieg auf dem Rückschluss oder dem ersten Retest von innen.
- **Scheitert wenn:** Ein zweiter Bruch in dieselbe Richtung — der hält meist. **Ein
  gescheiterter Ausbruch ist eine Falle, zwei sind ein Trend.**

## G8 — Squeeze Expansion

- **Einstieg:** Squeeze über mindestens sechs H1-Kerzen, dann erster Schluss außerhalb des
  Bollinger-Bandes.
- **Scheitert wenn:** Die erste Ausdehnung geht in die falsche Richtung.

## G9 — Divergence Reversal at HTF Level

- **Einstieg:** RSI-Divergenz gegen den Preis **an einem H4-Level**, bestätigt durch
  Strukturbruch auf H1. Die Level-Bedingung ist nicht optional.
- **Scheitert wenn:** Divergenz besteht fort und der Preis läuft weiter. Deshalb ist der
  Strukturbruch Pflicht, nicht die Divergenz allein.

## G10 — Fair Value Gap Retest

- **Einstieg:** Ungefülltes Gap ≥ 0,2 × ATR in Richtung des H1-Trends. Rückkehr hinein,
  Ablehnungskerze auf M15.
- **Scheitert wenn:** Der Preis füllt und läuft durch — dann war der Impuls eine Liquidation,
  keine Initiierung. Nachrichten-Gaps füllen und durchlaufen deutlich häufiger.

## G11 — Metal Selection by Ratio (Filter, kein Einstieg)

Läuft **vor** jedem anderen Setup und entscheidet, welches Metall die Richtungsmeinung
besser ausdrückt (Teil V.2).

## G12 — Post-News Structure

Kein Nachrichten-Trade, sondern das Gegenteil.

- **Einstieg:** Mindestens 30 Minuten nach der Veröffentlichung warten. Spread muss wieder
  unter 15 % des ATR liegen. Dann Spike-Hoch und -Tief als Levels behandeln und G6 oder G7
  dagegen handeln.
- **Stop:** 0,5 × ATR jenseits des Spike-Extrems — weiter als sonst.
- **Scheitert wenn:** Die Veröffentlichung hat das Metall **wirklich** neu bewertet. Eine
  CPI-Überraschung, die den Realzinspfad verschiebt, ist kein Rauschen zum Ausfaden. Das
  Erkennungsmerkmal: Wenn die Bewegung in der ersten Stunde nicht die Hälfte zurückholt, war
  die Neubewertung echt und dieses Setup greift nicht.

---

# Teil XIV — Nachrichten und Ereignisse

*Code: `metals/sources/calendar.py`, `metals/sources/news.py`*

## XIV.1 Was Gold bewegt

| Ereignis | Typische Reaktion **[BROKER]** |
|---|---|
| **NFP** (1. Freitag, 08:30 ET) | 80–200 Pips bei Überraschung, 40–80 bei erwartetem Wert |
| **CPI** (Mitte des Monats, 08:30 ET) | vergleichbar mit NFP, teils größer — geht direkt in die Realzinsrechnung ein |
| **FOMC** (14:00 ET) | Statement bewegt, die Pressekonferenz 30 Minuten später bewegt oft weiter — und häufig in die Gegenrichtung |
| **PPI / PCE** | kleiner, gleicher Übertragungsweg |
| **Erstanträge** (Do, 08:30 ET) | meist gering, gelegentlich scharf |

Genannt werden auch Bewegungen von 300 bis über 1.000 Pips innerhalb von Stunden an
FOMC-, NFP- und CPI-Tagen **[BROKER]**.

## XIV.2 Warum der Assistent Nachrichten nicht handelt

Zwei Zahlen genügen **[BROKER]**:

1. **Der Spread weitet sich auf 50+ Pips.**
2. **Die erste Spike-Richtung ist in über 40 % der Fälle falsch.**

Ein Trade mit vervielfachten Kosten und einer Trefferquote nahe dem Münzwurf hat keinen
positiven Erwartungswert. Deshalb **Regel R4: 30 Minuten Sperrzeit in beide Richtungen.**

Die verbreitete „15-Minuten-Regel" — nach einer Veröffentlichung 15 Minuten nicht einsteigen
**[BROKER]** — geht in dieselbe Richtung. Der Code verwendet 30 Minuten, weil bei Metallen
die Spread-Normalisierung länger dauert als bei Währungen.

## XIV.3 Nachrichten als Kontext statt als Trade

Was der Assistent stattdessen mit Nachrichten macht:

- **Veto** (Sicherheitsfunktion, versagt geschlossen)
- **Richtungsneigung**: Geopolitische Eskalation stützt Gold, Deeskalation belastet es;
  hawkish belastet, dovish stützt.

## XIV.4 Der eingebaute Kalender und seine Grenzen

Der Code berechnet den Hochimpakt-Kalender aus den Veröffentlichungsregeln (NFP am ersten
Freitag, CPI zwischen dem 10. und 15., Erstanträge donnerstags), damit das Veto auch ohne
API funktioniert.

**Ausdrücklich dokumentierte Grenzen** (`StaticCalendar.caveats`):

- Er kennt keine Sondersitzung, keine Terminverschiebung, keinen Shutdown, der eine
  Veröffentlichung verzögert — also genau die Fälle, in denen ein Veto am wichtigsten wäre.
- CPI und PPI sind ohne Live-Feed **Fenster**, keine Zeitpunkte.
- Nicht-US-Ereignisse (EZB, BoE, China-Daten) sind nicht abgedeckt und bewegen Metalle.

Er ist eine **Untergrenze** für das Veto, kein Ersatz für einen Live-Feed.

## XIV.5 Warum das News-Veto geschlossen versagt

Wenn die Nachrichtenebene nicht erreichbar ist, **blockiert** der Code — er nimmt nicht an,
dass die Luft rein ist. Begründung: Bei Gold blind durch einen CPI-Druck zu handeln ist der
Weg, ein Konto in einer Kerze zu halbieren.

**Nachgeschärft nach einem Testfund:** GDELT allein zählt **nicht** als erreichbare
Nachrichtenebene. GDELT misst weltweite Berichterstattungsmenge, nicht Schlagzeilen der
Quellen, die Geldpolitik führen. Ein Durchlauf, in dem nur GDELT antwortet, hat kein Bild
von einem FOMC-Statement — genau das, was das Veto abfangen soll.

---

# Teil XV — Risikomanagement für Metalle

*Code: `metals/risk.py`*

## XV.1 Die Positionsgrößen-Formel

Kanonische Einheit: **USD pro Feinunze.** Keine Pips.

```
Risikobetrag       = Kontostand × Risikoprozent
Stop-Distanz       = |Einstieg − Stop|                    (USD/oz)
Risiko pro Lot     = Stop-Distanz × Kontraktgröße         (USD)
Lots               = Risikobetrag / Risiko pro Lot        (abrunden!)
```

**Rechenbeispiel Gold:** Konto 10.000 USD, 1 % Risiko = 100 USD. Stop 10 USD/oz.
Risiko pro Lot = 10 × 100 oz = 1.000 USD. → **0,10 Lots.**

**Rechenbeispiel Silber:** Konto 10.000 USD, 1 % = 100 USD. Stop 0,40 USD/oz.
Risiko pro Lot = 0,40 × 5.000 oz = 2.000 USD. → **0,05 Lots.**

**Abrunden ist Pflicht.** Aufrunden überschreitet das Risikolimit — die einzige Richtung,
in die der Fehler niemals gehen darf. Im Code getestet.

## XV.2 Die Kleinkonto-Realität

Ein Beispiel, das der Code ausdrücklich behandelt: Konto 200 USD, Gold, Stop 40 USD/oz.
Risiko pro Lot = 4.000 USD. Bei 1 % Risiko wären das 0,0005 Lots — weit unter der
Mindestgröße 0,01.

**Die richtige Antwort ist Ablehnung, nicht Aufrunden.** Aufrunden auf 0,01 Lots bedeutet
40 USD Risiko auf ein 200-USD-Konto — das Zwanzigfache der Absicht.

> Das ist eine Kontogrößen-Beschränkung, kein Signalproblem. Sie wird nicht dadurch gelöst,
> dass man das Risiko erhöht.

## XV.3 Die allgemeinen Regeln R1–R8

| # | Regel |
|---|---|
| R1 | Risiko pro Trade nie über 1 % des Kontos |
| R2 | Bei –3 % am Tag: Schluss bis zur nächsten Session |
| R3 | Mindest-CRV 1:2, gemessen zum ersten Ziel |
| R4 | Kein Einstieg 30 Minuten um eine Hochimpakt-Veröffentlichung |
| R5 | Kein Einstieg bei Rollover, in tiefer Asien-Zeit, am späten Freitag |
| R6 | Positionsgröße steigt nie nach einem Verlust. Kein Martingale, kein Grid |
| R6b | Höchstens 2 Positionen gleichzeitig |
| R7 | Jeder Trade hat eine definierte Invalidierung, bevor er eingegangen wird |
| R8 | Der Stop kommt aus der Struktur, die Größe folgt daraus — nie umgekehrt |

## XV.4 Die metallspezifischen Regeln M1–M6

Diese existieren, weil Gold und Silber die Annahmen hinter normalen Forex-Risikoregeln brechen.

| # | Regel | Begründung |
|---|---|---|
| **M1** | Stop nie enger als 1,0 × ATR(14) der Einstiegsebene | Enger ist Rauschen. Ein normaler Docht nimmt ihn mit, bevor die Idee sich auflöst. |
| **M2** | Stops liegen 0,25 × ATR **jenseits** des Levels, nie darauf | Der Markt greift durch das Level, um die Stops zu holen (Teil XI.3). |
| **M3** | Kein Einstieg, wenn der Spread über 15 % des ATR liegt | Sonst wird die Kante an den Broker gezahlt. |
| **M4** | Gold und Silber teilen **ein** Risikobudget von 1,5 % | Ihre Korrelation ist hoch genug, dass zwei Positionen eine Position mit Extraschritten sind. |
| **M5** | Freitag ab 19:00 UTC flat | Gaps ≥ 5 USD in ~35 % der Wochen. Ein Stop schützt nicht gegen ein Gap. |
| **M6** | Stops nicht auf runden Zahlen parken | Orderfluss bündelt sich dort, und Metalle greifen hindurch. |

**Warum diese Regeln im Code stehen und nicht in einer Konfigurationsdatei:** Nach
Projektregel (CLAUDE.md) erfordert eine Änderung einen Commit und ein lesbares Diff. Ein
Risikolimit, das man in einer YAML-Datei ändern kann, wird um 15:30 an einem schlechten Tag
geändert.

## XV.5 Die Verlustspirale

Die häufigste Art, ein Metallkonto zu verlieren, ist keine einzelne schlechte Position:

1. Ein Verlust, größer als geplant, weil die Position zu groß war.
2. Der Wunsch, ihn zurückzuholen.
3. Ein Trade außerhalb der Regeln, größer als der letzte.
4. Wiederholen.

Regel R2 (Tagesstopp bei –3 %) existiert genau dafür. Der Code formuliert es beim Auslösen so:

> Diese Regel existiert, weil der Trade, mit dem man einen schlechten Tag zurückholen will,
> derjenige ist, der aus einem schlechten Tag einen schlechten Monat macht.

---

# Teil XVI — Typische Fehler bei Metallen

**Zusammengetragen aus Broker-Bildungsmaterial und Erfahrungsberichten [BROKER]** — die
Übereinstimmung über viele unabhängige Quellen ist hier bemerkenswert hoch:

## XVI.1 Übergröße — der Konto-Killer Nummer eins

Alle Quellen nennen dies zuerst. Gold bewegt sich 20+ USD pro Session; bei hohem Hebel
löscht schon eine kleine Position ein Konto schnell aus.

**Warum es speziell bei Metallen passiert:** Weil dieselbe Positionsgröße, die bei EUR/USD
harmlos wäre, bei Gold das Fünffache riskiert. Wer die Größe „nach Gefühl" wählt, überträgt
Forex-Gewohnheiten auf ein Instrument mit fünffacher Range.

## XVI.2 Zu enge Stops

Der zweithäufigste. Bei Gold wird ein enger Stop nicht durch die Idee widerlegt, sondern
durch das normale Dochtverhalten mitgenommen. → Regel M1.

## XVI.3 Der Ausbruch, der keiner war

Einstieg auf dem Bruch statt auf dem **Schluss** jenseits des Levels. Bei Metallen ist der
Fehlausbruch die Regel, nicht die Ausnahme. → Auf den Kerzenschluss warten.

## XVI.4 Overtrading nach Verlusten

Zeigt sich direkt nach einem Verlust: Anfänger wollen das Geld schnell zurückholen. Der
emotionale Reflex erzeugt größere Verluste. → Regel R2 und R6.

## XVI.5 Nachrichten ignorieren

Ein technisch perfektes Setup 10 Minuten vor CPI ist kein Setup. → Regel R4.

## XVI.6 Handel ohne Stop

Nennen mehrere Quellen ausdrücklich. Bei einem Instrument mit Wochenend-Gaps und
300-USD-Nachrichtentagen ist eine Position ohne Stop keine Position, sondern eine offene
Rechnung. → Regel R7.

## XVI.7 Rollover-Handel

Spreads von 10–15+ Pips im Fenster 21:00–22:30 UTC **[BROKER]**. Ein Scalp, der dort
eingegangen wird, startet mit einem erheblichen Rückstand. → Regel R5.

## XVI.8 Der spezielle Metall-Fehler: Silber wie Gold behandeln

Silber hat die 2–3-fache prozentuale Bewegung, geringere Liquidität, weitere Spreads und
eine bei manchen Brokern um Faktor 5 abweichende Kontraktgröße. Wer die Gold-Routine
unverändert überträgt, riskiert ein Vielfaches der Absicht.

---

# Teil XVII — Physische Marktsignale

## XVII.1 Die Shanghai-Prämie

Differenz zwischen SGE-Preis (in USD/oz umgerechnet) und London/COMEX **[Branchenquellen]**:

| Prämie | Bedeutung |
|---|---|
| 15–30 USD | starke chinesische Nachfrage über dem Importangebot |
| über 30 USD | ungewöhnlich starke Nachfrage oder Importbeschränkungen |
| über 100 USD | historisch am Ende parabolischer Anstiege — eher Blow-off-Top als Startsignal |
| negativ (Discount) | schwächere Nachfrage, lokaler Verkaufsdruck |

**Rechenhinweis:** Erfordert CNY/USD-Umrechnung und Gramm-zu-Unzen-Umrechnung, bevor die
Zahl etwas bedeutet.

## XVII.2 ETF-Bestände

Über den World Gold Council **[INST]** verfügbar. Als **Wochenkontext** zu lesen, nicht als
Feed — die Daten erscheinen als Berichte, nicht als dokumentierte API.

## XVII.3 Backwardation und Leihsätze

Vor allem bei Silber relevant (Teil IV.2). Wenn beides zusammenfällt — Backwardation *und*
erhöhte Leihsätze — signalisiert das akute Anspannung.

---

# Teil XVIII — Datenquellen

Vollständiger Katalog: **`docs/DATENQUELLEN.md`**. Maschinenlesbar in
`metals/sources/registry.py`. Kurzüberblick:

| Kategorie | Ohne Schlüssel nutzbar | Mit kostenlosem Schlüssel |
|---|---|---|
| **Preis** | Yahoo Finance, Stooq, gold-api.com | Twelve Data, Finnhub, GoldAPI, MetalpriceAPI |
| **Makro** | FRED CSV | FRED API |
| **Positionierung** | CFTC Open Data | — |
| **Physisch** | World Gold Council, SGE, GDX/GLD-Proxy | — |
| **Nachrichten** | Fed RSS, EZB RSS, Kitco, GoldSeek, Mining.com, GDELT | Marketaux, Alpha Vantage |
| **Kalender** | eingebauter berechneter Kalender | Finnhub |

**Wichtig:** Alle sieben Kategorien sind **ohne einen einzigen API-Schlüssel** abgedeckt. Der
Assistent funktioniert ab dem ersten Tag; Schlüssel verbessern Qualität und Genauigkeit.

Prüfen mit:

```bash
python -m metals check
```

---

# Teil XIX — Konfidenz-Bewertung

*Code: `metals/analyze.py`*

## XIX.1 Die Schichten

Die Analyse läuft in einer festen Reihenfolge, und **das Veto kommt zuletzt**:

```
1. Kontostand      → R2 kann alles blockieren
2. Session         → R5 kann blockieren
3. Regime          → welche Setups überhaupt zulässig sind
4. Makro           → Richtungsneigung über Tage
5. Ratio           → welches Metall
6. Setups          → welches Muster, mit welcher Basiskonfidenz
7. Ausrichtung     → Makro/Ratio/Saison stimmen zu oder nicht
8. News-Veto       → R4, versagt geschlossen
9. Datenqualität   → Multiplikator, nie über 1,0
10. Sizing         → R1, R3, M1–M6
```

Diese Reihenfolge ist Absicht: **Kein Maß an technischer Confluence darf sich an einer
Nachrichtensperre oder einem Tagesverlustlimit vorbeiargumentieren.**

## XIX.2 Gewichtung

| Komponente | Beitrag |
|---|---|
| Setup-Basiskonfidenz | 0,50–0,70 |
| Level-Stärke / Confluence | ±0,20 |
| Makro-Ausrichtung | +0,08 / −0,12 |
| Nachrichten-Neigung | +0,05 / −0,08 |
| Ratio-Präferenz | −0,05 bei falschem Metall |
| Saisonalität | ±0,05 |
| **Datenqualität** | **Multiplikator 0,35–1,00** |

**Schwelle für eine Handlungsempfehlung: 0,55.** Darunter wird das Setup gezeigt, aber als
nicht handelbar markiert — mit der Begründung, dass ein marginales Setup, wiederholt
genommen, die Kante in Spreadkosten auflöst.

## XIX.3 Datenqualität ist Teil der Aussage

Eine Empfehlung, die auf einem Fallback-Preisfeed ohne Makrodaten und ohne erreichbare
Nachrichtenebene beruht, ist **nicht dasselbe Objekt** wie eine aus dem vollen Stack. Die
Karte sagt das, statt gleich auszusehen. Jede fehlende Ebene senkt die Konfidenz messbar.

---

# Teil XX — Journal und Auswertung

## XX.1 Was protokolliert wird

Pro Empfehlung:

- Zeitstempel, Instrument, Setup-ID, Richtung
- Einstieg, Stop, Ziel, Losgröße, CRV, ATR-Vielfaches
- Konfidenz und ihre Bestandteile
- **Datenqualität** (welche Quellen, welche fehlten)
- Session, Regime, Makro-Neigung, Ratio-Zustand
- Alle Warnungen und Blockaden

Nach dem Trade:

- Ergebnis in **R**, nicht in Euro
- **MAE** (maximaler Gegenlauf) und **MFE** (maximaler Vorlauf)
- **Prozess-Note**: Wurde der Plan befolgt? Getrennt vom Ergebnis.
- Bei Verlust: Welcher `failure_mode` des Setups trat ein?

## XX.2 Warum Prozess-Note und Ergebnis getrennt bleiben

Vier Kombinationen, und nur zwei davon lehren etwas Nützliches:

| | Gewinn | Verlust |
|---|---|---|
| **Plan befolgt** | gut | **normal — kein Handlungsbedarf** |
| **Plan gebrochen** | **gefährlich** — bestärkt schlechtes Verhalten | schlecht, aber lehrreich |

Der gefährlichste Eintrag ist der gewonnene Trade, der gegen die Regeln lief. Wer nur nach
P&L auswertet, sieht ihn nicht.

## XX.3 Kennzahlen

- **Erwartungswert in R** — die einzige Zahl, die zählt
- **Profitfaktor** — Bruttogewinn / Bruttoverlust
- **Trefferquote** — nur zusammen mit dem durchschnittlichen R interpretierbar
- **Maximaler Drawdown** in R und in Prozent
- **Prozess-Treue** in Prozent
- **Erwartungswert pro Setup-ID** — welche G-Setups tragen tatsächlich?
- **Erwartungswert pro Session** — welches Zeitfenster?

## XX.4 Stichprobengröße

**Unter 30 Trades pro Setup sagen die Zahlen nichts.** Die Tabelle in Teil XII.2 enthält
absichtlich eine Zeile mit 10 Trades und dem beeindruckendsten Wert — als Erinnerung daran,
wie überangepasste Strategien aussehen.

Empfohlen wird, jede Strategie über mindestens **30 Trades** auf Demo zu testen, bevor
echtes Kapital eingesetzt wird **[BROKER — und methodisch vernünftig]**.

---

# Teil XXI — Der tägliche Arbeitsablauf

## XXI.1 Vor der Session (5 Minuten)

```bash
python -m metals check          # Was ist erreichbar? Welche Session?
python -m metals ratio          # Welches Regime? Welches Metall?
```

Dazu: Wirtschaftskalender ansehen. Bei NFP, CPI oder FOMC am selben Tag ist die Planung eine
andere.

## XXI.2 Während der Session

```bash
python -m metals analyse XAUUSD --equity 10000
python -m metals analyse XAGUSD --equity 10000
```

Die Empfehlungskarte lesen — **einschließlich des Abschnitts „HOW THIS SETUP FAILS".** Dann
selbst entscheiden und den Trade manuell in MT5 ausführen.

## XXI.3 Wenn die Levels schon feststehen

```bash
python -m metals size XAUUSD --entry 4500 --stop 4488 --target 4536 \
                             --equity 10000 --atr 6
```

Prüft eine eigene Idee gegen alle Regeln, ohne die volle Analyse.

## XXI.4 Nach der Session

Journal-Eintrag mit Ergebnis in R, MAE/MFE und Prozess-Note.

## XXI.5 Wöchentlich

Erwartungswert je Setup, je Session, je Wochentag. Prozess-Treue. Welcher `failure_mode`
trat am häufigsten ein?

---

# Teil XXII — Was dieses System nicht kann

Der Vollständigkeit halber und weil es zur Projektregel „keine Ertragsversprechen" gehört:

1. **Es sagt keine Preise vorher.** Es beschreibt, was da ist, prüft es gegen Regeln und
   nennt eine Wahrscheinlichkeitseinschätzung, die selbst unsicher ist.
2. **Die Setup-Konfidenzen sind kalibrierte Schätzungen, keine gemessenen Trefferquoten.**
   Sie stammen aus Literatur und Plausibilität. Erst das Journal über 30+ Trades pro Setup
   macht daraus Messwerte — und dann sollten die Zahlen im Code angepasst werden.
3. **Es kann keine unbekannten Ereignisse abfangen.** Der berechnete Kalender kennt keine
   Sondersitzung.
4. **Tick-Volumen ist kein Volumen.** Alle volumenbasierten Aussagen sind relativ.
5. **Backtest-Zahlen aus Anbieterquellen sind nicht unabhängig verifiziert.** Sie stehen in
   diesem Dokument mit Quellenkennzeichnung, damit man weiß, worauf man sich stützt.
6. **Der stärkste Filter ist nicht in einer Formel abbildbar:** die Bereitschaft, an den
   meisten Tagen nichts zu tun.

---

# Teil XXIII — Quellenübersicht

## Regulierung und Börsen [REG]
- CFTC Commitments of Traders — publicreporting.cftc.gov
- CME Group Kontraktspezifikationen (GC, MGC, SI, SIL)
- Federal Reserve / FRED (DFII10, DGS10, T10YIE, DTWEXBGS, VIXCLS, T10Y2Y)
- LBMA Preisbenchmarks

## Branchenverbände und Forschung [INST]
- World Gold Council — Goldhub: ETF-Bestände, Zentralbankkäufe, Gold Demand Trends
- The Silver Institute — World Silver Survey
- Akademische Arbeiten zu Safe-Haven-Eigenschaften (Review of Financial Economics,
  Financial Innovation, Cogent Economics & Finance)

## Anbieter- und Bildungsquellen [BROKER]
Für Größenordnungen zu Volatilität, Spreads, Sessions, Setups und typischen Fehlern wurden
zahlreiche Broker- und Trading-Bildungsseiten ausgewertet (u. a. PU Prime Help Center,
Vantage Markets, TMGM, StarTrader, FXNX, Pro-Scalper, Quant Signals, ICT-orientierte
Publikationen). Diese Quellen sind untereinander bemerkenswert konsistent bei
Verhaltensbeschreibungen (Sessions, Dochtverhalten, typische Fehler) und **inkonsistent bei
Zahlen** (Pip-Konventionen, Trefferquoten). Entsprechend wurden Verhaltensbeschreibungen
übernommen und Zahlen nur als Größenordnung geführt.

## Was bewusst nicht übernommen wurde
- Preisprognosen und Kursziele jeder Art
- „Trefferquoten" ohne offengelegte Methodik und Stichprobengröße
- Signalanbieter-Statistiken
- Alles, was einen Ertrag in Aussicht stellt
