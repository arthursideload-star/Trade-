# Plattformvergleich: MetaTrader 5 vs. Krypto-Börse

Entscheidungsgrundlage für die Frage "MT5 + Eigenbau" oder "Krypto + Freqtrade".
Stand: 2026-07-25

Randbedingungen aus den bisherigen Entscheidungen: **Startkapital 30 €**, **kurze Haltedauern,
mehrmals täglich**, **24/7-Betrieb**, Kapital soll stufenweise wachsen.

---

## 1. Das K.-o.-Kriterium: Geht 30 € überhaupt?

### MetaTrader 5 (Forex/CFD)

Die kleinste handelbare Einheit ist **0,01 Lot (Micro Lot) = 1.000 Einheiten**. Bei EUR/USD um
1,09 entspricht das einem Positionswert von rund **1.090 $**.

Unter der ESMA-Regulierung liegt der maximale Hebel für Privatkunden bei Hauptwährungspaaren
bei **1:30**. Daraus folgt die benötigte Margin:

```
Margin = (0,01 × 100.000 × 1,09) / 30 = 36,33 $ ≈ 33 €
```

**Ergebnis: 33 € Margin bei 30 € Kontoguthaben. Die kleinstmögliche Position ist mit diesem
Konto nicht eröffnungsfähig.**

Und selbst wenn es knapp reichen würde, wäre es unbrauchbar: Die gesamte Kontodeckung läge als
Margin gebunden, und der erste Pip gegen die Position löst einen Margin Call aus.

**Was MT5 realistisch bräuchte:**

| Posten | Betrag |
|---|---|
| Margin für 0,01 Lot | ~33 € |
| Freies Kapital als Puffer | mindestens das Doppelte |
| Damit 1 % Risiko pro Trade bei 10–20 Pip Stop ($1–2 Risiko) möglich ist | Konto ≥ 100–200 $ |
| **Praktische Untergrenze** | **300–500 €** |

Ausweg wären Anbieter außerhalb der EU-Regulierung mit Hebel 1:500 oder sogenannte Cent-Konten.
Genau dort sitzen aber die Anbieter ohne Aufsicht — das ist die Ecke, aus der die EasyTrading-App
kommt. Das ist kein gangbarer Weg.

### Krypto Spot (Binance/Bybit)

Die Mindestordergröße wird über den `MIN_NOTIONAL`-Filter geregelt und liegt bei Binance Spot
bei **5 USDT**.

Mit 30 € (≈ 32 $) sind damit rechnerisch bis zu 6 Positionen möglich, praktisch sinnvoll 2–3.
Es gibt keine Margin-Anforderung, weil ohne Hebel gehandelt wird.

**Ergebnis: 30 € funktionieren. Ohne Einschränkung.**

---

## 2. Kosten pro Trade — der entscheidende Faktor bei kurzen Trades

### Die Zahlen

| Plattform / Kontotyp | Kosten pro Roundtrip | Bemerkung |
|---|---|---|
| MT5 Raw/ECN-Konto | ~0,004 % vom Positionswert | 0,1 Pip Spread + ~3,50 $ Kommission je Standardlot; bei 0,01 Lot also ~0,045 $ auf 1.090 $ |
| MT5 Standard-Konto | ~0,01 % | ~1,0 Pip Spread, keine Kommission |
| **Krypto Spot**, Maker | **0,15–0,20 %** | 0,075–0,10 % je Seite |
| **Krypto Perpetual**, Maker | **0,04 %** | 0,02 % je Seite |
| Krypto Perpetual, Taker | 0,10 % | 0,05 % je Seite |

Auf den Positionswert bezogen ist Forex **deutlich** günstiger. Das ist allerdings ein
Scheinvorteil: Der niedrige Prozentsatz gilt für einen gehebelten Positionswert von 1.090 $,
den ein 30-€-Konto gar nicht tragen darf.

### Was das für "mehrmals täglich" bedeutet

Die für dieses Projekt wichtigste Rechnung. Jährliche Kostenlast bei 250 Handelstagen:

