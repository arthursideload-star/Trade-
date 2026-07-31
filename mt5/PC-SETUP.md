# Bot am eigenen PC — der einfache Weg

Das hier ist die Anleitung für **Windows-PC oder Laptop**. Sie ist kurz, weil der Weg kurz
ist: rund **15 Minuten**, davon 10 Minuten Warten auf Downloads.

Kein VPS. Keine Miete. Kein Container, kein KasmVNC, kein `CUSTOM_USER`-Rätsel.

> **Wenn du von der VPS-Anleitung kommst:** Ja, das ist wirklich alles. Der komplizierte Weg
> in [VPS-SETUP.md](./VPS-SETUP.md) existiert nur für den Fall, dass der Bot laufen soll,
> **während der Rechner aus ist**. Solange du testest, brauchst du das nicht.

---

## Vorher: Tag 1 gehört dem Backtest, nicht der Installation

Bevor du irgendetwas installierst, beantworte die Frage, die alles andere entscheidet:
**Funktioniert die Strategie auf echten Golddaten überhaupt?**

Bisher gemessen wurde nur auf einem Marktsimulator, weil die Bauumgebung keinen Netzzugang
hat — und dort war **jede** Konfiguration negativ
([BACKTEST-ERGEBNISSE.md](../docs/BACKTEST-ERGEBNISSE.md)). Auf echten Daten ist das noch
nicht geprüft. Das ist der offene Punkt O18, und du bist die erste Gelegenheit, ihn zu
schließen.

**Datei holen** (kostenlos, fertig als CSV):
Kaggle → *„XAU/USD Gold Price Historical Data"* von `novandraanugrah` → `XAU_5m_data.csv`.
Enthält 5-Minuten-Kerzen ab 2004. Alternativen und die Zeitzonenfallen:
[DATENQUELLEN.md](../docs/DATENQUELLEN.md).

**Laufen lassen — und zwar beides, das sind zwei verschiedene Strategien:**

```bash
# 1. Die Scalping-Setups S1-S6 (das, was der EA standardmaessig handelt)
python -m metals backtest --source file --file XAU_5m_data.csv --tz broker_gmt3

# 2. Die Tagesspanne-Strategie (das, was der Papier-Lauf misst)
python -m metals dayrange --file XAU_5m_data.csv --tz broker_gmt3 \
    --equity 1000 --risk 1
```

**Verwechsle die beiden nicht.** Der erste Befehl testet die Setups, die der EA ohne weitere
Einstellung handelt. Der zweite testet die Strategie, über die
[PAPIER-LAUF.md](../docs/PAPIER-LAUF.md) und [URTEIL.md](../docs/URTEIL.md) sprechen — Bewegung
vorhersagen, bei der Hälfte schließen. Das ist die, die du beschrieben hast, und im EA ist sie
als Setup „DR" **standardmäßig ausgeschaltet**.

Nur Befehl 1 laufen zu lassen und das Ergebnis auf den Papier-Lauf zu beziehen, wäre der
naheliegendste Fehler an dieser Stelle.

Beim zweiten Befehl wird dir auffallen, dass er auf 1.000 € die allermeisten Signale ablehnt
(in einem Testlauf: 886 von 924). Das ist kein Fehler, sondern die 1-%-Regel — die Rechnung
dazu steht in [KONTOGROESSE.md](../docs/KONTOGROESSE.md).

Der Lader erkennt das Format selbst und **prüft die Zeitzone gegen Golds bekanntes
Volatilitätsprofil**. Kommt eine Warnung wie *„die volatilsten Stunden sind [0,1,4,6] UTC,
normal sind 12–17"*, stimmt `--tz` nicht — dann `broker_gmt2` oder `utc` probieren, bis die
Warnung verschwindet. Das ist kein Schönheitsfehler: Eine falsche Zeitzone verschiebt jede
Session-Regel und produziert einen plausibel aussehenden, falschen Backtest.

**Was du dann liest:** nicht die Trefferquote, sondern den **Erwartungswert pro Trade**. Eine
Quote von 68 % bei −0,18R ist keine Seltenheit, sondern der Normalfall, wenn die Kosten die
Bruttokante auffressen. Der Report zeigt beides getrennt.

- **Erwartungswert deutlich negativ** → nicht installieren. Dann ist der EA ein sehr
  disziplinierter Weg, Geld zu verlieren, und die Arbeit gehört in die Setups.
- **Um null herum** → installieren, aber im Advisor-Modus und ohne Eile.
- **Deutlich positiv** → dann wird es interessant, und dann reden wir über die nächsten
  Schritte.

Erst danach das hier:

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

- Steht das da → weiter.
- Kommen Fehler mit Zeilennummern → **abfotografieren und mir schicken**. Ich kann MQL5 hier
  nicht kompilieren, das ist also der erste echte Test der Datei. Fehler sind an dieser
  Stelle normal und in Minuten behoben.

## Schritt 5 — Auf den Chart

1. **Ansicht → Marktübersicht** → **XAUUSD** suchen
   (heißt bei manchen Brokern `GOLD`, `XAUUSD.r` oder `XAUUSDm` — dann eben so)
2. Rechtsklick darauf → **Chartfenster**
3. Oben den Zeitrahmen auf **M5** stellen. **Pflicht** — der EA rechnet auf M5.
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
| Panel erscheint nicht | EA nicht auf den Chart gezogen, oder Algo-Trading rot |
| Panel zeigt dauernd `AVOID` | Wochenende, Rollover (21–23 UTC) oder Markt geschlossen. Richtig so |
| Panel `PRIME`, aber nichts passiert | Kein Setup. Nichtstun ist der Normalfall |
| Kein XAUUSD in der Marktübersicht | Rechtsklick → *Alle anzeigen* |
| „cannot size" im Experten-Reiter | Konto zu klein für die Stop-Distanz. Demokonto mit 1 000 USD nehmen |
| Keine `GoldScalpAssistant.csv` | Kommt erst beim ersten erkannten Setup. Geduld — in ruhigen Stunden dauert das |
