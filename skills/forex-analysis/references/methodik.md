# Methodik der deterministischen Analyse

Formeln, Schwellen und Musterdefinitionen der forex-analysis-Skill, mit Bezug zur
Wissensbasis in `docs/TRADING-WISSEN.md`. Alles ist reine Standardbibliothek — kein `ta-lib`,
weil die C-Bibliothek in der interaktiven Claude-Sitzung nicht vorhanden wäre.

## Indikatoren (`indicators.py`)

| Indikator | Glättung | Bemerkung |
|---|---|---|
| SMA | — | gleitendes Fenster |
| EMA 21/55/200 | mit SMA geseedet | kein langer Startbias durch Roh-Seed |
| RSI(14) | Wilder | erster Wert bei Index = period |
| ATR(14) | Wilder | erste True Range = High−Low |
| ADX(14) + DI | Wilder | ADX ist die Wilder-Glättung von DX |
| MACD(12,26,9) | EMA | Signal-EMA läuft nur über den definierten Bereich |
| Bollinger(20,2) | SMA ± σ | Populations-Standardabweichung |
| Stochastik(14,3) | — | %K bei flachem Fenster undefiniert, nicht 50 |

**Grundregel:** Positionen ohne genug Historie sind `None`, nie eine erfundene `0`. „Noch kein
Wert" bleibt von „Wert ist null" unterscheidbar.

**Warum Wilder:** RSI, ATR und ADX sind von Wilder mit seiner eigenen Glättung definiert. Ein
gewöhnlicher EMA an dieser Stelle würde von den Zahlen abweichen, die MT5 und TradingView anzeigen.

## Regime (`regime.py`) — PLAN.md A5

| Regime | Kriterien | Erlaubte Richtung |
|---|---|---|
| Aufwärtstrend | ADX > 25 **und** EMA 21>55>200 | nur Long |
| Abwärtstrend | ADX > 25 **und** EMA 21<55<200 | nur Short |
| Seitwärts | ADX < 20, oder Trend-ADX bei gemischtem EMA-Fächer | beide, vorsichtig |
| Volatil | ATR > 1,5× seines 50er-Durchschnitts, ohne klaren Trend | kleinere Größe |

Ein sauberer Trend behält sein Label auch bei erhöhtem ATR — dann mit Hinweis „Größe reduzieren".
Die Schwellen stehen als Konstanten im Code, damit eine Änderung ein Commit ist.

## Level (`levels.py`)

1. **Swing-Punkte:** ein Bar ist Swing-Hoch, wenn sein High das Maximum von ±`window` Bars ist.
2. **Clustern:** nahe Swings (innerhalb `tolerance_pips`) werden zu einer Zone gemittelt; die Zahl
   der Berührungen (`touches`) ist die Bestätigung — dreimal getestet zählt mehr als drei Linien.
3. **Nächstes Level:** höchster Support unter dem Kurs, tiefster Widerstand darüber. Abstände in Pips.
4. **Pivot Points:** klassischer Floor-Trader-Pivot aus dem Vorbar.

Pip-Größe: 0,01 bei JPY-Paaren, sonst 0,0001.

## Muster (`patterns.py`) — Teil III/XIV

Erkannt werden: Hammer, Shooting Star, Doji, Bullish/Bearish Engulfing, Morning/Evening Star.

**Die Kontextregel ist das Entscheidende:** `patterns_at_level()` behält nur Muster, die **an einem
Level** sitzen. Ein bullisches Umkehrmuster wird an seinem Low geprüft (dort testete es den Support),
ein bärisches an seinem High. Ein isolierter Hammer mitten in der Range wird verworfen.

## Fehlausbruch (`patterns.py`) — Teil XVI.9/XVIII

Sweep mit Rückschluss: Das High durchsticht einen Widerstand um mindestens `sweep_pips`, schließt
aber wieder darunter (bärisch) — oder spiegelbildlich am Support (bullisch). Ein sauberer Ausbruch,
der jenseits des Levels **schließt**, ist ausdrücklich **kein** Fehlausbruch.

## Was fehlt

- **Volumen:** Forex liefert keins. Volumenbasierte Aussagen entfallen; im Signal-Score
  (forex-signal) wird das zugehörige Gewicht umverteilt, nicht mit Null gefüllt.
- **Divergenzen** (Preis vs. RSI/MACD): noch nicht umgesetzt, sinnvolle Erweiterung.
