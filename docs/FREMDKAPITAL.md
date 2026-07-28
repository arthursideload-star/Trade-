# Fremdkapital-Challenges und KI-Bots — was davon stimmt

Einordnung von zwei Sachen, die im Juli 2026 aufkamen: einem Seminar über
„KI-Trading mit Fremdkapital" und einem Instagram-Reel über LLM-Agenten am Broker.

Beides enthält Wahres. Das Wahre ist aber jeweils nicht das, was verkauft wird.

---

## Teil 1 — Das Fremdkapital-Seminar

### Was gesagt wird

Wörtlich aus dem Transkript der ersten zehn Minuten:

> „Du steckst kein eigenes Kapital ins Trading mehr, man nutzt Fremdkapital."
>
> „Du kannst dein eigenes Geld dann nicht verlieren. Du hast auch keine
> Nachschusspflicht."
>
> „Es ist ein vollfinanziertes und vollversichertes Kapital."
>
> „98% fallen bei diesen Prüfungen durch."

### Der Satz, der nicht vorkommt

**Die Challenge kostet eine Gebühr.** In zehn Minuten Verkaufsgespräch fällt das
Wort nicht ein einziges Mal.

Das ist der ganze Punkt. „Ohne eigenes Risiko" ist wahr für das *fiktive* Konto —
die 50.000 oder 200.000 sind Demogeld, das kann man nicht verlieren, weil es nie
einem gehört hat. Es ist falsch für **dein** Geld: Die Gebühr ist deine, du zahlst
sie vorher, und sie ist weg, wenn du eine Grenze reißt.

Das Geschäftsmodell dieser Anbieter besteht in erheblichem Teil genau daraus.

### Die 98 % — und was sie wirklich bedeuten

Das Seminar nennt die Durchfallquote als Grund, das Produkt zu kaufen. Dieselbe
Quote **ist** aber die Einnahmequelle des Verkäufers. Wer 98 % Durchfall als
Verkaufsargument benutzt, verkauft ein Los, keine Ausbildung.

Veröffentlichte Branchenzahlen (Stand 2025/26, Anbieter- und Aggregatordaten, keine
geprüften Statistiken):

| Kennzahl | Wert |
|---|---|
| Bestehensquote der Prüfung | 5–10 % (FTMO nennt 9–10 %) |
| Käufer, die **jemals eine Auszahlung** erhalten | **≈ 7 %** (FPFX, >300.000 Konten) |
| Durchschnittliche Versuche bis zum Bestehen | ≈ 3 |
| Typische Gebühren für ein 100k-Konto bis zum Bestehen | > 1.600 $ |
| Häufigste Reißgründe | nachziehende Verlustschwelle, Konsistenzregel |

93 von 100 Käufern sehen also nie eine Auszahlung. Das ist die Zahl, die der Satz
„du kannst dein eigenes Geld nicht verlieren" verdeckt.

### Nachrechnen statt glauben

```bash
python -m metals challenge --account 100000 --fee 500 --programm
```

Rechnet den ganzen Weg: Phase 1, Phase 2, finanziertes Konto. Standardannahme ist
**keine Kante** — die Trefferquote, bei der die Auszahlungsstruktur des Projekts
exakt null ergibt — plus realistische Handelskosten.

Ergebnis bei 100.000 Konto und 500 Gebühr: Phase 1 bestehen rund 25 %, beide Phasen
rund 12 %, Erwartungswert **negativ**.

Eigene Zahlen einsetzen:

```bash
python -m metals challenge --programm --win-rate 55 --win-r 1.3 --cost 0.05
```

### Zwei Dinge, die beim Bauen dieses Rechners herauskamen

**1. Ohne Handelskosten wäre eine Challenge sogar bei Trefferquote null leicht
positiv.** Das war eine Überraschung und es ist kein Fehler: Der Verlust ist bei
der Verlustschwelle gedeckelt, die Auszahlungen sind es nicht. Das ist eine echte
Freikarte — und genau deshalb arbeiten die Anbieter mit **nachziehenden**
Verlustschwellen und Konsistenzregeln. Der Spread allein kippt die Rechnung ins
Minus. Er ist der Posten, den kein Werbevideo nennt.

**2. Bestehen ist keine Auszahlung.** Die Evaluierung läuft auf einem Demokonto.
Der Gewinn darin wird nicht ausgezahlt, er schaltet die nächste Stufe frei. Eine
Rechnung, die den Phase-1-Gewinn als Einkommen verbucht, kommt auf ein positives
Ergebnis — das war der erste Fehler in unserem eigenen Modell und ist im Code als
Test festgenagelt.

### „Die KI hat keine Emotionen" — stimmt, hilft aber nicht

Das Argument im Seminar: Menschen scheitern an Emotionen, die KI hat keine, also
besteht die KI.

