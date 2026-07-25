---
name: forex-analysis
description: Berechnet die deterministischen Analysezahlen fuer ein Forex-Paar aus den Kerzen der forex-data-Skill — Indikatoren (EMA, RSI, MACD, ATR, ADX, Bollinger, Stochastik), Regime (Trend/Seitwaerts/Volatil), Support/Resistance-Level, Kerzenmuster am Level und Fehlausbruch-Signaturen. Verwenden, sobald ein Paar technisch bewertet werden soll, etwa nach "Analysiere EUR/USD", bevor eine Empfehlung entsteht. Rechnet nur, empfiehlt nicht — die Empfehlung baut forex-signal darauf auf.
---

# Forex-Analyse (deterministische Rechner)

Die "harten Zahlen" aus BOT-PLAN.md Abschnitt 2: reproduzierbar, getestet, nicht geraten.
Dieser Skill bewertet **nicht** und gibt **keine** Handelsrichtung aus — das ist Aufgabe von
`forex-signal` (Sprint B4), das auf dieser Ausgabe aufbaut.

## Wann dieser Skill greift

Immer wenn Indikatoren, Trend, Regime, Level oder Muster für ein Paar gebraucht werden.
Der Skill holt sich die Kerzen selbst über den forex-data-Client.

## Voraussetzungen

- Python 3.9+ (nur Standardbibliothek — kein `ta-lib`, keine Installation)
- `TWELVEDATA_API_KEY` gesetzt (für den Kerzenabruf, siehe forex-data)

## Aufruf

```bash
# Vollständige Analyse über alle vier Zeitebenen, JSON nach stdout
python skills/forex-analysis/scripts/analyze.py --symbol EUR/USD

# Nur eine Zeitebene
python skills/forex-analysis/scripts/analyze.py --symbol EUR/USD --interval 15min

# Lesbare Kurzfassung
python skills/forex-analysis/scripts/analyze.py --symbol EUR/USD --format text
```

## Was berechnet wird

| Baustein | Modul | Inhalt |
|---|---|---|
| **Indikatoren** | `indicators.py` | EMA 21/55/200, RSI(14), MACD(12,26,9), ATR(14), ADX(14) mit +DI/−DI, Bollinger(20,2), Stochastik |
| **Regime** | `regime.py` | Aufwärtstrend / Abwärtstrend / Seitwärts / Volatil nach der Tabelle in PLAN.md A5 |
| **Level** | `levels.py` | Swing-Hochs/Tiefs, Support/Resistance-Zonen, Pivot Points, Abstand des Kurses zum nächsten Level |
| **Muster** | `patterns.py` | Kerzenmuster (Hammer, Engulfing, Doji, Shooting Star …) — **nur am Level gewertet** (Teil III/XIV) |
| **Fehlausbruch** | `patterns.py` | Sweep eines Levels mit Rückschluss in die Range (Teil XVI.9/XVIII) |

## Wichtige Zusagen

- **Reihenfolge:** rechnet auf aufsteigenden Kerzen (älteste zuerst), wie forex-data sie liefert.
- **Fehlende Werte** sind `null`, nie eine erfundene `0` — "noch kein Wert" bleibt von "Wert ist null"
  unterscheidbar.
- **Wilder-Glättung** bei RSI, ATR und ADX, damit die Zahlen zu dem passen, was MT5 anzeigt.
- **Volumen:** Forex liefert keins. Volumenbasierte Aussagen entfallen und werden nicht ersetzt.

## Grenze

Muster werden nur gewertet, wenn sie **an einem Level** auftreten. Ein isolierter Hammer
mitten in der Range zählt nicht — genau diese Kontextregel unterscheidet ein Setup von Rauschen.

## Weiterführend

- `references/methodik.md` — Formeln, Regime-Schwellen, Musterdefinitionen, Quellenbezug zu TRADING-WISSEN.md
