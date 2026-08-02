# Warum hier keine Zahlen stehen

Die naheliegende Idee ist, in Obsidian eine schöne Übersicht anzulegen: Kontostand,
Trefferquote, Erwartungswert, eine Kurve. Mach das nicht.

## Der Grund ist gemessen, nicht behauptet

Das Repo hat achtundzwanzig Auditbefunde, und ein **wiederkehrendes Muster** darin ist:
Eine Zahl wird in Fließtext geschrieben, die Wirklichkeit läuft weiter, und der Text
behauptet weiter die alte Zahl.

- `docs/URTEIL.md` sagte „53 Sitzungen", es waren längst 57.
- Die Skill-Datei nannte 0,20 $/oz Spread als *die* Zahl. Beim Rollover sind es 5 $.
- `PLAN.md` führte das Journal-Modul als „offen", Tage nachdem es fertig war.
- `metals rules` behauptete, alle harten Regeln zu listen, und ließ eine aus.
- Der Kalender versprach FOMC-Termine und gab nie einen aus.

Jedes Mal derselbe Mechanismus: **Eine kopierte Zahl kennt ihre Quelle nicht und kann
deshalb nicht mitwachsen.**

Ein Obsidian-Tresor voller Kennzahlen ist genau diese Falle, nur mit besserer Typografie.
Nach zwei Wochen stimmt nichts mehr, und weil es hübsch aussieht, glaubt man es länger.

## Was stattdessen

**Zahlen holst du dir, wenn du sie brauchst:**

```bash
python -m metals paper --review      # was gut war, was schlecht war
python -m metals journal             # was der EA getan hat
python -m metals paper --summary     # wo das Konto steht
```

Diese Befehle rechnen jedes Mal neu. Sie können nicht veralten.

**Hier hinein gehört, was kein Befehl rechnen kann:**

- „Ich bin ausgestiegen, weil mir mulmig war" — das ist eine Beobachtung über *dich*,
  und sie ist wertvoller als der R-Wert des Trades.
- „Der Spread war heute den ganzen Vormittag doppelt so breit" — das steht in keiner CSV.
- „Ich habe die Regel gebrochen und es hat funktioniert" — der gefährlichste Eintrag
  überhaupt, weil er schlechtes Verhalten belohnt. Er gehört aufgeschrieben.
- „Warum habe ich damals X entschieden" — in einem halben Jahr weißt du es nicht mehr.

## Die einzige Ausnahme

Eine Zahl darf hier stehen, wenn du **daneben schreibst, wann du sie geholt hast**:

> Erwartungswert +0,174 R (Stand 01.08.2026, `paper --review`)

Das Datum macht aus einer Behauptung eine Beobachtung. Ohne Datum ist es eine Behauptung,
die irgendwann falsch wird, ohne dass es jemandem auffällt.

Siehe auch: [[START HIER]]
