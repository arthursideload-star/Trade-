# Bot automatisch laufen lassen — ohne eigenen PC

## Die kurze Antwort

**Auf dem Handy oder iPad direkt geht es nicht.** Die MT5-App für iOS und Android hat
**keine EA-Engine**. Das ist keine Einstellung, die man freischalten kann — die Funktion
existiert in der mobilen App schlicht nicht. Dasselbe gilt für das MT5-Webterminal.

Das betrifft **jeden** Expert Advisor gleichermaßen: unseren, den aus dem MQL5-Markt, jeden
anderen.

| Umgebung | EA möglich? |
|---|---|
| MT5 Windows Desktop | ✅ ja |
| MT5 Mac / Linux (über Wine oder die MetaQuotes-Version) | ✅ ja, mit Einschränkungen |
| **MT5 iOS / Android App** | ❌ **nein** |
| **MT5 Webterminal** | ❌ **nein** |
| **Windows-VPS, ferngesteuert vom iPad** | ✅ **ja — das ist dein Weg** |
| **MT5-Docker-Container auf einem VPS, bedient im Browser** | ✅ **ja — und am wenigsten Aufwand** |

Was auf dem Handy **schon** geht: Charts ansehen, Trades manuell eröffnen und schließen,
Positionen überwachen, Push-Benachrichtigungen empfangen. Nur eben nichts Automatisches.

---

## Der Weg, der vom iPad aus funktioniert: Windows-VPS

Du mietest einen kleinen Windows-Server, steuerst ihn per Fernwartungs-App vom iPad, und
MT5 läuft dort dauerhaft — auch wenn dein iPad aus ist.

> **Kürzerer Weg, falls dein Anbieter ihn hat:** Manche VPS-Anbieter (unter anderem
> Hostinger) bieten MT5 als **Docker-Template** an. Dann läuft MT5 unter Wine in einem
> Container und wird über **KasmVNC direkt im Browser** bedient — kein Windows, keine
> Remote-Desktop-App, nur Safari. Schritt für Schritt in
> **[VPS-SETUP.md](./VPS-SETUP.md)**, Teil A.

**Das ist ohnehin die richtige Lösung für einen 24/7-Bot.** Ein EA auf dem eigenen Laptop
hört auf zu arbeiten, sobald der Deckel zugeht oder das WLAN wackelt.

### Was du brauchst

1. **Einen Windows-VPS.** Zwei Wege:
   - **MT5-eigenes Virtual Hosting** — direkt aus dem Terminal mietbar, ab etwa 10 $/Monat.
     **Haken:** Zum Einrichten und Migrieren brauchst du das Desktop-Terminal. Für dich
     also erst der zweite Schritt, nicht der erste.
   - **Normaler Windows-VPS** bei einem beliebigen Anbieter. Forex-VPS-Anbieter werben mit
     niedriger Latenz zu Broker-Servern; für einen M5-Scalper auf Demo ist das ziemlich
     egal. Ein einfacher Windows-Server mit 2 GB RAM reicht. Preise liegen typischerweise
     bei 5–15 €/Monat.
   - **Manche Broker geben einen VPS gratis** ab einer bestimmten Einlage oder einem
     bestimmten Handelsvolumen. Nachfragen kostet nichts — aber lass dich davon nicht zu
     einer Einzahlung drängen, die du sonst nicht machen würdest.

2. **Eine Remote-Desktop-App auf dem iPad.** Microsoft hat eine kostenlose im App Store
   („Windows App" bzw. früher „Microsoft Remote Desktop"). Damit siehst du den
   Windows-Desktop auf dem iPad und bedienst ihn per Touch.

### Ablauf

1. VPS bestellen, du bekommst **IP-Adresse, Benutzername, Passwort**.
2. Remote-Desktop-App auf dem iPad öffnen, Verbindung mit diesen Daten anlegen.
3. Auf dem Windows-Desktop: **MetaTrader 5 von deinem Broker herunterladen** und
   installieren (PuPrime hat einen Download-Link im Kundenbereich).
4. Mit deinem **Demokonto** anmelden.
5. Den EA installieren — siehe [README.md](./README.md), Abschnitt Installation. Es ist
   **eine einzige Datei**, `GoldScalpAssistant.mq5`, nach `MQL5/Experts` kopieren und F7
   drücken.
