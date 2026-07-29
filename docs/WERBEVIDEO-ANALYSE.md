# Das „40 € reichen"-Rechenfehler — und was im Werbevideo wirklich steht

Analyse zweier TikTok-Videos (29.07.2026) und eines Grok-Screenshots, die
zusammen den Eindruck erzeugten, 40 € genügten für den Handel mit 0,1 Lot Gold.

---

## 1. Die Videos sind Werbung, nicht Ergebnisse

Beide Videos tragen die Kennzeichnung **„Anzeige"** und bewerben die App
**XTrend Lite** aus dem App Store. Im Kleingedruckten steht wörtlich:

> *Your capital is at risk. Past performance is not indicative of future
> results. This is not investment advice.*

Das ist keine Aufzeichnung eines Nutzers, sondern eine bezahlte Anzeige des
Anbieters.

---

## 2. Der Rechenfehler im Screenshot

Der Grok-Screenshot rechnet:

> Position-Wert: 0,1 × 10 Unzen × 4.030 USD = **4.030 USD**
> Margin: 4.030 / 100 = **40,30 USD**

**Die Kontraktgröße stimmt nicht.** Bei XAUUSD ist 1 Lot = **100 Unzen**, nicht
10. Also:

| | Grok | Richtig |
|---|---:|---:|
| 0,1 Lot in Unzen | 1 | **10** |
| Positionswert bei 4.030 | 4.030 USD | **40.300 USD** |
| Margin bei 1:100 | 40,30 USD | **403 USD** |
| Margin bei 1:20 (EU-Recht) | — | **2.015 USD** |

**Faktor 10 zu klein.**

### Bewiesen mit den Zahlen aus dem Werbevideo selbst

Das Schöne: Die Anzeige widerlegt den Screenshot.

| Video | Position | Bewegung | Gewinn | daraus folgt |
|---|---|---:|---:|---|
| 1 | sell 0,05 · 5092,140 → 5091,514 | 0,626 USD/oz | 3,13 USD | 3,13 / 0,626 = **5 oz** → 1 Lot = 100 oz |
| 2 | buy 0,02 · 5091,736 → 5091,985 | 0,249 USD/oz | 0,50 USD | 0,50 / 0,249 = **2 oz** → 1 Lot = 100 oz |

Beide Videos bestätigen unabhängig: **1 Lot = 100 Unzen.**

### Der zweite Fehler: der Hebel

Der Screenshot behauptet, 1:100 sei „die maximale Leverage bei den meisten
regulierten Brokern in Deutschland/EU – ESMA-Regelung". Falsch: Die
ESMA-Produktinterventionsregeln setzen für **Gold 1:20** für Privatkunden.
1:100 gibt es dort nicht.

Beide Fehler multiplizieren sich: Faktor 10 × Faktor 5 = **50**. Genau der
Unterschied zwischen „40 € reichen" und „2.015 USD nötig".

---

## 3. Was im Video sonst noch nicht stimmt

**Der Goldpreis.** Die Anzeige zeigt XAUUSDm bei **5.092 USD/oz**. Die eigenen
MT5-Charts des Nutzers zeigten am 22.–27. Juli 2026 Kurse zwischen 4.059 und
4.177. Ein Sprung auf 5.092 innerhalb von zwei Tagen wäre +24 %. Das ist kein
realer Goldkurs.

**Die Margin.** Video 1 zeigt acht Positionen à 0,05 Lot — zusammen 40 Unzen,
also rund 203.000 USD Nominalwert — bei einer ausgewiesenen Margin von **0,23
USD**. Das entspräche einem Hebel von etwa 1:885.000. Bei keinem regulierten
Broker existiert das.

**Das zweite Video zeigt ein Minus.** Balance 101,15, Equity 99,08 — die
Kopfzeile weist **−2,07 USD** aus. Die Anzeige, die „richtig dick Geld" zeigen
soll, zeigt ein Konto im Verlust.

**Das Muster.** Acht identische Positionen zum praktisch selben Kurs, kein
sichtbarer Stop. Dasselbe Grid-Stapeln wie in der zuvor analysierten Anzeige.

---

## 4. Das Prinzip getestet — mit 100, 200 und 400 €

Nachgebaut: viele gleiche Positionen zu 0,02 Lot, Mini-Gewinnziel, kein Stop.
25 Märkte je Zeile, 10.000 Minutenkerzen.

| Konto | Hebel | Trefferquote | Median | Mittelwert | Stop-out | halbiert |
|---:|---|---:|---:|---:|---:|---:|
| 100 € | 1:20 | — | — | — | — | *kein Trade möglich* |
| 100 € | 1:500 | 95,2 % | **−92,6 %** | +865,6 % | 92 % | 80 % |
| 200 € | 1:20 | — | — | — | — | *kein Trade möglich* |
| 200 € | 1:500 | 97,8 % | **−96,5 %** | +627,3 % | 76 % | 68 % |
| 400 € | 1:20 | 99,5 % | +0,0 % | +0,4 % | 0 % | 0 % |
| 400 € | 1:500 | 99,2 % | +109,3 % | +575,0 % | 56 % | 48 % |

### Was da steht

**Bei legalem EU-Hebel handeln 100 € und 200 € überhaupt nicht.** Nicht
schlecht — gar nicht. 400 € handeln, verdienen aber praktisch nichts (+0,4 %),
weil die Position im Verhältnis zum Konto winzig ist.

**Der Hebel, der 40 € „reichen" lässt, ist genau der, der das Konto zerlegt.**
Bei 1:500 wird gehandelt — und der typische Durchlauf verliert 93 bis 97 %,
mit 76–92 % Broker-Stop-out.

**Trefferquote 95–99 % bei Median −93 %.** Das ist kein Widerspruch, sondern
dieselbe Struktur wie in allen bisherigen Analysen: Fast jeder Trade gewinnt
ein bisschen, der eine Verlierer nimmt alles.

**Mittelwert +865 % neben Median −93 %.** Der Mittelwert beschreibt die wenigen
Überlebenden. Der Median beschreibt dich.

---

## Fazit

Der Screenshot rechnet mit einer zehnfach zu kleinen Kontraktgröße und einem
fünffach zu hohen Hebel. 40 € reichen nicht für 0,1 Lot Gold — nötig sind bei
EU-Recht rund 2.000 USD.

Und selbst wenn man den Hebel bei einem Anbieter außerhalb der EU besorgt, wo
40 € formal genügen: Genau dieser Hebel führt in der Messung dazu, dass vier
von fünf Konten mindestens die Hälfte verlieren.
