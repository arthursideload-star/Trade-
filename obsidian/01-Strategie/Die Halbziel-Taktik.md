# Die Halbziel-Taktik — viele kurze Trades

Deine Idee vom 04.08.2026, gebaut und gemessen. Code: `metals/halfscalp.py`

## Die Idee in einem Absatz

Der Bot schaut durchgehend auf den Chart. Sieht er eine Möglichkeit, nimmt er sie. Er
schätzt, **wie weit** der Kurs plausibel laufen würde, und schließt schon bei der **Hälfte**
dieser Strecke — für Sicherheit. Dazu ein Stop für den Fall, dass es in die falsche Richtung
geht. Ein Trade dauert 1–10 Minuten, dann schaut er wieder 1–10 Minuten und macht den
nächsten.

## Das Ergebnis: sie verliert. Jeden Tag.

Über fünf simulierte Märkte, 152 Trades am Tag:

| | |
|---|---|
| Trefferquote | **64,1 %** |
| Erwartungswert | **−0,110 R je Trade** |
| Verlusttage | **85 von 85** |
| Bester Tag | **−1,17 R** |

Der **beste** von 85 Tagen war ein Verlusttag. Das ist kein Pech.

## Warum — und das ist der wichtigste Absatz hier

Du nimmst die **Hälfte** des Ziels. Der Stop steht aber bei der **vollen** Strecke.

Damit riskierst du **zwei, um eins zu gewinnen**. Und dann rechnet sich die Trefferquote,
die du dafür brauchst, ganz von allein aus:

> Gewinne im Schnitt 1, verliere im Schnitt 2,5 → du brauchst **72 %** Treffer, nur um bei
> null zu landen.

Gemessen wurden 64 %. Die fehlenden acht Punkte **sind** der Verlust.

**Das Frühschließen erhöht die Trefferquote wirklich.** Deine Intuition stimmt an der
Stelle. Es erhöht aber gleichzeitig die Latte — und zwar um mehr. Beides passiert, man
sieht nur das eine.

> Das ist die Falle: **Zwei von drei Trades gewinnen, und das Konto fällt trotzdem.**
> Von innen fühlt sich das an, als könnte es gar nicht sein.

## Die zweite Zahl: der Spread frisst alles

Ergebnis −287,6 R. Kosten −292,5 R.

**Vor Kosten ist die Strategie fast genau bei null.** Der ganze Verlust ist der Spread —
152-mal am Tag bezahlt.

Bei einem Ziel von 1,50 $ pro Unze, halbiert auf 0,75 $, kostet ein Spread von 0,30 $
**40 % vom Bruttogewinn**. Bei jedem Trade. Egal ob er gewinnt oder verliert.

Deshalb lehnt der Bot Trades ab, deren Halbziel den Spread nicht deutlich schlägt, und
zählt sie mit. Ein Trade, der seinen eigenen Spread nicht verdient, hat keine kleine
Kante — er hat eine negative.

## Was sie retten würde

Ich habe 18 Varianten durchgerechnet. Zwei Dinge kamen heraus:

**1. Dem Impuls folgen verliert immer.** Alle neun Momentum-Varianten sind negativ.
Dagegenhalten funktioniert besser.

**2. Der Hebel ist die Zielweite, nicht der Stop.** Wenn das Ziel doppelt so weit gesteckt
wird, halbieren sich die Kosten je Trade — der Spread ist ja fest, das Risiko wächst mit.

Die beste gefundene Fassung: dagegenhalten, Ziel doppelt so weit, weiter bei der Hälfte
schließen. Alle Zahlen unten: Stand 04.08.2026, Befund A34 in `docs/REPO-AUDIT.md`.

Nachzurechnen — und der Befehl braucht die alten Vorgaben, weil sie inzwischen ehrlicher
sind (siehe Nachtrag):

```bash
python -m metals halfscalp --spread 0.20 --spread-model flat --all-hours
```

| | wörtlich | beste Fassung |
|---|---:|---:|
| Trades/Tag | 152 | 128 |
| Trefferquote | 64,1 % | 61,5 % |
| nötig für null | 71,9 % | 56,4 % |
| **Erwartungswert** | **−0,110 R** | **+0,045 R** |
| Verlusttage | 85 von 85 | 20 von 85 |

