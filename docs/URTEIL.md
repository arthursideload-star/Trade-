# Das Urteil an der vorher festgelegten Stichprobe

> ## Nachtrag 01.08.2026 — bitte zuerst lesen
>
> Alles unten steht. Die Deutung ist seit **[A27](./REPO-AUDIT.md)** eine andere, und zwar
> nicht ein bisschen.
>
> Der Erwartungswert von +0,198 R ist überwiegend eine **Ablesung eines einzelnen
> Parameters im Simulator**: `MarketParams.reversion = 0.002`. Setzt man ihn auf null,
> fällt die Erwartung auf **+0,007 R** mit einem Band, das die Null schneidet; schaltet man
> alle erzeugten Merkmale ab, verliert die Strategie **−0,133 R** — ihren eigenen Spread,
> was auf einem Zufallspfad genau richtig ist. Die Dosis-Wirkungs-Kurve ist nahezu linear.
>
> Und dieser Parameter ist keine Behauptung über Gold. Sein Kommentar im Generator sagt,
> wozu er da ist: *„prevents random walk blowups"* — eine Rechenschutzplanke.
>
> Dieses Dokument nannte „es läuft auf dem Simulator" schon immer als Vorbehalt Nummer
> eins. Das war richtig und **zu schwach**: Es ist kein Vorbehalt neben anderen, es ist die
> Quelle der gemessenen Kante.
>
> Das heißt **nicht**, dass die Strategie an echtem Gold scheitert. Es heißt, dass dieses
> Urteil die Frage nicht beantwortet, auf die es eine Antwort zu geben scheint. Der Lauf,
> der sie beantwortet, dauert Sekunden:
>
> ```bash
> python -m metals persistence --file XAU_5m_data.csv --tz broker_gmt3
> ```

Bei Sitzung 18 wurde festgelegt, wann geurteilt wird: **rund 300 Trades**, hergeleitet aus
einem nüchternen Vorteil von +0,10 R bei der beobachteten Streuung. Nicht „wenn es gut
aussieht", sondern eine Zahl, die vorher feststand.

**Diese Zahl ist erreicht: 302 Trades nach 36 Sitzungen.** Hier ist das Ergebnis.

## Was dasteht

| | | |
|---|---:|---|
| Trefferquote | 61,3 % | 95%-Band 56–67 % |
| **Erwartungswert** | **+0,198 R** | **95%-Band +0,098 bis +0,297 R** |
| Streuung | 0,880 R | |
| Sitzungs-Clustering | ICC 0,00 | Design-Effekt 1,00 — n ist n |
| Konto | 400 → 1.606,65 € | +301,7 % |

Das Band liegt **vollständig über der Null**. Auf diesen Daten ist der Vorteil messbar.

## Nachtrag nach 53 Sitzungen: die Kette steht auf drei Tagen

> **Momentaufnahme vom 31.07.2026, Stand 53 Sitzungen.** Die Zahlen unten sind nicht
> fortgeschrieben — ein Urteil, das man nachträglich an neue Daten anpasst, ist kein Urteil.
> Der aktuelle Stand kommt aus `python -m metals paper --provenance`, und wie er sich
> seither verändert hat, steht am Ende dieses Abschnitts.
>
> Die Zeilen „2,22 %" und „2,23 %" sind **derselbe Handelstag**, an zwei verschiedenen
> Spotkursen abgefragt. Der Code schlüsselt inzwischen nach dem Hoch/Tief-Paar auf statt
> nach der Prozentzahl und führt sie deshalb zusammen — die Aufteilung hier ist genau der
> Fehler, den der Text darunter beschreibt, in seiner ursprünglichen Form stehengelassen.

```bash
python -m metals paper --provenance
```

| Tagesbild | Sitzungen | Trades | Gewinn | Anteil | Ø Rendite/Sitzung |
|---|---:|---:|---:|---:|---:|
| **ANGESETZT 1,57 %** | 21 | 168 | +779,33 € | **56,3 %** | +3,26 % |
| beobachtet 2,22 % | 13 | 110 | +273,24 € | 19,7 % | +3,11 % |
| beobachtet 2,23 % | 7 | 64 | +240,79 € | 17,4 % | +6,05 % |
| beobachtet 1,01 % | 12 | 93 | +91,77 € | 6,6 % | +0,48 % |

