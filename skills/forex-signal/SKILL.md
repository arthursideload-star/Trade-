---
name: forex-signal
description: Erstellt aus der deterministischen Forex-Analyse eine begruendete Handelsempfehlung — Richtung (Long/Short/Abwarten), Konfidenz, Einstieg, Stop aus der Struktur, Ziel mit mindestens 1:2, Positionsgroesse und die Pruefung aller Risikoregeln R1-R8. Verwenden als letzter Schritt, wenn der Nutzer nach einer Empfehlung oder Einschaetzung zu einem Paar fragt, etwa "Analysiere EUR/USD", "Soll ich EUR/USD kaufen", "Was meinst du zu GBP/USD". Baut auf forex-analysis auf und ist der Punkt, an dem Claude den Top-Down-Workflow anwendet.
---

# Forex-Signal (Empfehlungskarte)

Der letzte Baustein von Phase A (Sprint B4). Hier wird aus den harten Zahlen von
`forex-analysis` eine begruendete Empfehlung — und hier wendest **du (Claude)** den
Top-Down-Workflow an. Das Skript liefert einen deterministischen Vorschlag; das Urteil,
die Nachrichtenlage und die Erklaerung kommen von dir.

## Der Top-Down-Workflow (so gehst du vor)

1. **Daten holen und rechnen.** Rufe `recommend.py` (siehe unten). Es holt die Kerzen,
   berechnet die Analyse ueber alle vier Zeitebenen, bildet den Signal-Score und die
   Positionsgroesse und prueft R1-R8.
2. **Oben anfangen.** Lies die Empfehlungskarte von 4h nach unten: Der uebergeordnete Trend
   (4h/1h) legt fest, welche Richtung ueberhaupt erlaubt ist. Gegen ihn wird nicht gehandelt.
3. **Setup am Level pruefen.** Ein Signal zaehlt nur, wenn ein Muster **an einem Level** sitzt
   (das Skript filtert das schon). Kein Level, kein Setup.
4. **Vetos anwenden.** Sieh dir die Regeln mit Status `need_input` an — das sind die, die das
   Skript nicht allein entscheiden kann:
   - **R2 (Tagesverlust):** Frag den Nutzer nach dem heutigen Ergebnis, wenn unklar.
   - **R4 (News):** Pruefe selbst, ob in den naechsten 30 Minuten Hochimpakt-News anstehen
     (NFP, CPI, FOMC, EZB). Bis der News-Feed in B5 angebunden ist, ist das dein Job.
5. **Karte schreiben.** Fasse die Empfehlung in der Form aus `references/empfehlungskarte.md`
   zusammen — mit Begruendung, damit der Nutzer lernt, nicht blind folgt.

## Aufruf

```bash
# Vollstaendige Empfehlung; Kontogroesse fuer die Positionsgroesse noetig
python skills/forex-signal/scripts/recommend.py --symbol EUR/USD --account 10000

# Ohne Kontogroesse: Richtung, Konfidenz und Level, aber keine Stueckzahl
python skills/forex-signal/scripts/recommend.py --symbol EUR/USD

# Lesbare Karte statt JSON
python skills/forex-signal/scripts/recommend.py --symbol EUR/USD --account 10000 --format text
```

## Was das Skript entscheidet — und was nicht

| Das Skript | Du (Claude) |
|---|---|
| Score aus Trend, Momentum, Muster, S/R (Gewichte aus PLAN.md A5) | Deutest den Kontext und die Nachrichtenlage |
| Stop aus der naechsten Struktur, Ziel mit 1:2, Groesse mit 1 % Risiko | Pruefst R4 (News) und fragst R2 (Tagesverlust) ab |
| R1-R8 maschinell, soweit ohne externe Daten moeglich | Schreibst die Begruendung und die Warnungen |

## Ehrliche Grenzen

- **Volumen fehlt bei Forex.** Der Score verteilt dessen Gewicht auf die anderen Faktoren um,
  statt eine Null zu erfinden. Das ist dokumentiert, kein Fehler.
- **Kontowaehrung.** Die Groesse wird exakt in der Kurswaehrung gerechnet. Passt sie nicht zur
  Kontowaehrung (z. B. USD-Konto, EUR/GBP), weist die Karte darauf hin.
- **Keine automatische Order.** Die Empfehlung ist ein Vorschlag. Der Nutzer entscheidet und
  klickt selbst in MT5.
- **Keine Gewinngarantie.** Konfidenz ist eine interne Bewertung, keine Wahrscheinlichkeit fuer
  Gewinn.

## Weiterfuehrend

- `references/empfehlungskarte.md` — das Format der Karte (nach TRADING-WISSEN.md XXVI.3)