**Deine Grundidee bleibt darin erhalten.** Früh sichern, Stop dabei. Nur die Strecke wird
weiter gesteckt, damit der Spread nicht mehr die Hauptrolle spielt.

## Nachtrag: der Spread war noch zu freundlich gerechnet

Die Zahlen oben rechnen mit **einem** Spread für den ganzen Tag — 0,20 $. So hat es das
ganze Projekt bisher gemacht.

Bei vier Trades im besten Fenster ist das ungefähr richtig. Bei **128 Trades am Tag** nicht:
Wer durchgehend auf den Chart schaut, schaut auch durch den Rollover. Und da steht im
Repo seit langem:

| | $/Unze |
|---|---:|
| normal | 0,20 |
| **Rollover (21–23 Uhr UTC)** | **5,00** |
| um eine Nachricht herum | 10,00 |

**Fünfundzwanzigmal so teuer.** Neu gerechnet, 24 Märkte, Stand 04.08.2026:

| | Erwartungswert |
|---|---:|
| ein Spread für alles, rund um die Uhr | +0,043 R |
| **echter Spread je Stunde, rund um die Uhr** | **+0,010 R** |
| echter Spread, nur in guten Fenstern | **+0,029 R** |

**Der eine flache Spread hat die Kante auf das Vierfache aufgeblasen.**

Zwei Dinge sind daraus geworden, und beide sind jetzt die Vorgabe:

1. Der Spread wird berechnet, **wenn er anfällt** — nicht gemittelt.
2. Der Bot **eröffnet** nur in guten Fenstern. Er schaut weiter durchgehend zu; er handelt
   nur nicht mehr um drei Uhr nachts.

Punkt 2 allein ist +0,018 R je Trade wert (Stand 04.08.2026, Befund A35). Das ist mehr als
die halbe Kante.

> Nebenbei: Das Kostengatter hat den Rollover von selbst abgefangen — bei 5,00 $ Spread
> schafft kein Halbziel den nötigen Abstand. Der Filter ist trotzdem besser, weil er auch
> die *mittelteuren* Stunden erwischt.

## Und jetzt die Einschränkung, die dazugehört

Das ist der **Simulator**, nicht echtes Gold.

Ich habe den Test gemacht, an dem die Hauptstrategie gescheitert ist (siehe A27): einzelne
Eigenschaften des künstlichen Marktes abschalten und neu messen.

- **Gut:** Die Kante überlebt, wenn man die „Rückkehr" abschaltet — genau daran ist die
  Hauptstrategie gestorben.
- **Nicht gut:** Sie stirbt, wenn man den **Rundzahl-Magneten** abschaltet (+0,033 → −0,013).

Die Kante sitzt also darin, dass der künstliche Markt zu runden Kursen (4100, 4110 …)
hingezogen wird. Und dieser Magnet steht im Simulator, **weil jemand geglaubt hat, dass
Gold sich so verhält**. Das wieder herauszumessen beweist nichts über echtes Gold.

Es ist trotzdem ein besserer Befund als bei der Hauptstrategie: dort hing alles an einer
reinen Rechenschutzplanke ohne jede Marktbehauptung. Hier hängt es an der Modellierung
eines Effekts, den es geben könnte. **Interessanter — nicht bewiesen.**

## Was dem im Weg steht

Im Code steht `MAX_TRADES_PER_DAY = 4`. Diese Taktik braucht **104 bis 152**.

Das habe ich **nicht** verändert. Projektregel: Risikolimits stehen im Code, und sie zu
ändern ist eine Entscheidung, kein Handgriff. Solange die 4 dort steht, kann die
Halbziel-Taktik nicht scharf laufen — sie lässt sich nur messen.

Diese Entscheidung gehört dir. Sie betrifft jede andere Strategie im Repo mit.

## Selbst nachrechnen

```bash
python -m metals halfscalp --spread 0.20                      # deine Fassung
python -m metals halfscalp --spread 0.20 --signal reversion --target 2.0
```

Der Spread ist Pflicht — es gibt keine Vorgabe, weil er auf diesem Zeithorizont über das
**Vorzeichen** entscheidet. [[Was der Spread zum falschen Zeitpunkt kostet]]

Siehe auch: [[Die Hauptstrategie]] · [[Was noch offen ist]] · Befund A34 in
`docs/REPO-AUDIT.md`