Zwei Dinge stehen da, und beide sind unangenehm.

**Erstens: 56 % des gesamten Gewinns stammen aus Sitzungen, deren Tagesspanne
*angesetzt* war, nicht nachgeschlagen.** Die 1,57 % sind keine Messung. Sie sind aus
*einer* Wochenspanne durch Wurzel 5 abgeleitet, weil an dem Tag keine Ist-Spanne
verfügbar war. Ein Ergebnis, das überwiegend darauf steht, steht auf einer Herleitung.

**Zweitens: es gab nur drei tatsächlich beobachtete Handelstage** — 2,22 %, 2,23 % und
1,01 %. Die ersten beiden sind derselbe Tag (30. Juli, FOMC) aus zwei Kursabfragen. Eine
Kette von 53 Sitzungen aus drei beobachteten Tagen ist ein langer Lauf **eines**
Experiments, nicht ein langer Lauf von Experimenten.

### Was das für die Kurve heißt

Hätte jede der 53 Sitzungen so ausgesehen wie:

| | Endstand nach 53 Sitzungen |
|---|---:|
| der FOMC-Tag (2,23 %) | 9.019 € |
| die angesetzte Spanne (1,57 %) | 2.192 € |
| **der ruhige Tag (1,01 %)** | **515 €** |
| *tatsächliche Kette* | *1.785 €* |

**Der einzige beobachtete ruhige Tag hätte aus 400 € nach 53 Sitzungen 515 € gemacht** —
nicht 1.785 €. Das sind +0,48 % je Sitzung statt +3,26 %.

Die spektakuläre Kurve ist damit zum größten Teil erklärt, und zwar nicht durch die
Strategie: Sie kommt aus einer angesetzten Volatilität und einem außergewöhnlich
bewegten Tag. Das deckt sich mit dem bereits gemessenen Zusammenhang, dass der Ertrag
**schneller** wächst als die Tagesspanne.

Diese Aufschlüsselung ist als Kommando eingebaut und durch Tests festgehalten, damit sie
nicht stillschweigend aus dem Bericht verschwindet.

### Dieselbe Kette ohne die Tage, die nie jemand gesehen hat

Die 21 Sitzungen mit angesetzter Spanne herausgenommen — gleiche Sitzungen, gleiche
Reihenfolge, gleiche Renditen:

| | |
|---|---:|
| Sitzungen behalten | 32 von 53 |
| Konto | 400 € → **919,23 €** (+129,8 %) |
| *zum Vergleich: volle Kette* | *1.785,13 € (+346 %)* |

**Rund zwei Fünftel des Zuwachses verschwinden**, sobald man nur zählt, was tatsächlich
beobachtet wurde. Und die restlichen +130 % ruhen immer noch auf drei Handelstagen.

### Konsequenz im Code, nicht nur im Text

Ein Bericht, der eine Schieflage beschreibt und sie weiter wachsen lässt, ist Dekoration.
`python -m metals paper` **lehnt eine Sitzung jetzt ab**, wenn dasselbe Tagesbild bereits
zehn oder mehr Sitzungen trägt:

```
UEBERSAMPELT: Dieses Tagesbild (2.22 % Spanne) traegt schon 13 Sitzungen.
Eine weitere vergroessert die Schieflage, statt etwas zu messen.
```

Überschreibbar mit `--force`, aber dann bewusst. Der Grund für die Schranke ist genau die
Entstehungsgeschichte dieser Kette: Sie kam auf 53 Sitzungen aus drei beobachteten Tagen,
**weil nichts Halt gesagt hat.** Wiederholung eines Tages lässt die Sitzungszahl wachsen
und die Stichprobe nicht.

### Nachtrag: die Zählung selbst war falsch

Die Aufschlüsselung gruppierte nach der Tagesspanne **in Prozent des Kurses**. Das ist eine
abgeleitete Größe, und sie war in beide Richtungen falsch:

- Der 30. Juli wurde bei drei verschiedenen Spotkursen abgefragt (4.114,79 / 4.102,83 /
  4.114,23). Dieselbe Beobachtung landete dadurch in zwei Zeilen — „2,22 %" und „2,23 %" —
  und **eine Beobachtung mit 20 Sitzungen las sich wie zwei mit 13 und 7**.
