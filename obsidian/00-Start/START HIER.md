# START HIER

Das ist dein Trading-Tresor. Er hat **eine** Aufgabe, und es ist nicht die, die man
erwartet: Er soll festhalten, was du **entschieden und beobachtet** hast — nicht, was der
Bot gerechnet hat.

Der Grund steht in [[Warum hier keine Zahlen stehen]].

---

## Die drei Fragen, für die dieser Tresor da ist

1. **Was habe ich heute gesehen, das keine Zahl erfasst?** → [[10-Handelstage]]
2. **Warum habe ich das damals so entschieden?** → [[30-Entscheidungen]]
3. **Was weiß ich über Gold, das ich nicht nachschlagen will?** → [[20-Wissen]]

---

## Der tägliche Ablauf

**Vor dem Handeln** — ein Befehl, im Repo-Ordner:

```bash
python -m metals stop --equity <dein Kontostand>
```

Sagt er **AUFHÖREN**, ist der Tag vorbei. Nicht verhandeln. Notiz anlegen und zumachen.

**Nach dem Handeln** — neue Tagesnotiz aus [[Vorlage Handelstag]], zwei Minuten ausfüllen.

**Sonntags** — [[Vorlage Wochenrückblick]]. Die eine Frage, die zählt: *Habe ich meinen
Plan befolgt?* Nicht: *habe ich gewonnen?*

---

## Was wo liegt

| Ordner | Inhalt |
|---|---|
| `00-Start` | Diese Seite und die Grundregeln |
| `10-Handelstage` | Eine Notiz je Handelstag |
| `20-Wissen` | Was du über Gold gelernt hast, in deinen Worten |
| `30-Entscheidungen` | Warum etwas so ist, wie es ist |
| `90-Vorlagen` | Die Vorlagen zum Kopieren |

## Was **nicht** hier liegt

Alles, was gerechnet wird. Das steht im Repo und wird dort neu berechnet:

| Frage | Befehl |
|---|---|
| Darf ich gerade handeln? | `python -m metals stop --equity <k>` |
| Reicht mein Konto? | `python -m metals minimum XAUUSD --equity 400 --eur` |
| Was belegen meine Trades? | `python -m metals journal --file GoldScalpAssistant.csv` |
| Lohnt sich der Bot überhaupt? | `python -m metals verdict --file XAU_5m_data.csv --tz broker_gmt3` |
| Was war gut, was schlecht? | `python -m metals paper --review` |

---

## Die Regeln, die nicht verhandelbar sind

Sie stehen im Code, nicht in einer Einstellung — sie zu ändern kostet einen Commit.
Vollständig: `python -m metals rules`. Die sechs, die im Alltag greifen:

- **R1** Nie mehr als 1 % des Kontos je Trade riskieren
- **R2** Bei −3 % am Tag ist Schluss bis morgen
- **R2b** Bei +2 % am Tag auch — *für dich*, nicht für den Bot ([[Warum R2b nur für Menschen gilt]])
- **R4** Kein Einstieg 30 Minuten um eine wichtige Nachricht
- **R5** Kein Einstieg bei Rollover, tiefer Asienzeit, Freitagabend
- **R7** Kein Einstieg ohne vorher definierten Stop

Warum R4 und R5 keine Vorsicht, sondern Rechnen sind: [[Was der Spread zum falschen Zeitpunkt kostet]]