| Trades pro Tag | Trades/Jahr | Spot Maker (0,16 %) | Perp Maker (0,05 %) |
|---|---|---|---|
| 1 | 250 | 40 % p. a. | 12,5 % p. a. |
| 2 | 500 | 80 % p. a. | 25 % p. a. |
| 3 | 750 | 120 % p. a. | 37,5 % p. a. |
| 5 | 1.250 | **200 % p. a.** | 62,5 % p. a. |
| 10 | 2.500 | 400 % p. a. | 125 % p. a. |

**Die Schlussfolgerung ist unbequem, aber sie steht:** Auf Krypto **Spot** ist "mehrmals täglich"
rechnerisch nicht darstellbar. Bei 5 Trades am Tag müsstest du 200 % Bruttorendite erwirtschaften,
nur um die Gebühren zu bezahlen.

**Perpetual Futures mit Maker-Orders sind Faktor 4 günstiger** und machen den Stil handelbar —
bei 1–3 Trades pro Tag, nicht bei zehn.

### Der Vorschlag: Perpetuals mit 1× Hebel

Das klingt widersprüchlich zur bisherigen Empfehlung "kein Hebel", ist es aber nicht:

- Perpetual-Kontrakte haben die **Futures-Gebührenstruktur** (0,02 % Maker statt 0,10 %)
- Bei **1× Hebel** entspricht das Risiko exakt einer Spot-Position — der Liquidationspreis liegt
  rund 100 % entfernt und ist praktisch unerreichbar
- Funding fällt alle 8 Stunden an; bei Haltedauern von Minuten bis wenigen Stunden zahlst du
  meist gar keines

Du bekommst also die günstige Gebührenstruktur ohne das Liquidationsrisiko. Der Hebel wird im
Risk-Layer hart auf 1× begrenzt, nicht in der Börsen-Oberfläche.

---

## 3. Technischer Betrieb — der zweite harte Unterschied

| Kriterium | MT5 | Krypto |
|---|---|---|
| **Python-Anbindung** | Paket `MetaTrader5` | `ccxt` + native WebSockets |
| **Betriebssystem** | ⚠️ **Nur Windows** | Linux |
| **Was laufen muss** | MT5-Terminal als GUI-Anwendung, dauerhaft | Ein Docker-Container |
| **VPS-Kosten** | Windows-VPS ~15–25 €/Monat | Linux-VPS ~5 €/Monat |
| **Handelszeiten** | 24/5 — Wochenende geschlossen | **24/7** |
| **Historische Daten** | Vom Broker, oft lückenhaft und broker-spezifisch | Vollständig von der Börse, kostenlos |
| **Backtest-Framework** | Selbst bauen (~3 Wochen) | Freqtrade fertig |
| **Testumgebung** | Demo-Konto | Testnet + Freqtrade Dry-Run |

Der Windows-Zwang ist für ein 24/7-System ein ernsthafter Nachteil: Das offizielle
`MetaTrader5`-Python-Paket läuft ausschließlich unter Windows, und das MT5-Terminal muss dabei
als laufende Anwendung aktiv sein. Für unbeaufsichtigten Dauerbetrieb ist das eine deutlich
fragilere Konstruktion als ein Linux-Container mit Healthcheck und automatischem Neustart.

Dazu kommt: Dein erklärtes Ziel ist **24/7**. Forex ruht am Wochenende. Das sind ~28 % der Zeit
ohne Handelsmöglichkeit.

---

## 4. Gesamtbewertung

| Kriterium | Gewicht | MT5 | Krypto + Freqtrade |
|---|---|---|---|
| Mit 30 € handelbar | 🔴 K.-o. | ❌ Nein (Margin 33 €) | ✅ Ja |
| 24/7-Betrieb | hoch | ⚠️ 24/5 | ✅ 24/7 |
| Betrieb auf Linux-VPS | hoch | ❌ Windows nötig | ✅ |
| Kosten bei kurzen Trades | hoch | ✅ sehr günstig | ⚠️ nur als Perp-Maker tragbar |
| Fertiges Backtesting | mittel | ❌ Eigenbau | ✅ Freqtrade |
| Datenqualität/-verfügbarkeit | mittel | ⚠️ broker-abhängig | ✅ vollständig, kostenlos |
| Entwicklungszeit bis lauffähig | mittel | ~3 Wochen länger | ✅ schneller |