- Umgekehrt wurde die angesetzte Spanne auf drei verschiedenen Kursniveaus angewandt und vom
  Prozentschlüssel zu **einer** Zeile verschmolzen.

Schlimmer noch: Ein frischer Spotkurs gegen dieselbe 30.-Juli-Spanne ergab den neuen
Schlüssel „2,26 %" und wäre am Übersampel-Wächter **vorbeigelaufen**, der genau diesen Tag
schon zwanzigmal abgelehnt hatte.

Der Schlüssel ist jetzt das **Hoch/Tief-Paar** — das ist die Beobachtung. Der Prozentwert ist
eine Zahl, die sich mitbewegt, wenn der Nenner sich bewegt.

**Korrigierte Zählung: drei beobachtete Handelstage**, nicht vier. Ich hatte nach Sitzung 54
„vier" gemeldet; der vierte existierte nur als Aufspaltungsartefakt.

| Tagesbild | Sitzungen | Gewinn | Anteil |
|---|---:|---:|---:|
| ANGESETZT 1,57 % | 21 | +779,33 € | 56,2 % |
| beobachtet 30.07. (4.028,77–4.120,16) | 20 | +514,03 € | 37,1 % |
| beobachtet 31.07. (4.069,83–4.111,19) | 12 | +91,77 € | 6,6 % |
| beobachtet 31.07. (4.021,07–4.111,81) | 1 | +1,76 € | 0,1 % |

An der Kernaussage ändert das nichts — sie wird schärfer: **93 % des Gewinns stammen aus
einer angesetzten Spanne und einem einzigen echten Handelstag.**

### Stand nach 57 Sitzungen (01.08.2026)

Vier Sitzungen später hat sich die Struktur **nicht** verbessert, und die Zahl, auf die es
ankommt, ist die letzte:

| | 53 Sitzungen | 57 Sitzungen |
|---|---:|---:|
| Endstand | 1.785,13 € | 1.799,24 € |
| beobachtete Handelstage | 3 | **3** |
| Anteil aus angesetzten Spannen | 56 % | **56 %** |
| **dieselbe Kette, nur beobachtete Tage** | — | **400 € → 926,49 €** |

Die letzte Zeile ist die ehrlichste Zahl des Projekts: Streicht man die Sitzungen, deren
Tagesspanne nie jemand nachgeschlagen hat, bleiben von 1.799 € noch **926 €** — bei
gleichen Sitzungen, gleicher Reihenfolge, gleichen Renditen. Reproduzierbar mit
`python -m metals paper --provenance`.

Und seit A21 kommt eine zweite Korrektur dazu, die in beiden Spalten oben noch nicht steckt:
Die Euro-Beträge sind mit einem **angenommenen** Wechselkurs von 1,08 gerechnet. Beim
EZB-Referenzkurs von 1,1476 sind es 5,9 % weniger — **1.716,82 €** statt 1.799,24 €.
Nachzurechnen mit `python -m metals paper --restate 1.1476`.

## Was das heißt — und was nicht

**Es heißt:** Die Maschinerie funktioniert. Die Regeln lesen tatsächlich Struktur aus dem
Chart, statt Buchhaltungsartefakte zu produzieren. Der Misch-Test bestätigt das von der
anderen Seite: zerstört man die Reihenfolge der Kerzen und lässt alles andere gleich, bleiben
**0 bis 26 %** der Kante übrig. Eine Strategie, deren Kante das Mischen überlebt, liest nicht
den Chart — diese tut es.

**Es heißt nicht, dass die Strategie auf echtem Gold Geld verdient.** Fünf Gründe, jeder
einzeln ausreichend:

### 1. Der Simulator enthält, wonach die Strategie sucht

`metals/simulate.py` wurde mit Volatilitätsclustern, Rundzahlen-Magnetismus und
Liquiditätsjagden gebaut, weil Gold diese Eigenschaften hat. Eine Strategie, die Tageshoch
und -tief liest, findet genau diese Struktur. **Struktur zu finden, die absichtlich
hineingelegt wurde, beweist nichts über echtes Gold.**

Die deutlichste Warnung liefert die Verteilung selbst: Ein Median von etwa +7,4 % pro Tag
verdoppelt ein Konto in neun Tagen. Das tut niemand. Die Zahl sagt nicht, dass der Bot gut
ist — sie sagt, dass der Markt zu leicht ist.

