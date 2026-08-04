# Bot am eigenen PC — der einfache Weg

Das hier ist die Anleitung für **Windows-PC oder Laptop**. Sie ist kurz, weil der Weg kurz
ist: rund **15 Minuten**, davon 10 Minuten Warten auf Downloads.

Kein VPS. Keine Miete. Kein Container, kein KasmVNC, kein `CUSTOM_USER`-Rätsel.

> **Wenn du von der VPS-Anleitung kommst:** Ja, das ist wirklich alles. Der komplizierte Weg
> in [VPS-SETUP.md](./VPS-SETUP.md) existiert nur für den Fall, dass der Bot laufen soll,
> **während der Rechner aus ist**. Solange du testest, brauchst du das nicht.

---

## Zuerst: ein Doppelklick, und du weißt, ob sich der Rest lohnt

Bevor du MetaTrader auch nur herunterlädst, beantworte die Frage, die alles andere
entscheidet: **Funktioniert die Strategie auf echten Golddaten überhaupt?**

Der Grund, warum das zuerst kommt, steht in [REPO-AUDIT.md, A27](../docs/REPO-AUDIT.md).
Kurz: Alles bisher Gemessene lief auf einem Marktsimulator, und der gemessene Vorteil ist
im Wesentlichen die Ablesung **eines einzelnen Parameters dieses Simulators** — einer
Rechenschutzplanke, die verhindern soll, dass erzeugte Kurse ins Absurde laufen. Setzt man
sie auf null, ist die Kante weg. Der Simulator kann die Frage also nicht beantworten.
Deine heruntergeladene Datei kann es.

### Drei Schritte

**1. Das Projekt holen.** Grüner Knopf *Code* → *Download ZIP* auf
`github.com/arthursideload-star/Trade-`, entpacken. Oder, wenn Git da ist:

```
git clone https://github.com/arthursideload-star/Trade-.git
```

**2. Die Golddatei holen.** Kaggle → *„XAU/USD Gold Price Historical Data"* von
`novandraanugrah` → `XAU_5m_data.csv`. Kostenlos, 5-Minuten-Kerzen ab 2004. Die Datei in
denselben Ordner legen wie `START-WINDOWS.bat`. Alternativen und die Zeitzonenfallen:
[DATENQUELLEN.md](../docs/DATENQUELLEN.md).

**3. `START-WINDOWS.bat` doppelklicken.**

Das war es. Das Skript prüft Python, prüft das Paket, findet die Datei und rechnet. Fehlt
etwas, sagt es, was fehlt und wo es herkommt. Auf Mac oder Linux stattdessen
`./start-mac-linux.sh`.

Wer lieber selbst tippt:

```bash
python -m metals verdict --file XAU_5m_data.csv --tz broker_gmt3 --equity 400
```

### Was dabei herauskommt

Fünf Prüfungen und eine Empfehlung im Klartext:

```
  [JA ] 1. Die Datei                    geladen, Zeitzone plausibel
  [   ] 2. Kehrt Gold zur Tagesmitte zurueck?     zur Einordnung
  [JA ] 3. Ist Gold von einem Zufallspfad zu unterscheiden?
  [?  ] 4. Was verdient die Tagesspanne-Strategie?
  [NEIN] 5. Was verdienen die Scalping-Setups S1-S6?

  EMPFEHLUNG: NOCH NICHT INSTALLIEREN
```

**Schritt 3 ist der wichtigste.** Er misst mit dem Varianzverhältnis-Test, ob Bewegungen
zurückkommen oder weiterlaufen — und anders als der Hurst-Exponent hat er eine
Nullverteilung, sagt also nicht nur eine Zahl, sondern ob sie etwas bedeutet.

**Schritt 2 entscheidet bewusst nichts.** Der Anteil der Tage, die in der Mitte ihrer
eigenen Spanne schließen, sah wie das billigste Maß für dieselbe Frage aus. Er ist es
nicht: Auf 5-Minuten-Balken fällt er, wenn die Rückkehr steigt, auf 1-Minuten-Balken steigt
er. Derselbe Generator, dieselben Tage, entgegengesetzte Antworten
([A28](../docs/REPO-AUDIT.md)). Er steht noch da, weil er eine echte Beobachtung über deine
Datei ist — aber er trägt keine Entscheidung.