Der Trugschluss steckt im letzten Schritt. Emotionslosigkeit beseitigt eine
*Fehlerquelle*, sie erzeugt keine *Kante*. Ein Bot, der sich perfekt an Regeln hält,
verändert die Streuung der Ergebnisse — nicht ihr Vorzeichen. Ohne positiven
Erwartungswert ist das Konto ein Zufallspfad, und ein Zufallspfad trifft die nähere
Schranke häufiger als die fernere.

Das ist in der Simulation direkt sichtbar: perfekte Regeltreue unterstellt, keine
Kante, und die Bestehensquote fällt trotzdem auf ein Viertel.

### Für dieses Projekt konkret

- Eine Challenge kostet mehr als das gesamte verfügbare Kapital von 55 €.
- Der eigene Bot hat **keinen nachgewiesenen positiven Erwartungswert**
  ([BACKTEST-ERGEBNISSE.md](./BACKTEST-ERGEBNISSE.md)).
- Für den Nachweis bräuchte es rund 385 Trades ([LERNEN.md](./LERNEN.md)).

Eine Challenge zu kaufen, bevor diese 385 Trades gelaufen sind, heißt: eine Gebühr
auf eine Kante setzen, von der man nicht weiß, ob es sie gibt.

---

## Teil 2 — Das Reel: LLM-Agenten am Broker

Inhaltlich deutlich seriöser. Es zeigt drei Dinge:

**1. Ein Paper** (ICLR 2026, FinAI-Workshop) über ein GNN-plus-RL-Modell, dessen
Befund ist, dass das Verbergen der Aktiennamen die Performance verändert. Echte
Forschung, kein Verkauf.

**2. STOCKBENCH** — ein Benchmark, der LLM-Agenten über 82 Handelstage auf echten
Marktdaten nach dem Wissens-Stichtag testet. Das Ergebnis ist gemischt: Die
Modelle schlagen Kaufen-und-Halten nicht durchgängig, und der Befund der Autoren
lautet sinngemäß, dass gutes Finanzwissen nicht automatisch gutes Handeln ergibt.

> 82 Handelstage sind übrigens dieselbe Stichprobenfalle wie überall sonst hier:
> zu wenig, um die Frage zu entscheiden. Auch bei akademischen Benchmarks.

**3. Broker-MCPs** (Alpaca, Interactive Brokers) mit dem Satz: *„any of these can
hold your brokerage keys."*

### Der Satz, an dem man hängenbleiben sollte

Einem autonomen Agenten die Broker-Zugangsdaten zu geben ist technisch möglich und
war noch nie einfacher. Was dabei fehlt, ist genau das, was dieses Projekt gebaut
hat: eine Ebene, die **nein** sagt. Positionsgröße aus dem Stop statt aus dem
Bauchgefühl, ein Tagesverlustlimit das greift, ein Spread-Tor, eine Ablehnung wenn
das Konto zu klein ist.

Ein LLM ohne diese Ebene ist kein Trading-System, sondern ein sehr überzeugter
Praktikant mit Kontovollmacht.

### Was daran brauchbar ist

**Alpaca bietet kostenloses Paper-Trading** mit MCP-Anbindung. Das ist ein echter,
kostenloser Weg, einen Agenten gegen den Markt laufen zu lassen, ohne Geld zu
riskieren — und deutlich einfacher als der VPS-Weg.

Zwei Einschränkungen: Es sind US-Aktien und Krypto, **kein XAUUSD-CFD**. Und für
den Live-Betrieb bräuchte es dieselbe Risikoebene wie der EA, sonst gilt der Absatz
darüber.

---

## Quellen

Getrennt nach Verlässlichkeit.

**Akademisch (begutachtet oder Preprint):**
- StockBench: *Can LLM Agents Trade Stocks Profitably In Real-world Markets?*
  — [arxiv.org/abs/2510.02209](https://arxiv.org/abs/2510.02209)

**Branchen- und Anbieterzahlen (nicht geprüft, teils Eigeninteresse):**
- [QuantVPS — Prop Firm Statistics 2025](https://www.quantvps.com/blog/prop-firm-statistics-2025)
- [FunderPro — Prop Trading Pass Rates in 2025](https://funderpro.com/blog/prop-trading-pass-rates-in-2025-what-the-data-really-shows/)
- [Damn Prop Firms — Evaluation Pass Rates: Reality Check](https://damnpropfirms.com/trading-guides/prop-firm-evaluation-pass-rates-statistics-reality-check/)
- [Apex Trader Funding — What Percentage of Traders Pass?](https://apextraderfunding.com/resources/prop-trading/what-percentage-of-traders-pass-prop-firm-challenges/)

**Zur Grenze von Chart-Screenshots als KI-Eingabe:**
- [ChartSnipe — Best AI Chart Screenshot Analysis Tools Tested](https://chartsnipe.com/blog/best-ai-chart-screenshot-analysis-tools)

Die Anbieterzahlen sind mit Vorsicht zu lesen — eine Firma, die Challenges verkauft,
hat ein Interesse an ihrer eigenen Bestehensquote. Sie zeigen hier trotzdem alle in
dieselbe Richtung, und in dieselbe wie die Simulation.