### 2. Ich habe 36-mal hingesehen

Bei 36 Auswertungen liegt die Chance, dass ein 95 %-Band irgendwann zufällig über der Null
steht, bei bis zu **84 %**, nicht bei 5 %.

Die Vorfestlegung mildert das — es wurde bei der festgelegten Stichprobengröße geurteilt und
nicht beim ersten günstigen Blick. Aber **sie ist keine saubere Vorregistrierung**: Als die
Zahl festgelegt wurde, waren bereits 155 Trades sichtbar. Ein wirklich sauberer Test legt die
Stichprobengröße fest, **bevor** irgendetwas gemessen wurde.

### 3. Die Kette wiederholt einen ungewöhnlich volatilen Tag

Die ersten elf Sitzungen liefen auf dem 30. Juli — einem FOMC-Tag mit 2,23 % Tagesspanne
gegen typische 1,57 %. Das hebt den Median um rund ein Viertel. Die späteren Sitzungen
benutzen die abgeleitete typische Spanne, aber die Stichprobe ist dadurch nicht homogen.

### 4. Zwei Kostenmodelle in einer Stichprobe

Sitzungen 1–9 rechneten mit Spread allein, ab Sitzung 10 mit Spread × 1,5 (Auditbefund A8).
Rund 6,5 % Unterschied im Erwartungswert. Streng genommen sind das zwei verschiedene Welten
in einer Zahl.

### 5. Der EA steigt anders aus

Was hier gemessen wird, ist der **Python-Ausstieg**: ein Ziel bei 1,0 R, ganze Position. Der
EA nimmt 60 % bei 0,5 R und lässt den Rest bis 2,5 R laufen — gemessen rund **20 % weniger**
Erwartungswert (Auditbefund A11). Die +0,198 R beschreiben nicht, was der EA täte.

## Und das Konto? +301,7 % sind weniger, als sie aussehen

Das Lot stand fest bei 0,01, der Kurs war über die ganze Kette derselbe. Der Gewinn einer
Sitzung **in Euro** konnte also gar nicht davon abhängen, wie viel auf dem Konto lag — nur
der Nenner änderte sich. Gemessen: absolute Bewegung ×0,90 bei ×2,07 Kontowachstum, die
Prozentzahl entsprechend ×0,42.

**Der größte Teil der 301,7 % stammt aus den Sitzungen, in denen das Konto am kleinsten war.**

Dazu die Zahl, die eine Schluss-zu-Schluss-Rechnung verstecken würde: Der größte Rückgang
**innerhalb** einer Sitzung war **23,1 %**, nicht die gemeldeten 8,0 %. Ein Margin Call
reagiert auf den Gleitwert.

## Was als Nächstes ein Urteil verdient

Nicht mehr Sitzungen auf dem Simulator. Die würden die Stichprobe vergrößern und dieselbe
Frage beantworten, die schon beantwortet ist: **Ja, die Strategie liest den Simulator.**

Was aussteht, ist der Backtest auf **echter Historie**:

```bash
python -m metals dayrange --file XAU_5m_data.csv --tz broker_gmt3 --equity 1000 --risk 1
```

Der Weg dahin steht in [DATENQUELLEN.md](./DATENQUELLEN.md), der Befehl läuft und ist
getestet ([PAPIER-LAUF.md](./PAPIER-LAUF.md)). Er braucht die heruntergeladene Datei und
damit einen PC.

**Und dann eine Demo-Phase**, deren Journal dieselbe Auswertung bekommt wie diese Kette —
mit derselben Statistik, denselben Warnungen und derselben Vorfestlegung. Diesmal
festgelegt, bevor der erste Trade läuft.

---

*Reproduzierbar: `python -m metals paper --verify` rechnet jede Sitzung aus ihren eigenen
Eingaben neu und prüft sie gegen das Journal. Stand: 36 Sitzungen, keine Abweichung.*

---

## Nachprüfung bei 361 Trades

Das Urteil oben wurde bei den vorher festgelegten ~300 Trades gefällt (Sitzung 36). Seither
sind 59 Trades dazugekommen — **überwiegend am ruhigeren 31. Juli** (1,01 % Tagesspanne
statt 2,23 %), also unter Bedingungen, unter denen die Strategie nachweislich schlechter
abschneidet.