**Schritt 4 und 5 sind zwei verschiedene Strategien**, und sie zu verwechseln ist der
naheliegendste Fehler an dieser Stelle. Schritt 5 misst die Setups S1–S6, die der EA
**standardmäßig** handelt. Schritt 4 misst die Tagesspanne-Strategie, über die
[PAPIER-LAUF.md](../docs/PAPIER-LAUF.md) und [URTEIL.md](../docs/URTEIL.md) sprechen — sie
ist im EA als Setup „DR" **standardmäßig ausgeschaltet**.

### Und was du dann tust

| Empfehlung | Was sie bedeutet |
|---|---|
| **NICHT INSTALLIEREN** | Bewegungen laufen weiter statt zurückzukommen, und die Strategie zeigt keine Kante. Fertig. Das hat eine halbe Stunde gekostet statt einer Demo-Phase über Wochen. |
| **NOCH NICHT INSTALLIEREN** | Kein Ergebnis in die eine oder andere Richtung — der häufigste Ausgang. Was hier nicht als Kante sichtbar ist, wird es durch eine Demo-Phase nicht. |
| **INSTALLIEREN — im Advisor-Modus** | Die Kante ist auf echten Daten messbar. Erster Beleg dieses Projekts, der nicht vom Simulator kommt. Dann weiter mit dem Rest dieser Seite. |

