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
- Welche hatten `konfidenz` über 0,70 — und lief es da wirklich besser?

Das ist der eigentliche Zweck: **aus Fehlern lernen setzt voraus, dass man sie wiederfindet.**

## Die Konfidenz — und warum sie in jeder Notiz steht

Der EA gibt jedem erkannten Setup eine Zahl zwischen etwa 0,55 und 0,90 und handelt erst ab
**0,60**. Diese Zahl steht seit dem 04.08.2026 in jeder Trade-Notiz.

Sie steht dort, damit sie **überprüfbar** ist. Eine Schwelle rechtfertigt sich nur dadurch,
dass sie sortiert: Trades darüber müssten besser laufen als Trades darunter. Solange das
niemand nachrechnen kann, ist die Zahl Dekoration.

Nachrechnen tut es die Tabelle **BY CONFIDENCE** in:

```bash
python -m metals journal --file GoldScalpAssistant.csv
```

Erwartet wird eine steigende mittlere R-Spalte von oben nach unten. **Kommt sie nicht,
gehört die Schwelle abgeschafft — nicht nachjustiert.** Ein Regler, der nichts trennt,
wird nicht besser, wenn man ihn verschiebt.

Vor 30 abgeschlossenen Trades sagt die Tabelle von selbst, dass sie nichts belegt.

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
