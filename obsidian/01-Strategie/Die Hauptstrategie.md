# Die Hauptstrategie — Tagesspanne

Das ist **die** Strategie des Projekts. Alles andere im Repo dient dazu, sie zu messen
oder davor zu schützen.

## In einem Absatz

Der Bot schaut auf die **Spanne des laufenden Tages** — Hoch und Tief, seit dem
Broker-Rollover. Steht der Kurs im unteren oder oberen Drittel dieser Spanne **und** stimmen
die letzten Kerzen in dieselbe Richtung, sagt er eine Bewegung vorher. Er nimmt **die Hälfte**
dieser vorhergesagten Bewegung als Ziel. Geht es in die Gegenrichtung, schließt ein Stop.

Code: `metals/dayrange.py` · im EA als Setup **„DR"**

## Die drei Zahlen, die sie ausmachen

| Regler | Wert | Was er tut |
|---|---|---|
| `edge_fraction` | 0,30 | Wie nah am Rand der Tagesspanne der Kurs stehen muss — unteres/oberes Drittel |
| `take_fraction` | 0,5 | Ziel bei der **Hälfte** der vorhergesagten Bewegung |
| `stop_fraction` | — | Stop als Anteil derselben Bewegung. **Der eine Regler, der zählt** |

**Warum die Hälfte keine Kleinigkeit ist:** Der Bot hat öfter recht mit der *Richtung* als
mit der *Entfernung*. Ein halbes Ziel wird viel häufiger erreicht als ein ganzes. Das kauft
eine höhere Trefferquote für weniger Ertrag je Trade — ein echter Tausch, kein Geschenk.

## Was gemessen wurde — und was das wert ist

Auf dem Simulator: +0,17 bis +0,20 R je Trade, Band über der Null (Stand 01.08.2026,
`paper --review`).

**Diese Zahl ist im Wesentlichen die Ablesung eines Simulator-Parameters.** Schaltet man
`MarketParams.reversion` ab — eine Rechenschutzplanke, die verhindern soll, dass erzeugte
Kurse ins Absurde laufen —, fällt die Erwartung auf +0,007 R mit einem Band über der Null.
Ohne alle erzeugten Merkmale verliert die Strategie ihren eigenen Spread.

Nachrechnen: `python -m metals persistence --ablate` · Befund A27 in `docs/REPO-AUDIT.md`

**Das heißt nicht, dass sie an echtem Gold scheitert. Es heißt, dass der Simulator die Frage
nicht beantworten kann.** Siehe [[Was noch offen ist]].

## Die Struktur der Kante — und warum sie zerbrechlich ist

Gemessen über 469 Trades (Stand 01.08.2026, `paper --review`):

| | |
|---|---|
| Gewinner im Mittel | +0,83 R |
| Verlierer im Mittel | −0,82 R |
| **Payoff-Verhältnis** | **1,01** |
| Break-even bei | 49,8 % Trefferquote |
| Beobachtete Trefferquote | 60,3 % |
| **Luft nach unten** | **10,6 Prozentpunkte** |

Gewinner und Verlierer sind **gleich groß**. Damit ist die Trefferquote der *ganze* Vorteil,
und es gibt nichts, was einen Rückgang abfedert. Fällt sie um 10,6 Punkte, ist der
Erwartungswert null — nicht halbiert, null.

## Was nicht die Hauptstrategie ist

**Die Scalping-Setups S1–S6.** Der EA handelt sie standardmäßig, die Tagesspanne-Strategie
ist bei ihm **ausgeschaltet** (`InpUseDayRange`). Das zu verwechseln ist der naheliegendste
Fehler im ganzen Projekt — `metals verdict` misst deshalb beide getrennt und nummeriert sie.

Genauer: der EA handelt **S2, S4 und S5** — nicht S1, obwohl S1 im Simulator mit Abstand am
häufigsten auslöst. Bis zum 04.08.2026 waren davon zwei faktisch tot: S2 konnte
konstruktionsbedingt nie auslösen, S5 fiel vollständig durch den Konfidenzfilter. Behoben,
nachzulesen als A31–A33 in `docs/REPO-AUDIT.md`.

**Was daraus für dieses Blatt folgt:** Jede Zahl über S2 oder S5, die vor diesem Datum
entstanden ist, beschreibt eine leere Menge. Nicht „ungenau" — leer. Was die beiden Setups
verdienen, ist eine offene Frage, siehe [[Was noch offen ist]].

Siehe auch: [[Die Regeln]] · [[Was noch offen ist]] · [[START HIER]]
