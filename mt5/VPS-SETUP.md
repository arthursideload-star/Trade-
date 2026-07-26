# VPS-Setup — MT5 auf Hostinger, gesteuert vom iPad

Ziel: MetaTrader 5 läuft auf deinem VPS dauerhaft, du bedienst ihn per
Remote-Desktop-App vom iPad, der EA arbeitet weiter wenn dein iPad aus ist.

**Zeitbedarf:** 30–60 Minuten beim ersten Mal.

---

## Schritt 0 — Welches Betriebssystem hast du?

Das entscheidet alles Weitere. Schau im Hostinger-Kundenbereich unter **VPS → dein Server →
Übersicht** nach.

| OS | Weg |
|---|---|
| **Windows Server** | Teil A. Einfach: MT5 herunterladen, fertig. |
| **Ubuntu / Debian / AlmaLinux** | Teil B. Etwas mehr Arbeit, funktioniert aber gut. |

Hostinger verkauft überwiegend **Linux-VPS** (KVM-Pläne). Wenn du nicht ausdrücklich Windows
gewählt hast, ist es Linux → **Teil B**.

Falls dein Plan einen OS-Wechsel erlaubt und Windows dabei ist: Das spart dir Teil B
komplett. Im Panel unter **Betriebssystem → Neu installieren** nachsehen. Achtung: Dabei
wird der Server zurückgesetzt.

---

## Teil A — Windows-VPS

### A1. Verbinden

Auf dem iPad die App **„Windows App"** (früher *Microsoft Remote Desktop*) aus dem App Store
installieren — kostenlos.

Neue Verbindung anlegen mit den Daten aus dem Hostinger-Panel:
- **PC-Name:** die IP-Adresse deines VPS
- **Benutzerkonto:** `Administrator` + dein VPS-Passwort

### A2. MT5 installieren

Im Remote-Desktop den Browser öffnen → PuPrime-Kundenbereich → **MT5 für Windows**
herunterladen → installieren → mit deinem **Demokonto** anmelden.

Weiter bei **Schritt C**.

---

## Teil B — Linux-VPS (Ubuntu)

Drei Dinge sind nötig: eine grafische Oberfläche, ein Fernzugang dorthin, und MT5 über Wine.

### B1. Per SSH verbinden

Auf dem iPad brauchst du eine SSH-App. **Termius** ist kostenlos und funktioniert gut.

Verbindung anlegen mit IP, Benutzer `root` und dem Passwort aus dem Hostinger-Panel.

### B2. Desktop und Fernzugang installieren

Diese Befehle nacheinander eingeben. Der zweite dauert einige Minuten.

```bash
apt update && apt upgrade -y
apt install -y xfce4 xfce4-goodies xrdp
```

Bei einer Rückfrage nach dem Display-Manager: **lightdm** wählen.

```bash
echo "xfce4-session" > ~/.xsession
systemctl enable xrdp
systemctl restart xrdp
ufw allow 3389/tcp
```

Falls `ufw` nicht aktiv ist, ist auch das in Ordnung — dann ist der Port ohnehin offen.

### B3. Vom iPad verbinden

Jetzt dieselbe **„Windows App"** wie in Teil A:
- **PC-Name:** deine VPS-IP
- **Benutzer:** `root` + VPS-Passwort

Du solltest einen XFCE-Desktop sehen.

### B4. MT5 installieren

**Im Remote-Desktop** ein Terminal öffnen (Anwendungen → Terminal) und eingeben:

```bash
wget https://download.mql5.com/cdn/web/metaquotes.software.corp/mt5/mt5ubuntu.sh
chmod +x mt5ubuntu.sh
./mt5ubuntu.sh
```

Das ist das **offizielle Installationsskript von MetaQuotes**. Es installiert Wine und MT5
und startet den Installer. Beim ersten Lauf dauert es 10–20 Minuten und lädt einiges herunter.