| | bei 302 Trades | bei 361 Trades |
|---|---:|---:|
| Trefferquote | 61,3 % | 61,5 % |
| Erwartungswert | +0,198 R | **+0,191 R** |
| 95 %-Band | +0,098 bis +0,297 R | **+0,101 bis +0,281 R** |

**Die Schätzung bewegt sich kaum**, das Band wird etwas schmaler. Das ist die erwartete
Entwicklung, wenn zusätzliche Daten aus derselben Grundgesamtheit kommen — und es ist
mildernd, weil die neuen Trades aus einem *ungünstigeren* Regime stammen und den Wert
trotzdem kaum gedrückt haben.

**Was das belegt:** dass die Messung stabil ist. Eine Zahl, die bei jedem Nachschlagen
irgendwo anders steht, wäre ein Warnsignal gewesen; diese tut es nicht.

**Was es nicht belegt:** irgendetwas über echtes Gold. Alle fünf Gründe oben gelten
unverändert. Der Mehrfachvergleichs-Einwand wird sogar **schlimmer**: Bei inzwischen 44
Auswertungen liegt die Chance, dass ein 95-%-Band irgendwann zufällig über der Null steht,
bei bis zu **90 %**. Die Vorfestlegung bei 300 Trades bleibt das einzige, was diesen Einwand
mildert — und sie war, wie oben gesagt, keine saubere Vorregistrierung.

---

## Nachtrag: Auf welchem Parameter die Kante tatsächlich steht

Grund 1 oben sagt, der Simulator enthalte die Struktur, die die Strategie sucht. Das ist
richtig, aber vage. Inzwischen ist es **genau benannt**.

`metals/simulate.py` hat einen Parameter `MarketParams.reversion = 0.002` — eine eingebaute
Rückkehr des Kurses zu einem langsamen Anker. Die Strategie kauft am Rand der Tagesspanne
und verkauft Richtung Mitte. Das ist exakt die Bewegung, die dieser Parameter erzeugt.

Also die naheliegende Frage: Was bleibt, wenn man ihn abdreht?

| Rückkehr zur Mitte | Drift | Trefferquote | Erwartungswert | Rendite (Median) |
|---:|---:|---:|---:|---:|
| **0,0020** (Standard) | 0 | 57,9 % | **+0,144 R** | +9,06 % |
| 0,0020 | leichter Trend | 55,0 % | +0,077 R | +7,40 % |
| 0,0005 | 0 | 51,0 % | +0,048 R | +1,41 % |
| 0,0005 | leichter Trend | 48,2 % | −0,001 R | +0,59 % |
| **0,0000** | **0** | 48,3 % | **+0,021 R** | +0,30 % |
| 0,0000 | leichter Trend | 44,5 % | **−0,054 R** | −2,91 % |

**Ohne diesen einen Parameter fallen rund 85 % der gemessenen Kante weg** — bei völlig
unverändertem Drift. Mit leichtem Trend dazu wird sie negativ.

Das ist keine Nebenbemerkung, sondern der Kern:

> Der Erwartungswert von +0,19 R, den der Papier-Lauf ausweist, steht fast vollständig auf
> **einer Zeile im Marktgenerator**. Nicht auf einer Eigenschaft von Gold — auf einer
> Annahme über Gold, die jemand hineingeschrieben hat, weil Gold sie *vermutlich* hat.

Ob echtes Gold innerhalb des Tages in dieser Stärke zur Mitte zurückkehrt, ist eine
empirische Frage, und sie ist hier nicht beantwortet. **Genau das entscheidet der Backtest
auf echter Historie** — und damit ist jetzt auch klar, worauf man dort schauen muss: nicht
auf die Trefferquote, sondern darauf, ob die Kante überhaupt existiert, wenn niemand sie in
den Datengenerator gelegt hat.

Der Befund bestätigt nebenbei die Fachpresse-Behauptung C13/C14: „Gold-EAs funktionieren,
bis der Markt trendet." Die Zeile mit Trend und ohne Rückkehr zur Mitte ist genau dieser
Fall — und sie ist die einzige mit negativem Erwartungswert.