6. Auf den XAUUSD-M5-Chart ziehen, Algo-Trading einschalten.
7. iPad zuklappen. Läuft weiter.

### Wie du die Datei auf den VPS bekommst

Am einfachsten: Im Remote-Desktop auf dem VPS einen Browser öffnen und die Datei direkt
aus GitHub herunterladen:

```
https://github.com/arthursideload-star/Trade-
  -> mt5/Experts/GoldScalpAssistant.mq5
  -> Rechtsklick auf "Raw" -> Ziel speichern unter
```

Speichern nach `…/MQL5/Experts/`. Den Pfad findest du in MT5 über
**Datei → Datenverzeichnis öffnen**.

Alternativ Copy-Paste: Datei in MetaEditor neu anlegen (**Neu → Expert Advisor**), Inhalt
einfügen, speichern, F7.

### Kostenkontrolle

Ein VPS kostet monatlich Geld, **bevor** irgendein Ertrag da ist — und dieser Bot hat
keinen nachgewiesenen positiven Erwartungswert. Rechne den VPS als **Lerngeld**, nicht als
Investition, die sich rechnen muss.

Wenn dir das zu früh ist: Der `/trade`-Befehl im Chat funktioniert auf dem iPad ohne
irgendwelche Kosten. Du bekommst dieselbe Analyse, klickst den Trade selbst in der
MT5-App. Das ist langsamer, aber es kostet nichts und du lernst dabei mehr.

---

## Was du unterwegs schon jetzt tun kannst — ohne VPS

| Womit | Was |
|---|---|
| **`/trade` im Chat** | Vollständige Analyse: hoch/runter/abwarten, Einstieg, Stop, zwei Ziele, Größe, wann aufhören |
| **MT5-App auf dem Handy** | Trade manuell eröffnen, Stop setzen, Position überwachen |
| **MT5-App Push-Nachrichten** | Benachrichtigung, wenn ein Stop oder Ziel erreicht wird |

Das ist der halbautomatische Betrieb aus dem ursprünglichen Plan, und für die Demo-Phase
ist er ehrlich gesagt der bessere: **Du siehst jede Entscheidung und lernst dabei.** Ein
Auto-Bot, der auf einem VPS Trades macht, die du nicht mitverfolgst, lehrt dich nichts —
er sammelt nur Statistik.

---

## Der ehrliche Rat zur Reihenfolge

1. **Jetzt, auf dem iPad:** `/trade` im Chat, Trades manuell in der MT5-App. Kostet nichts.
   Führ dabei Buch — mindestens 30 Trades, Ergebnis in R, und die Frage „habe ich den Plan
   befolgt" getrennt von „hat der Trade gewonnen".
2. **Wenn du wieder am PC bist:** EA im **Advisor-Modus** auf die Demo. Vergleiche seine
   Signale mit dem, was du selbst gemacht hättest. Wo er und die Chat-Analyse
   übereinstimmen, ist das ein Argument. Wo nicht, ist es eins, das man untersuchen sollte.
3. **Danach, falls die Zahlen es hergeben:** VPS mieten, Auto-Modus, weiterhin **Demo**.
4. **Echtes Geld erst,** wenn du über mehrere Monate eigene Zahlen hast, die etwas anderes
   sagen als der bisherige Backtest.

Schritt 3 zu überspringen und direkt einen Auto-Bot auf einen VPS zu stellen, ist
technisch machbar und lehrreich ungefähr null. Der EA würde eine Strategie ausführen, von
der wir wissen, dass sie sich noch nicht bewährt hat, und du würdest dabei nicht zusehen.

---

## Zur Frage nach dem MQL5-Produkt

Das kostenlose „Gold Scalper for MT5" aus dem MQL5-Markt kannst du **ebenfalls nicht** auf
dem Handy installieren — dieselbe Einschränkung. Über den MQL5-Markt heruntergeladene EAs
laufen genauso nur im Desktop-Terminal.

Was ich daraus gelernt und in unseren EA übernommen habe, steht in
[docs/GOLD-SCALPING.md](../docs/GOLD-SCALPING.md), Teil VI — vor allem die drei
Broker-Randbedingungen, die im Backtest gar nicht auftreten können und live sofort:
Mindest-Stop-Abstand, unmöglicher Teilverkauf und Phantom-Trades bei dünner Tick-Dichte.
