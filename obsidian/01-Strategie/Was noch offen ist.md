# Was noch offen ist

Eine Liste, und der erste Punkt wiegt schwerer als alle anderen zusammen.

## 1. Der Backtest auf echter Historie

**Kein einziges Ergebnis dieses Projekts ist an echten Intraday-Golddaten geprüft.** Alles
Gemessene läuft auf `metals/simulate.py` — einer erzeugten Kursreihe, die dokumentierte
statistische Eigenschaften von Gold nachbildet, nicht Gold.

Was sich trotzdem überträgt, ist **Arithmetik**: Spread, Margin, Losgröße, Swap, und dass
eine Trefferquote keine Kante ist. Was sich **nicht** überträgt, sind Aussagen über
Verhalten: welche Session besser läuft, ob ein Filter hilft, wie hoch der Erwartungswert ist.

```bash
python -m metals verdict --file XAU_5m_data.csv --tz broker_gmt3 --equity 400
```

Fünf Prüfungen, eine Empfehlung im Klartext. Sie darf **NICHT INSTALLIEREN** sagen, und wenn
sie das tut, ist das ein Ergebnis und kein Rückschlag.

## 2. Ob der EA überhaupt kompiliert

Die Datei `mt5/Experts/GoldScalpAssistant.mq5` ist nie durch einen MQL5-Compiler gelaufen —
im Container gibt es keinen MetaEditor. Der erste Kompilierversuch am PC ist der erste echte
Test. Fehler dort sind normal und in Minuten behoben.

## 3. Es gibt nur eine Strategie-Familie

Der Bot setzt auf **Rückkehr** — Kurs am Rand, Bewegung zurück. Sagt der Varianztest auf
echten Daten „Bewegungen laufen weiter", steht das Projekt mit leeren Händen da, weil keine
Trend-Variante existiert.

## 4. Kein Währungsrisiko modelliert

Das Konto läuft in Euro, gehandelt wird in Dollar. In 57 Papier-Sitzungen wurde derselbe
Kurs auf beiden Seiten eingesetzt, also **null** Währungsrisiko. Real bewegt sich EUR/USD an
einem normalen Tag um 0,3–0,6 % — dieselbe Größenordnung wie das, was die Strategie an einem
Tag verdienen soll. Befund A21.

## 5. Der Spread muss jede Sitzung neu abgelesen werden

Er entscheidet in einer Tagessitzung über das **Vorzeichen** des Erwartungswerts. Deshalb
ist `--spread` im ganzen Projekt Pflicht und wird nirgends vorbelegt.
[[Was der Spread zum falschen Zeitpunkt kostet]]

## 6. Was S2 und S5 verdienen, ist ungemessen

Beide Setups liefen bis zum 04.08.2026 faktisch nie — S2 konnte nicht auslösen, S5 fiel
komplett durch den Konfidenzfilter (A31, A32). Seit der Behebung handeln sie: rund ein
Trade pro Tag im Simulator statt einem alle zehn Tage.

**Häufigkeit ist aber kein Ertrag.** Ein Setup, das zehnmal so oft handelt und dabei
verliert, ist zehnmal schlechter. Bevor S2 auf ein echtes Konto darf, braucht es dieselbe
Behandlung wie die Tagesspanne: `paper --review` über genug Sitzungen, Konfidenzbänder, und
den Ablationstest aus A27 — der bei der Hauptstrategie gezeigt hat, dass die gemessene Kante
im Wesentlichen ein Simulator-Parameter war. Es gibt keinen Grund anzunehmen, dass S2 davor
gefeit ist.

Solange das offen ist, gehört der EA auf ein **Demokonto**.

---

Siehe auch: [[Die Hauptstrategie]] · `docs/REPO-AUDIT.md`
