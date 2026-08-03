# Trades

**Dieser Ordner füllt sich selbst.** Jeder abgeschlossene Trade des EA bekommt eine eigene
Notiz — mit Einstieg, Stop, Ziel, Ausstiegsgrund, Haltedauer, dem Spread beim Einstieg und
dem Ergebnis in R.

```bash
python -m metals vault --journal GoldScalpAssistant.csv
```

Die CSV schreibt der EA selbst. In MetaTrader: **Datei → Datenverzeichnis öffnen** →
`MQL5` → `Files`.

## Zwei Dinge, die du wissen musst

**Deine eigenen Notizen bleiben erhalten.** Jede Trade-Notiz hat einen Block
*„Was ich dazu weiß"*. Was du dort hineinschreibst, liest der Export vor dem Überschreiben
aus und setzt es danach wieder ein. Du kannst also gefahrlos jede Woche neu exportieren.

**Der obere Teil wird überschrieben.** Er trägt einen Vermerk. Schreib nichts hinein, was du
behalten willst — es ist beim nächsten Export weg.

## Wozu das gut ist

Eine CSV-Zeile kann man nicht durchsuchen, nicht verlinken und nicht kommentieren. Eine
Notiz schon. Nach dreißig Trades kannst du in Obsidian fragen:

- Welche Trades hatten `ausstieg: stop` **und** einen Spread über 0,40 $/oz?
- Welche habe ich mit „Plan nicht befolgt" markiert — und wie sind die ausgegangen?
- Welches Setup hat mich am meisten gekostet?

Das ist der eigentliche Zweck: **aus Fehlern lernen setzt voraus, dass man sie wiederfindet.**

## Was der Ordner NICHT ist

Er ist keine Auswertung. Die Übersicht [[Alle Trades]] zählt zusammen, was passiert ist —
sie sagt **nicht**, was das belegt. Dafür gibt es Konfidenzbänder:

```bash
python -m metals journal --file GoldScalpAssistant.csv
```

Bei kleiner Stichprobe sagt die Auswertung ehrlich, dass sie nichts belegt. Dann belegt sie
nichts, egal wie überzeugend die Summe aussieht.

## Nicht genommene Signale

Sie bekommen **keine** eigene Notiz. Dreihundert „kein Trade"-Notizen begraben die zwanzig,
die stattgefunden haben. Sie werden in [[Alle Trades]] gezählt, und ihre Gründe wertet
`metals journal` aus.
