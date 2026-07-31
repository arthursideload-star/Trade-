# Das Urteil an der vorher festgelegten Stichprobe

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
