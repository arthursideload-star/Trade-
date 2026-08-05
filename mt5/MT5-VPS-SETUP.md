# Der Bot 24/7 auf dem MetaTrader-VPS

Für das **eingebaute Hosting von MetaTrader** (der Reiter *VPS* im Terminal, „MetaTrader VPS
— Amsterdam"). Nicht zu verwechseln mit `VPS-SETUP.md` — das beschreibt einen gemieteten
Linux-Server bei Hostinger und hat mit dieser Seite nichts zu tun.

---

## Wie dieses Hosting funktioniert — und warum das die wichtigste Seite hier ist

Der MT5-VPS ist **kein Rechner, auf den du dich einloggst.** Er ist eine Kopie deines
Terminals, die MetaQuotes für dich laufen lässt. Daraus folgen vier Regeln, und wer sie
nicht kennt, sucht Stunden nach einem Fehler, der keiner ist:

| Regel | Was sie bedeutet |
|---|---|
| **Migriert wird, was gerade läuft** | Nur Charts mit *angehängtem* EA und eingeschaltetem Algo-Handel kommen mit. Ein EA, der nur im Navigator liegt, wird nicht mitgenommen |
| **Migration ist eine Momentaufnahme** | Änderst du danach lokal etwas — anderer EA, andere Einstellung, anderer Zeitrahmen —, **passiert auf dem VPS gar nichts**, bis du erneut migrierst |
| **Der VPS schickt keine Dateien zurück** | Die `GoldHalfScalp.csv`, die der EA schreibt, liegt auf dem VPS und ist von deinem PC aus nicht erreichbar. Wie du trotzdem an die Ergebnisse kommst, steht weiter unten |
| **Ein Konto je VPS** | Du kannst nicht zwei Konten auf demselben VPS laufen lassen |

Deshalb ist die Reihenfolge unten nicht verhandelbar: **erst lokal alles richtig
einstellen, dann migrieren.** Andersherum migrierst du einen Zustand, den du nicht wolltest.

---

## Schritt 0 — Das Demokonto muss groß genug sein

**10 000 USD.** Nicht 1 000 — das ist die Zahl aus der Anleitung für den *anderen* EA, und
der riskiert 1 % je Trade statt 0,25 %, also das Vierfache.

Bei 1 000 USD hat dieser EA 2,50 $ Budget je Trade. Das reicht gemessen für **3 %** seiner
Signale; er würde etwa vier statt hundert Trades am Tag machen und die Zehn-Minuten-Vorgabe
klar verfehlen. Die ganze Tabelle steht in `HALFSCALP-SETUP.md`.

Neues Demokonto: **Datei → Konto eröffnen → MetaQuotes-Demo**, beim Einzahlungsbetrag
10 000 wählen. Kostet nichts.

> Danach musst du den VPS **erneut migrieren** — er hängt am alten Konto, und ein
> Kontowechsel ist genau so eine lokale Änderung, die von allein nicht ankommt.

## Schritt 1 — Den neuen EA lokal installieren

Falls noch nicht geschehen: `mt5/HALFSCALP-SETUP.md`, Schritte 2 und 3. Kurzfassung:

1. **Datei → Datenverzeichnis öffnen** → `MQL5` → `Experts`
2. `GoldHalfScalp.mq5` hineinkopieren
3. MetaEditor (F4) → Datei doppelklicken → **F7**
4. Unten muss `0 errors, 0 warnings` stehen

Danach steht `GoldHalfScalp` im Navigator unter *Experten* — direkt neben
`GoldScalpAssistant`.

## Schritt 2 — Aufräumen, damit nur eine Strategie läuft

In deinem Screenshot lag `GoldScalpAssistant` schon da und der Chart stand auf **M5**.
Beides muss sich ändern:

1. **Jeden Chart schließen, auf dem `GoldScalpAssistant` liegt.** Sonst laufen zwei
   Strategien auf einem Konto und du weißt bei jedem Ergebnis nicht, welcher es war.
2. Einen **XAUUSD**-Chart öffnen und auf **M1** stellen — nicht M5. Der neue EA rechnet
   auf M1.

> Der EA weigert sich auf einem Nicht-Gold-Chart zu starten und meldet das. Auf dem
> falschen *Zeitrahmen* startet er dagegen und rechnet trotzdem auf M1 — er sagt es nur
> ins Log. Stell den Chart trotzdem auf M1, damit du siehst, was er sieht.

## Schritt 3 — Lokal starten und wirklich hinschauen

1. `GoldHalfScalp` aus dem Navigator auf den M1-Chart ziehen
2. Im Dialog Reiter **Allgemein** → Haken bei *Algo-Trading erlauben* → **OK**
3. Oben in der Symbolleiste: **Algo-Handel** muss grün sein

Jetzt steht oben links am Chart:

```
GoldHalfScalp  aktiv  |  Session: PRIME  |  Trades heute: 0/200  |  flach
```

**Warte hier, bis du den ersten Trade gesehen hast.** In einem guten Fenster dauert das im
Schnitt 8–9 Minuten. Das ist der einzige Moment, in dem du einen Fehler noch billig
findest — auf dem VPS siehst du nur noch ein Logfile.

Wenn nach einer halben Stunde in einem PRIME-Fenster nichts passiert: Reiter **Experten**
unten. Der EA schreibt jedes Mal hin, warum er nichts genommen hat. Die Meldungen und was
sie bedeuten stehen in `HALFSCALP-SETUP.md`.

## Schritt 4 — Migrieren

Erst **jetzt**. Im Reiter **VPS**:

1. Punkt bei **„Alles migrieren: Konto, Signal, Charts, Experten, Indikatoren und
   Einstellungen"**
2. **Migrieren** klicken

Nach ein paar Sekunden steht bei *Letzte Migration* das aktuelle Datum.

## Schritt 5 — Nachprüfen, dass der VPS wirklich handelt

Das ist der Schritt, den man weglässt und dann drei Tage später merkt, dass nichts lief.

**Reiter VPS → Unterreiter „Journal".** Das ist das Logbuch des VPS, nicht deines. Dort muss
stehen, dass der EA geladen wurde:

```
GoldHalfScalp ready. reversion, risk 0.25% per trade, ...
```

**Und dann: dein lokales Terminal schließen.** Wirklich schließen. Wenn der VPS richtig
arbeitet, laufen die Trades weiter — das siehst du beim nächsten Öffnen in der
**Kontohistorie**, weil die vom Broker kommt und nicht von deinem PC.

Solange dein Terminal nebenher läuft, kannst du nicht unterscheiden, ob der VPS handelt
oder dein PC.

---

## Wie du an die Ergebnisse kommst

Hier ist die Einschränkung von oben zu spüren: **Die `GoldHalfScalp.csv` liegt auf dem VPS.**
Der EA schreibt sie dort, und du kommst nicht heran.

Was du bekommst — und es reicht:

**1. Die Kontohistorie.** Sie liegt beim Broker, nicht auf dem VPS, und ist in deinem
lokalen Terminal vollständig da. Unten der Reiter **Kontohistorie** → Rechtsklick →
**Bericht** → als Datei speichern.

**2. Das VPS-Journal.** Reiter *VPS* → *Journal*. Dort steht jede Meldung des EA, also auch
jedes „refused: ..." — die Gründe, aus denen er einen Trade *nicht* genommen hat. Die stehen
in der Kontohistorie naturgemäß nicht.

**Und dafür gibt es einen Befehl.** Der Export aus der Kontohistorie lässt sich ins
Journalformat umwandeln, dann läuft die ganze Auswertung wie gewohnt:

```bash
python -m metals import-history Bericht.html --symbol XAUUSD --out vps-trades.csv
python -m metals journal --file vps-trades.csv
```

Und in den Tresor, damit du die Trades kommentieren kannst:

```bash
python -m metals vault --journal vps-trades.csv
```

**Damit das R-Multiple überlebt, schreibt der EA seinen Stop in den Order-Kommentar**
(`HS sl=4098.00`). Das ist kein Schmuck: Ein Deal-Export speichert, was ein Trade
*eingebracht* hat, niemals, was er *riskiert* hat — und jede Erwartungswert-Zahl dieses
Projekts ist in R gerechnet, also Ertrag geteilt durch Risiko. Ohne den Stop hätte kein
einziger Trade ein R und fiele komplett aus der Auswertung.

Kürzt dein Broker die Kommentare (manche tun das), bleibt die Spalte leer statt geraten,
und der Befehl sagt dir, bei wie vielen Trades das passiert ist. Ein erfundener Nenner
sähe aus wie eine echte Zahl und wäre keine.

**Was auch damit fehlt:** die Signalzeilen mit ihren Ablehnungsgründen. Ein abgelehnter
Trade wird nie zu einem Deal, steht also in keinem Broker-Export. Wenn du wissen willst,
welches Gatter wie oft greift, ist das VPS-Journal die einzige Quelle — lesen musst du es
selbst.

> **Der Ausweg, falls dich das stört:** Den EA zusätzlich lokal auf einem *zweiten*
> Demokonto laufen lassen. Dann schreibt die lokale Kopie ihre CSV normal, und du hast beide
> Sichten. Zwei Konten, damit sich die Trades nicht vermischen.

---

## Die Rechnung, die in einem Monat auffällt

In deinem Screenshot:

| | |
|---|---|
| Zahlungsplan | 1 Monat für 15,00 $ mit Verlängerung |
| Auto-Erneuerung | **aktiviert** |
| MQL5-Guthaben | **0,00 USD** |

**Die automatische Verlängerung kann mit 0,00 $ Guthaben nicht ziehen.** Wenn du willst,
dass der VPS weiterläuft, lade das MQL5-Guthaben rechtzeitig auf — sonst steht der Bot in
einem Monat still, und zwar ohne dass dir jemand auf den Chart schreibt.

Das ist keine Vermutung über MetaQuotes' Kulanz, sondern die naheliegende Lesart der beiden
Zeilen nebeneinander. Prüf es zur Sicherheit unter *Extras → Optionen → Community*.

---

## Was du ab jetzt NICHT mehr tun darfst

**Nichts lokal ändern und erwarten, dass es wirkt.** Andere Einstellung, neu kompilierter
EA, anderer Chart — alles das bleibt auf deinem PC, bis du **erneut migrierst**. Das ist der
häufigste Fehler mit diesem Hosting und er sieht von außen aus wie „der Bot ignoriert
meine Einstellung".

**Nicht nebenher XAUUSD von Hand handeln.** Dein Konto ist ein **Hedge**-Konto, also
existieren mehrere Positionen nebeneinander — der EA verwaltet nur seine eigene, erkennt
sie an seiner Magic Number. Deine Handtrades stören ihn nicht direkt, aber sie verfälschen
jede Auswertung, weil die Kontohistorie beides enthält.

**Den lokalen EA nicht parallel laufen lassen.** Sonst handeln zwei Kopien dasselbe Konto
und verdoppeln jedes Risiko.

---

## Wenn etwas nicht stimmt

| Symptom | Ursache |
|---|---|
| VPS-Journal zeigt den EA gar nicht | Beim Migrieren war der EA nicht auf einem Chart oder Algo-Handel war aus. Schritt 3 wiederholen, dann neu migrieren |
| „REFUSED: this EA is built for gold" | Der migrierte Chart war nicht XAUUSD |
| „REFUSED: this is not a demo account" | Echtgeldkonto. Der EA startet dort absichtlich nicht |
| „cannot size: position rounds to ..." | Kontoguthaben zu klein für 0,25 % Risiko bei diesem Stop |
| Stundenlang keine Trades, Journal still | Prüfen, ob das VPS-Journal überhaupt neue Zeilen bekommt. Wenn nicht: Migration hat nichts mitgenommen |
| Alles lief, seit einem Monat nichts | Guthaben. Siehe oben |

Siehe auch: `mt5/HALFSCALP-SETUP.md` (die Strategie selbst) ·
`obsidian/01-Strategie/Die Halbziel-Taktik.md` (was gemessen ist und was nicht)