Danach: MT5 startet, mit deinem **Demokonto** anmelden.

> **Wenn PuPrime nicht in der Serverliste steht:** Im Anmeldedialog den Servernamen von Hand
> eintippen. Er steht in deiner Kontoeröffnungs-E-Mail von PuPrime.

---

## Schritt C — EA installieren (gilt für beide Wege)

### C1. Datei auf den VPS holen

Im Browser **auf dem VPS** öffnen:

```
https://github.com/arthursideload-star/Trade-/blob/claude/trading-bot-plan-4uj86r/mt5/Experts/GoldScalpAssistant.mq5
```

Auf **Raw** klicken, dann Rechtsklick → **Seite speichern unter**.

Wohin? In MT5: **Datei → Datenverzeichnis öffnen** → Ordner `MQL5/Experts`.

Es ist **eine einzige Datei**, sonst nichts.

### C2. Kompilieren

In MT5 **F4** → MetaEditor öffnet sich → links `GoldScalpAssistant.mq5` anklicken → **F7**.

Erwartet: `0 errors, 0 warnings`.

> **Wenn Fehler kommen:** Schick mir die Zeilennummern und den Text. Ich kann hier nicht
> kompilieren, also ist das der erste echte Test.

### C3. Auf den Chart

- **XAUUSD** öffnen, Zeitrahmen **M5**
- EA aus dem Navigator auf den Chart ziehen
- Reiter **Allgemein**: Haken bei *Algo-Trading erlauben* → OK
- In der Symbolleiste den Knopf **Algo-Trading** grün schalten

Oben links erscheint das Panel. Steht dort `[ADVISOR]` — richtig.

---

## Schritt D — Damit es nach dem Zumachen weiterläuft

**Wichtig, sonst war alles umsonst:** Wenn du die Remote-Desktop-Verbindung einfach trennst,
läuft MT5 weiter. Wenn du dich **abmeldest**, nicht.

- **Windows:** Im Remote-Desktop einfach das **X** oben schließen, *nicht* Start → Abmelden.
- **Linux/xrdp:** Fenster schließen, *nicht* Abmelden. Die Sitzung bleibt.

Zum Prüfen: iPad zuklappen, 10 Minuten warten, wieder verbinden. Steht MT5 noch da und ist
das Panel aktuell, läuft es.

---

## Schritt E — Der erste Abend

Reihenfolge, die etwas bringt:

1. **Demokonto auf einen realistischen Betrag stellen.** Bei PuPrime im Kundenbereich ein
   neues Demokonto mit **1.000 USD** anlegen. Nicht 100.000 — dann lernst du Größen, die du
   später nie handeln wirst. Und nicht 55, dann lehnt der EA jeden Trade ab (siehe unten).

2. **Advisor-Modus laufen lassen.** Er meldet Setups, platziert aber nichts. Vergleiche seine
   Vorschläge mit dem, was du selbst gemacht hättest.

3. **Ins Journal schreiben.** Jeden Vorschlag: Setup-ID, Einstieg, Stop, was daraus geworden
   wäre. In R, nicht in Euro.

4. **Erst wenn du 20–30 Vorschläge gesehen hast:** Auto-Modus, weiterhin Demo.

---

## Zu deinem Zeitplan — die Zahl, die entscheidet

Du hast geschrieben: heute einrichten, heute Abend testen, dann mit 55 € echt starten.

**Mit 55 € lehnt der EA jeden Gold-Trade ab.** Das ist keine Vorsichtsmaßnahme, sondern
Arithmetik:

```
python -m metals minimum XAUUSD --equity 55
```

Die kleinstmögliche Position (0,01 Lot) ist **eine Feinunze**. Ein Stop von 3 USD/oz kostet
dich damit 3 USD — das sind **5,5 % von 55 €**. Erlaubt ist 1 %.