## 5. Empfehlung

**Krypto + Freqtrade, gehandelt als USDT-Perpetuals mit hart begrenztem 1× Hebel.**

Begründung in der Reihenfolge ihrer Wichtigkeit:

1. **MT5 ist mit 30 € nicht handelbar.** Die kleinstmögliche Position erfordert mehr Margin, als
   auf dem Konto liegt. Das ist kein Nachteil, den man abwägen könnte — es ist ein Ausschluss.
2. **24/7 statt 24/5**, entsprechend dem erklärten Ziel.
3. **Linux-Docker statt Windows-GUI** — der Unterschied zwischen einem System, das man
   unbeaufsichtigt laufen lassen kann, und einem, das man beaufsichtigen muss.
4. **Freqtrade spart mehrere Wochen** und bringt ein erprobtes Backtesting mit.
5. **Perpetual-Maker-Gebühren machen kurze Trades überhaupt erst tragbar** (0,04 % statt 0,20 %
   pro Roundtrip).

**MT5 bleibt eine Option für später.** Sobald das Konto bei 300–500 € liegt und das System sich
bewährt hat, ist eine zweite Instanz für Forex sinnvoll — Forex und Krypto sind schwach
korreliert, das wäre echte Diversifikation. Die Architektur wird so gebaut, dass der
Exchange-Adapter austauschbar bleibt.

---

## 6. Daraus folgende harte Vorgaben

| # | Vorgabe | Grund |
|---|---|---|
| V1 | **Post-Only-Limit-Orders sind Pflicht**, Market nur bei Stop-Auslösung | Faktor 2,5 bei den Gebühren (0,02 % vs. 0,05 % je Seite) |
| V2 | **Hebel hart auf 1× begrenzt** — im Code, nicht in der Börsenoberfläche | Perp-Gebühren ohne Liquidationsrisiko |
| V3 | **Maximal 3 Trades pro Tag und Symbol** | Ab 5 Trades/Tag übersteigt die Kostenlast jede realistische Rendite |
| V4 | **Mindest-Zielbewegung 0,5 %** (≈ 10× Roundtrip-Kosten) | Signale unterhalb dieser Schwelle sind nach Kosten wertlos |
| V5 | **Nicht-Ausführung von Post-Only-Orders muss der Backtest simulieren** | Sonst systematische Überschätzung |
| V6 | **Funding-Kosten werden mitgerechnet**, auch wenn selten fällig | Sonst Überraschung bei längeren Haltedauern |

---

## Quellen

- [MetaTrader 5 Margin Calculation — Retail Forex (offizielle Doku)](https://www.metatrader5.com/en/terminal/help/trading_advanced/margin_forex)
- [Margin Calculation Examples (Admiral Markets)](https://admiralmarkets.com/products/margin-calculation-examples)
- [MetaTrader 5 Lot Size Explained](https://hw.online/faq/metatrader-5-lot-size-explained-a-comprehensive-guide/)
- [MQL5 — Python Integration (offizielle Doku)](https://www.mql5.com/en/docs/python_metatrader5)
- [MetaTrader5 Python-Paket auf PyPI](https://pypi.org/project/MetaTrader5/5.0.47)
- [Binance Spot API — Filters (MIN_NOTIONAL)](https://developers.binance.com/docs/binance-spot-api-docs/filters)
- [Binance Spot Trading Rules (Binance Academy)](https://academy.binance.com/en/articles/binance-spot-trading-rules-a-comprehensive-guide)
- [Raw Spread vs Standard Account: Cost Analysis 2026](https://forexspreadcompare.com/artigos/raw-spread-vs-standard-account)
- [Forex Brokers with Lowest Spreads 2026](https://newyorkcityservers.com/blog/lowest-spread-forex-brokers-2026)
- [Crypto Exchange Fees Compared 2026](https://homecryptoinvest.com/articles/crypto-exchange-fees-2026.html)
