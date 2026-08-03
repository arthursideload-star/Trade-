# START HIER

Dein Trading-Tresor. Er hat zwei Aufgaben:

1. **Die Strategie und die Regeln festhalten** — verbindlich, an einem Ort → [[Die Hauptstrategie]]
2. **Festhalten, was du entschieden und beobachtet hast** — das, was keine Zahl erfasst

Und seit dem Trade-Export eine dritte: **die Trades des Bots aufnehmen**, damit du sie
wiederfindest → [[05-Trades]]

---

## Was der Bot liest — und was nicht

Wichtig, damit keine falsche Erwartung entsteht:

| | liest diesen Tresor? |
|---|---|
| **Der EA in MetaTrader** | **Nein.** Er ist eine kompilierte `.mq5`-Datei, seine Regeln stehen in seinem Code |
| **Claude im Chat** (`/trade`) | Ja, wenn du ihm den Ordner gibst |
| **Du** | Ja, und das ist der Hauptzweck |

Der Weg zurück ist der wichtige und der funktioniert: **Alles, was der EA tut, landet als
Notiz hier** (`python -m metals vault`). Eine Änderung an [[Die Hauptstrategie]] ändert
dagegen nichts am Verhalten des EA — dafür braucht es eine Änderung im Repo und ein neues
Kompilieren.

---

## Die vier Fragen, für die es diesen Tresor gibt

| Frage | Wo |
|---|---|
| Was macht der Bot eigentlich? | [[Die Hauptstrategie]] |
| Was darf ich nicht tun? | [[Die Regeln]] |
| Was hat der Bot getan? | [[05-Trades]] → [[Alle Trades]] |
| Warum habe ich das damals so entschieden? | [[06-Entscheidungen]] |

---

## Der tägliche Ablauf

**Vor dem Handeln**, im Repo-Ordner:

```bash
python -m metals stop --equity <dein Kontostand>
```

Sagt er **AUFHÖREN**, ist der Tag vorbei. Nicht verhandeln.

**Nach dem Handeln:** neue Tagesnotiz aus [[Vorlage Handelstag]], zwei Minuten.

**Einmal pro Woche:**

```bash
python -m metals vault --journal GoldScalpAssistant.csv   # Trades in den Tresor
python -m metals journal --file GoldScalpAssistant.csv    # was das belegt
```

Dann [[Vorlage Wochenrückblick]]. Die eine Frage: *Habe ich meinen Plan befolgt?* — nicht:
*habe ich gewonnen?*

---

## Aufbau

| Ordner | Inhalt |
|---|---|
| `00-Start` | Diese Seite |
| `01-Strategie` | Was der Bot macht und was offen ist |
| `02-Regeln` | Die harten Grenzen und warum es sie gibt |
| `03-Wissen` | Deine eigenen Erkenntnisse über Gold |
| `04-Handelstage` | Eine Notiz je Tag |
| `05-Trades` | **Füllt sich selbst** aus dem Journal des EA |
| `06-Entscheidungen` | Warum etwas so ist, wie es ist |
| `90-Vorlagen` | Vorlagen zum Kopieren |

## Was hier bewusst nicht steht

Kennzahlen. Der Grund: [[Warum hier keine Zahlen stehen]]

Zahlen holst du dir per Befehl — die rechnen neu und können nicht veralten:

| Frage | Befehl |
|---|---|
| Darf ich gerade handeln? | `python -m metals stop --equity 400` |
| Reicht mein Konto? | `python -m metals minimum XAUUSD --equity 400 --eur` |
| Was belegen meine Trades? | `python -m metals journal --file GoldScalpAssistant.csv` |
| Lohnt der Bot überhaupt? | `python -m metals verdict --file XAU_5m_data.csv --tz broker_gmt3` |
| Was war gut, was schlecht? | `python -m metals paper --review` |