| Konto | Stop 2 USD/oz | Stop 3 USD/oz | Stop 5 USD/oz |
|---|---|---|---|
| 55 € | 3,6 % ❌ | 5,5 % ❌ | 9,1 % ❌ |
| 105 € | 1,9 % ❌ | 2,9 % ❌ | 4,8 % ❌ |
| **300 €** | 0,7 % ✅ | 1,0 % ✅ | 1,7 % ⚠️ |

(Euro und Dollar sind hier gleichgesetzt. Beim aktuellen Kurs verschiebt das die Zahlen um
wenige Prozentpunkte — an der Aussage ändert es nichts.)

Für Gold bei 1 % Risiko brauchst du **rund 300 USD (≈ 275 €)**. Darunter ist es rechnerisch
nicht handelbar — egal wie gut ein Setup aussieht.

Du könntest das Limit im Code hochsetzen. Bei 5 % Risiko pro Trade sind vier Verlust-Trades
in Folge — was in den Backtests regelmäßig vorkam — ein Fünftel des Kontos. Bei 55 € ist das
zufällig verkraftbar; als Gewohnheit ist es der Grund, warum die meisten Konten verschwinden.

### Und der zweite Punkt

„Heute Abend testen, dann echt starten" ergibt bei M5-Scalping etwa **2–4 Trades**. Aus
2–4 Trades lässt sich nichts ableiten. Meine eigenen Backtests haben eine Variante mit
**63 % Trefferquote** produziert, die trotzdem Geld verlor — bei 4 Trades hättest du die für
großartig gehalten.

Und: Die Strategie hat **keinen nachgewiesenen positiven Erwartungswert**. In 17
Konfigurationen über 100 Märkte war jede negativ, auch die ohne Spread. Das widerlegt sie
nicht (der Test konnte ihre Kernwette strukturell nicht prüfen) — aber es ist auch keine
Grundlage, um Geld darauf zu setzen, das du zurückholen musst.

### Was ich stattdessen vorschlage

Der VPS läuft ohnehin noch 1–2 Tage. Nutz ihn für das, wofür er taugt:

- **Heute:** einrichten, Demo mit 1.000 USD, Advisor-Modus.
- **Heute Abend:** zusehen, mitschreiben. Kostet nichts.
- **Morgen:** Auto-Modus auf Demo, weiter beobachten.
- **Die 55 € behalten.** Sie reichen nicht für Gold nach den Regeln, und sie reichen erst
  recht nicht, um damit VPS-Kosten zurückzuholen.

Zu den Umfragen: Die zahlen realistisch ein paar Euro pro Stunde. 50–100 € sind damit viele
Stunden Arbeit — und die dann in ein System zu stecken, dessen Kante noch nicht belegt ist,
ist die teure Reihenfolge. Wenn das Geld ohnehin da ist, ist gegen ein größeres Demokonto
nichts einzuwenden; das kostet nämlich gar nichts.

---

## Häufige Probleme

| Symptom | Ursache |
|---|---|
| Remote Desktop verbindet nicht | Port 3389 blockiert. Hostinger-Panel → Firewall → 3389/TCP freigeben |
| Linux: schwarzer Bildschirm nach dem Login | `echo "xfce4-session" > ~/.xsession` vergessen, dann `systemctl restart xrdp` |
| MT5 startet nicht (Linux) | Wine-Installation unvollständig. `./mt5ubuntu.sh` erneut ausführen |
| EA-Panel erscheint nicht | Algo-Trading nicht grün, oder EA nicht auf den Chart gezogen |
| Panel zeigt dauernd `AVOID` | Wochenende, Rollover (21–23 UTC) oder Markt geschlossen. Richtig so |
| Panel `PRIME`, aber nichts passiert | Kein Setup. Die meisten Kerzen sind keine Gelegenheit |
| „Cannot size" im Journal | Konto zu klein für die Stop-Distanz — siehe oben |
| MT5 weg nach dem Trennen | Du hast dich abgemeldet statt nur das Fenster zu schließen |
