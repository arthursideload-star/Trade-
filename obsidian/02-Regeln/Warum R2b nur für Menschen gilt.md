# Warum R2b nur für Menschen gilt

**R2b:** Bei +2 % am Tag ist Schluss. „Einen guten Tag zurückzugeben ist die häufigste Art,
eine gute Woche zu verlieren."

Die Regel steht im Code und `python -m metals stop` setzt sie durch. Für den **Bot** ist
sie ausgeschaltet, und das ist kein Versehen, sondern gemessen.

## Was die Messung ergab

Dieselben Märkte, einmal mit Regel, einmal ohne — 1.200 Durchläufe:

| | ohne R2b | mit R2b |
|---|---:|---:|
| Median | −1,26 % | **+2,39 %** |
| Verlusttage | 54,2 % | **34,5 %** |
| schlimmster Tag | −11,35 % | **−9,18 %** |
| **Mittelwert** | **+1,75 %** | **+0,77 %** |

**Drei von vier Zahlen, auf die ein Mensch schaut, werden besser. Die eine, die zahlt, wird
schlechter** — um 1,34 % am Tag, mit einem Konfidenzband, das die Null nicht berührt.

Reproduzieren: `python -m metals claims --measure` bzw. `claims.measure_daily_win_stop`.

## Warum das kein Widerspruch ist

Ein Gewinnziel schneidet den **rechten Rand** der Verteilung ab und lässt den linken stehen.
Es verwandelt viele verschiedene Ergebnisse in einen Haufen bei exakt +2 % plus die
Verlierer. Das hebt Trefferquote und Median — und bezahlt es mit den Tagen, die den Monat
gemacht hätten.

Es ist dieselbe Sache wie „90 % Trefferquote": Man kann sie kaufen, sie kostet
Erwartungswert.

## Und trotzdem gilt sie für dich

Weil R2b kein Rechenmittel ist, sondern ein **Verhaltensmittel**. Sie adressiert, dass ein
Mensch nach einem guten Tag anfängt, größer zu werden und schlechtere Setups zu nehmen.

Eine Strategie tut das nicht. Sie hat kein Gefühl von „heute läuft's".

**Wenn du also bei +2 % aufhörst, hörst du nicht auf, weil es rechnerisch besser ist. Du
hörst auf, weil du dir selbst nicht zutraust, ab hier noch gute Entscheidungen zu treffen.**
Das ist ein völlig legitimer Grund und ein ehrlicherer als der, den die Regel behauptet.

Siehe auch: [[START HIER]] · `docs/REPO-AUDIT.md`, A25
