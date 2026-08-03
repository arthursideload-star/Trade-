# Obsidian-Tresor für den Gold-Bot

Ein fertiger Obsidian-Tresor. **Keine Plugins nötig** — alles läuft mit den Kernfunktionen,
die Obsidian mitbringt.

## Öffnen

1. [obsidian.md](https://obsidian.md) herunterladen, installieren
2. **Open folder as vault** wählen
3. Diesen Ordner (`obsidian/`) auswählen
4. Mit [[START HIER]] anfangen

Tägliche Notizen und Vorlagen sind bereits eingestellt: `Strg+P` →
*Daily note: Open today's daily note* legt eine Tagesnotiz aus der richtigen Vorlage an.

## Was das Ding soll — und was ausdrücklich nicht

**Soll:** festhalten, was du entschieden und beobachtet hast. Das ist genau das, was kein
Befehl je rechnen kann und was in drei Monaten wertvoll ist.

**Soll nicht:** Kennzahlen spiegeln. Der Grund dafür ist gemessen und steht in
[[Warum hier keine Zahlen stehen]] — kurz: Dieses Projekt hat achtundzwanzig Auditbefunde,
und ein wiederkehrendes Muster darin ist eine Zahl, die in Fließtext kopiert wurde und dort
alt geworden ist, ohne dass es jemandem auffiel. Ein hübscher Tresor voller Kennzahlen ist
dieselbe Falle mit besserer Typografie.

Zahlen holst du dir, wenn du sie brauchst:

```bash
python -m metals paper --review     # was gut war, was schlecht war
python -m metals journal            # was der EA getan hat
python -m metals stop --equity 400  # darf ich gerade handeln?
```

## Der Trade-Ordner füllt sich selbst

`05-Trades/` ist der Grund, warum dieser Tresor mehr ist als ein Notizbuch. Jeder
abgeschlossene Trade des EA bekommt eine eigene Notiz:

```bash
python -m metals vault --journal GoldScalpAssistant.csv
```

Mit Einstieg, Stop, Ziel, Ausstiegsgrund, Haltedauer, **Spread beim Einstieg** und Ergebnis
in R — als durchsuchbare, verlinkbare Notiz statt als CSV-Zeile.

**Deine eigenen Notizen bleiben erhalten.** Jede Trade-Notiz hat einen Block
*„Was ich dazu weiß"*. Der Export liest ihn vor dem Überschreiben aus und setzt ihn danach
wieder ein — du kannst also jede Woche gefahrlos neu exportieren.

Damit lässt sich nach dreißig Trades fragen: *Welche sind am Stop gestorben und hatten
gleichzeitig einen Spread über 0,40 $/oz?* Aus Fehlern lernen setzt voraus, dass man sie
wiederfindet.

## Aufbau

| Ordner | Inhalt |
|---|---|
| `00-Start` | Einstieg |
| `01-Strategie` | **Was der Bot macht** und was noch offen ist |
| `02-Regeln` | Die harten Grenzen und warum es sie gibt |
| `03-Wissen` | Deine eigenen Erkenntnisse, nicht die aus `docs/` |
| `04-Handelstage` | Eine Notiz je Tag — auch an Tagen ohne Trade |
| `05-Trades` | **Füllt sich selbst** aus dem Journal des EA |
| `06-Entscheidungen` | Warum etwas so ist, wie es ist |
| `90-Vorlagen` | Vorlagen für Handelstag, Wochenrückblick, Entscheidung |

## Wenn du ihn woanders haben willst

Der Ordner ist selbstständig. Kopier ihn wohin du willst — nach `Dokumente`, in eine
Cloud, egal. Nur dann bekommt er keine Updates mehr aus dem Repo, was für einen Tresor mit
persönlichen Notizen genau richtig ist.