Kommt oben eine **Zeitzonen-Warnung** („die volatilsten Stunden sind [0,1,4,6] UTC, normal
sind 12–17"), stimmt `--tz` nicht. Dann `broker_gmt2` oder `utc` probieren, bis die Warnung
verschwindet. Das ist kein Schönheitsfehler: Eine falsche Zeitzone verschiebt jede
Session-Regel und produziert einen plausibel aussehenden, falschen Backtest.

**Was du liest, ist nicht die Trefferquote, sondern der Erwartungswert pro Trade.** Eine
Quote von 68 % bei −0,18 R ist kein Sonderfall, sondern der Normalfall, wenn die Kosten die
Bruttokante auffressen.

---

## Was du brauchst

- Einen Windows-PC oder Laptop
- Etwa 15 Minuten
- Kein Geld, kein Konto irgendwo (das Demokonto kommt gleich aus MetaTrader selbst)

---

## Schritt 1 — MetaTrader 5 installieren

Im Browser auf **https://www.metatrader5.com/de/download** → **Windows** herunterladen →
Datei öffnen → durchklicken.

Am Ende startet MT5 und fragt nach einem Konto.

## Schritt 2 — Demokonto anlegen

MT5 fragt beim ersten Start nach einem Broker. Du brauchst keinen:

1. In das Suchfeld **`MetaQuotes`** tippen
2. **MetaQuotes-Demo** auswählen → **Weiter**
3. **Neues Demokonto eröffnen** wählen
4. Ausfüllen: Name, E-Mail, Land. Kontotyp **Forex**, Einzahlung **1 000 USD**, Hebel
   **1:100**
5. Haken bei den Bedingungen → **Weiter**

Login und Passwort werden dir angezeigt — Screenshot machen, du brauchst sie beim nächsten
Start.

> **Warum 1 000 USD und nicht 100 000?** Weil du sonst Positionsgrößen übst, die du später
> nie handeln wirst. Und nicht 55, weil der EA dann jeden Gold-Trade ablehnt — die kleinste
> mögliche Position wäre über dem 1 %-Risikolimit. Warum das so ist:
> `python -m metals minimum XAUUSD --equity 55`.

> ### Zwei verschiedene Logins — das wird ständig verwechselt
>
> | | Was es ist | Brauchst du es? |
> |---|---|---|
> | **Handelskonto** | Die Nummer, die MT5 dir gerade gegeben hat (z. B. `<deine Kontonummer>`), Broker `MetaQuotes-Demo` | **Ja.** Ohne das läuft nichts |
> | **MQL5-Community-Konto** | Ein separates Konto auf mql5.com, für Market, Signale und das eingebaute VPS | **Nein**, nicht für den EA |
>
> Wenn „das Einloggen nicht geht", ist es fast immer das **zweite**. Der EA braucht es
> nicht. Erkennen kannst du das an der **Titelleiste**: Steht dort deine Kontonummer und
> `MetaQuotes-Demo`, ist das Handelskonto verbunden — fertig.
>
> **Für den VPS wird es allerdings gebraucht:** Das eingebaute *Virtual Hosting* in MT5
> (Knopf **VPS** unten rechts) setzt ein MQL5-Community-Konto voraus. Dafür dann auf
> [mql5.com](https://www.mql5.com) registrieren. Ein gemieteter Windows-VPS braucht es
> nicht — siehe [VPS-SETUP.md](./VPS-SETUP.md).

Unten rechts in MT5 muss jetzt eine Verbindung mit Zahlen (kb/s) stehen. Steht dort „Keine
Verbindung", stimmt etwas mit dem Internet nicht.

## Schritt 3 — Die EA-Datei holen

Im Browser diese Adresse öffnen:

```
https://raw.githubusercontent.com/arthursideload-star/Trade-/refs/heads/claude/trading-bot-plan-4uj86r/mt5/Experts/GoldScalpAssistant.mq5
```

Du siehst eine Wand aus Text. **Rechtsklick → Speichern unter**.

**Wohin?** In MT5: **Datei → Datenverzeichnis öffnen**. Ein Explorer-Fenster geht auf. Dort
in den Ordner **`MQL5`** → **`Experts`**. Dorthin speichern.

Wichtig: Der Dateiname muss auf **`.mq5`** enden, nicht auf `.txt`. Falls Windows `.txt`
anhängt, umbenennen.

## Schritt 4 — Kompilieren

Zurück in MT5: **F4** drücken. Es öffnet sich der MetaEditor.

Links im **Navigator** den Ordner **Experts** aufklappen → **`GoldScalpAssistant.mq5`**
doppelklicken → oben auf **Kompilieren** (oder **F7**).

Unten muss stehen: **`0 errors, 0 warnings`**.

> ### ⚠ Die Falle: F7, nicht F5
>
> **F7 = Kompilieren. F5 = im Debug-Modus starten.** Die Tasten liegen nebeneinander und
> tun völlig verschiedene Dinge.
>
> Drückst du **F5**, startet MetaEditor eine Debug-Sitzung: Es öffnet MetaTrader, legt einen
> Chart mit dem **Debug-Standardsymbol** an — meist **EURUSD, H1** — und hängt den EA
> **dort** an. Nicht auf den Chart, den du offen hattest.
>
> Du erkennst es an drei Stellen:
> - MetaEditor-Titelleiste sagt **„MetaEditor (Debugging)"**
> - unten im MetaEditor ist der Reiter **Debug** aktiv statt **Fehler**
> - oben rechts im Chart steht **„GoldScalpAssistant (Debugging)"**, und die Titelleiste
>   von MT5 endet auf **`[EURUSD,H1]`**
>
> **Das ist der Grund, wenn „der Bot immer das Falsche öffnet".**
>
> Rauskommen: in MetaEditor **Umschalt+F5** (Debuggen beenden), dann in MT5 den falschen
> Chart schließen. Danach normal mit **F7** kompilieren und weiter bei Schritt 5.
>
> Seit dieser Erfahrung **verweigert der EA den Start auf einem Nicht-Gold-Symbol** — er
> zeigt eine Meldung und lädt sich nicht. Vorher hat er auf EURUSD einfach weitergerechnet
> und sein Panel gezeichnet, als wäre alles in Ordnung ([A30](../docs/REPO-AUDIT.md)).

- Steht `0 errors, 0 warnings` da → weiter.
- Kommen Fehler mit Zeilennummern → **abfotografieren und mir schicken**. Ich kann MQL5 hier
  nicht kompilieren, das ist also der erste echte Test der Datei. Fehler sind an dieser
  Stelle normal und in Minuten behoben.

## Schritt 5 — Auf den Chart

1. **Ansicht → Marktübersicht** → **XAUUSD** suchen
   (heißt bei manchen Brokern `GOLD`, `XAUUSD.r` oder `XAUUSDm` — dann eben so)
2. Rechtsklick darauf → **Chartfenster**
3. Oben den Zeitrahmen auf **M5** stellen. Der EA rechnet ohnehin auf M5 — alle
   Kursabfragen im Code fragen ausdrücklich nach M5, egal was der Chart zeigt. Auf
   einem H1-Chart wären die Zahlen also **richtig**, sie passen nur nicht zu den
   Kerzen, die du siehst. Der EA sagt das dann auch. M5 ist trotzdem richtig, damit
   Panel und Chart dasselbe erzählen.
4. Links im **Navigator** unter *Expert Advisors* den **GoldScalpAssistant** auf den Chart
   ziehen
5. Im Fenster: Reiter **Allgemein** → Haken bei **Algo-Trading erlauben** → **OK**
6. In der Symbolleiste den Knopf **Algo-Trading** anklicken, bis er **grün** ist

**Fertig, wenn:**
- oben rechts im Chart ein 🙂 steht (nicht 😞)
- oben links das Panel erscheint und dort **`[ADVISOR]`** steht

---

## Was jetzt passiert

`[ADVISOR]` heißt: Er rechnet, zeichnet, meldet Setups — **platziert aber keine Order**.
Genau so soll es anfangen. Du vergleichst seine Vorschläge mit dem, was du selbst gemacht
hättest.

**Meistens passiert nichts, und das ist richtig.** Die allermeisten Kerzen sind keine
Gelegenheit. Wenn stundenlang nichts kommt, arbeitet der EA korrekt.

Das Panel bewertet zuerst die **Uhrzeit**:

| Anzeige | Bedeutung |
|---|---|
| **`PRIME`** | London, New York oder die Überlappung. Die Stunden mit Bewegung. |
| **`good`** | Handelbar, aber nicht die beste Zeit. |
| **`marginal`** | Dünn. Asiatische Stunden. |
| **`AVOID`** | Gesperrt: Wochenende, Rollover (21–23 UTC) oder Markt zu. Kein Fehler. |

Wo du nachliest, was er gemeldet hat: **Ansicht → Werkzeugkasten** → Reiter **Experten**.

## Das Journal

Ab dem ersten Setup schreibt der EA automatisch mit — jedes erkannte Setup, jedes abgelehnte
samt Grund, jeden geschlossenen Trade mit Ergebnis in R. Die Datei heißt
`GoldScalpAssistant.csv` und liegt in **Datei → Datenverzeichnis öffnen** → `MQL5` →
`Files`.

Schick sie mir, oder werte sie selbst aus:

```bash
python -m metals journal --file GoldScalpAssistant.csv
```

Die Auswertung sagt dir nicht nur, was passiert ist, sondern auch **was das belegt** — und
bei kleiner Stichprobe sagt sie ehrlich: nichts. Warum das so ist und warum sich der Bot
nicht selbst nachjustiert: [../docs/LERNEN.md](../docs/LERNEN.md).

---

## Wenn du den Rechner ausmachst

Dann steht der EA still. Er läuft nur, solange MT5 offen ist.

**Für die Testphase ist das völlig in Ordnung.** Lass ihn abends ein paar Stunden laufen,
während du sowieso am Rechner bist — das reicht, um zu sehen, ob er sinnvolle Sachen meldet.

Ein VPS lohnt sich erst, wenn du sagen kannst: „Seine Vorschläge sehen brauchbar aus, ich
will das durchgehend messen." Vorher zahlst du Miete für einen Bot, dessen Vorteil nicht
belegt ist. Der Weg dorthin steht dann in [VPS-SETUP.md](./VPS-SETUP.md).

---

## Häufige Probleme

| Symptom | Ursache und Lösung |
|---|---|
| Datei heißt `.mq5.txt` | Windows hat `.txt` angehängt. Im Explorer umbenennen, Dateiendungen ggf. über *Ansicht → Dateinamenerweiterungen* einblenden |
| MetaEditor zeigt die Datei nicht | Falscher Ordner. In MT5 **Datei → Datenverzeichnis öffnen**, dann `MQL5\Experts` — nicht irgendein anderer Experts-Ordner |
| Trauriges Gesicht 😞 am Chart | *Algo-Trading erlauben* nicht angehakt, oder der Knopf in der Symbolleiste ist nicht grün |
| EA hängt auf **EURUSD, H1** statt XAUUSD | **F5 statt F7** gedrückt — Debug-Modus. Siehe den Kasten in Schritt 4. Umschalt+F5, falschen Chart schließen, mit F7 neu kompilieren |
| Meldung „REFUSED: this EA is built for gold" | Genau richtig — der EA hängt auf einem Nicht-Gold-Chart und weigert sich. Auf einen XAUUSD-Chart ziehen |
| Panel passt nicht zu den Kerzen | Chart steht nicht auf M5. Die Zahlen stimmen trotzdem, sie beziehen sich nur auf M5 |
| „Einloggen geht nicht" | Meist das MQL5-Community-Konto, nicht das Handelskonto. Für den EA nicht nötig — siehe den Kasten in Schritt 2 |
| Panel erscheint nicht | EA nicht auf den Chart gezogen, oder Algo-Trading rot |
| Panel zeigt dauernd `AVOID` | Wochenende, Rollover (21–23 UTC) oder Markt geschlossen. Richtig so |
| Panel `PRIME`, aber nichts passiert | Kein Setup. Nichtstun ist der Normalfall — aber siehe den Kasten unten, wie lange „normal" ist |
| Kein XAUUSD in der Marktübersicht | Rechtsklick → *Alle anzeigen* |
| „cannot size" im Experten-Reiter | Konto zu klein für die Stop-Distanz. Demokonto mit 1 000 USD nehmen |
| Keine `GoldScalpAssistant.csv` | Kommt erst beim ersten erkannten Setup. Geduld — in ruhigen Stunden dauert das |

---

## Wie oft der Bot überhaupt etwas tut

Diese Frage kam auf, weil der Bot 15 Minuten lief und nichts passierte. Das war damals
**kein Geduldsproblem, sondern ein Fehler** — S2 konnte konstruktionsbedingt nie auslösen
und S5 fiel vollständig durch den Konfidenzfilter (siehe A31–A33 in
`docs/REPO-AUDIT.md`). Beides ist behoben.

Gemessen über je 60 simulierte Handelstage, drei Seeds, Setups S2/S4/S5:

| Seed | vorher | nachher |
|---|---:|---:|
| 7 | 6 Trades (0,10/Tag) | **57 Trades (0,95/Tag)** |
| 99 | 8 Trades (0,13/Tag) | **81 Trades (1,35/Tag)** |
| 4242 | 9 Trades (0,15/Tag) | **75 Trades (1,25/Tag)** |

**Was diese Zahlen sind und was nicht.** Sie stammen aus dem simulierten Markt, nicht aus
echten Gold-Daten, und sie sagen nur, **wie oft** gehandelt wird — nichts darüber, ob das
Geld verdient. Dafür ist `python -m metals verdict` zuständig, und dessen Antwort steht in
`docs/URTEIL.md`. Gemessen wird außerdem im gemeinsamen Backtest, in dem auch S1 und S3 um
dieselben Balken konkurrieren; der EA handelt nur S2/S4/S5 und kommt deshalb eher auf mehr
als auf weniger.

**Die praktische Erwartung: rund ein Trade pro Tag.** Wenn du eine Stunde zusiehst, ist
„nichts" das wahrscheinlichste Ergebnis. Wenn ein **ganzer Handelstag** ohne einen einzigen
Eintrag im Experten-Reiter vergeht, stimmt etwas nicht — dann lohnt der Blick ins Log.

**Der EA sagt dir jetzt, wenn er etwas gesehen und verworfen hat.** Im Experten-Reiter
steht dann eine Zeile wie:

```
S5 seen at confidence 0.58, below the 0.60 minimum. Skipped -- the backtest
that produced the published numbers filtered it too.
```

Das ist der Normalfall und kein Fehler. Der Wert ist über `InpMinConfidence` einstellbar,
Voreinstellung 0,60 — dieselbe Zahl, mit der der Backtest rechnet. **Wer sie senkt,
handelt eine andere Strategie als die gemessene.**

Diese Zeile landet auch im Journal, nicht nur im Log. Nach ein paar Wochen beantwortet

```bash
python -m metals journal --file GoldScalpAssistant.csv
```

in der Tabelle **BY CONFIDENCE** die Frage, ob die Schwelle überhaupt etwas sortiert:
Laufen Trades über 0,70 wirklich besser als die bei 0,60? Wenn nicht, gehört die Zahl
abgeschafft statt nachjustiert. Vorher — unter 30 abgeschlossenen Trades — sagt die
Tabelle selbst, dass sie nichts belegt.
