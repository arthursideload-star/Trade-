# VPS-Setup — MT5 auf Hostinger, gesteuert vom iPad

Ziel: MetaTrader 5 läuft auf deinem VPS dauerhaft, du bedienst ihn vom iPad, der EA arbeitet
weiter wenn dein iPad aus ist.

---

## Schritt 0 — Welchen Weg hast du?

| Was auf dem VPS läuft | Weg | Zeitbedarf |
|---|---|---|
| **Hostinger Docker-Template „MetaTrader 5"** | **Teil A** | ~15 Minuten |
| Windows Server | Teil B | ~30 Minuten |
| Nacktes Ubuntu/Debian, kein Template | Teil C | ~60 Minuten |

Nachsehen im Hostinger-Panel unter **VPS → dein Server → Docker Manager**. Steht dort ein
Projekt namens `metatrader-5-…` auf **„In Betrieb"**, ist es **Teil A** — dann ist MT5 schon
installiert und du überspringst B und C komplett.

---

## Teil A — MT5 läuft schon als Docker-Container

Das Hostinger-Template ist MetaTrader 5 unter Wine, bedient über **KasmVNC im Browser**
(Port 3000). Es braucht keinen Remote-Desktop, keine App — nur Safari auf dem iPad.

### A1. MT5 öffnen

Hostinger-Panel → **VPS → Docker Manager** → beim Projekt `metatrader-5-…` auf
**Zugriff → Öffnen**.

Es fragt nach Benutzername und Passwort. Das sind die, die bei der Bereitstellung des
Templates gesetzt wurden (`CUSTOM_USER` / `PASSWORD`) — nicht dein Root-Passwort. Wenn du sie
nicht mehr weißt: **Verwalten → Umgebungsvariablen**.

> **Sicherheit, kurz und ernst:** Dieser Port ist aus dem ganzen Internet erreichbar und
> dahinter liegt ein Handelskonto. Wenn das Passwort schwach oder Standard ist, ändere es
> jetzt, bevor irgendein Konto verbunden wird. Nicht dasselbe wie das Root-Passwort nehmen.

### A2. Beim Broker anmelden

In MT5: **Datei → Handelskonto öffnen** bzw. **Mit Handelskonto verbinden** → Login,
Passwort und Server deines **Demokontos** eintragen.

Steht PuPrime nicht in der Serverliste: Servernamen von Hand eintippen. Er steht in der
Kontoeröffnungs-E-Mail.

### A3. EA in den Container kopieren

Das geht ohne Datei-Upload — der Container holt sich die Datei selbst. Im Hostinger-Panel
beim Docker-Projekt auf **Zugriff → Terminal**, dann:

```bash
find / -type d -path "*MQL5/Experts" 2>/dev/null
```

Erwartet wird ein Pfad in dieser Art:

```
/config/.wine/drive_c/Program Files/MetaTrader 5/MQL5/Experts
```

Diesen Pfad unten einsetzen (die Anführungszeichen sind wegen der Leerzeichen nötig):

```bash
cd "/config/.wine/drive_c/Program Files/MetaTrader 5/MQL5/Experts"
wget -O GoldScalpAssistant.mq5 \
  https://raw.githubusercontent.com/arthursideload-star/Trade-/refs/heads/claude/trading-bot-plan-4uj86r/mt5/Experts/GoldScalpAssistant.mq5
wc -l GoldScalpAssistant.mq5
```

**Erwartet: `1377 GoldScalpAssistant.mq5`.** Steht dort eine andere Zahl oder eine Fehlermeldung,
ist die Datei nicht vollständig angekommen — dann nicht weitermachen, sondern mir die Ausgabe
schicken.

> Findet `find` mehrere Pfade, nimm den unter `Program Files/MetaTrader 5/`. Findet es gar
> keinen, öffne in MT5 **Datei → Datenverzeichnis öffnen** — der Pfad steht dann in der
> Titelzeile des Fensters.

### A4. Kompilieren

Zurück im MT5-Fenster im Browser: den **IDE-Knopf** in der Symbolleiste (öffnet MetaEditor;
**F4** funktioniert über VNC oft nicht, weil der Browser die Taste abfängt).

Links im Navigator unter *Experts* auf `GoldScalpAssistant.mq5` → **Kompilieren** (oder F7).

**Erwartet: `0 errors, 0 warnings`.**

> **Wenn Fehler kommen:** Zeilennummern und Text abschreiben oder abfotografieren und mir
> schicken. Ich kann hier nicht kompilieren — das ist der erste echte Test des EA.

### A5. Auf den Chart

- **XAUUSD** öffnen, Zeitrahmen **M5**
- EA aus dem Navigator auf den Chart ziehen
- Reiter **Allgemein**: Haken bei *Algo-Trading erlauben* → OK
- In der Symbolleiste **Algo-Trading** grün schalten

Oben links erscheint das Panel. Steht dort `[ADVISOR]` — richtig, so soll es anfangen.

### A6. Weiterlaufen lassen

Hier ist es einfacher als bei Windows: **Browser-Tab einfach zumachen.** Der Container läuft
auf dem VPS weiter, MT5 ebenfalls. VNC ist nur die Fernbedienung.

Nicht tun: im Docker Manager auf *Stoppen* oder *Neu starten*.

Zum Prüfen: Tab schließen, 10 Minuten warten, wieder öffnen. Ist das Panel aktuell, läuft es.

**Weiter bei Schritt E.**

---

## Teil B — Windows-VPS

### B1. Verbinden

Auf dem iPad die App **„Windows App"** (früher *Microsoft Remote Desktop*) aus dem App Store
installieren — kostenlos.

Neue Verbindung anlegen mit den Daten aus dem Hostinger-Panel:
- **PC-Name:** die IP-Adresse deines VPS
- **Benutzerkonto:** `Administrator` + dein VPS-Passwort

### B2. MT5 installieren

Im Remote-Desktop den Browser öffnen → PuPrime-Kundenbereich → **MT5 für Windows**
herunterladen → installieren → mit deinem **Demokonto** anmelden.

Weiter bei **Schritt D**.

---

## Teil C — Linux-VPS ohne Template

Nur nötig, wenn kein MT5-Docker-Projekt existiert. Drei Dinge fehlen: eine grafische
Oberfläche, ein Fernzugang dorthin, und MT5 über Wine.

> **Der bequemere Weg:** Statt das alles von Hand zu bauen, im Hostinger-Panel unter
> **VPS → Katalog** nach *MetaTrader* suchen und das Template bereitstellen — dann bist du
> bei Teil A. Das hier ist der Weg für den Fall, dass das Template nicht in Frage kommt.

### C1. Per SSH verbinden

Auf dem iPad eine SSH-App — **Termius** ist kostenlos. Verbindung mit IP, Benutzer `root`
und dem Passwort aus dem Hostinger-Panel.

### C2. Desktop und Fernzugang installieren

```bash
apt update && apt upgrade -y
apt install -y xfce4 xfce4-goodies xrdp
```

Bei der Rückfrage nach dem Display-Manager: **lightdm** wählen. Der zweite Befehl dauert
einige Minuten.

```bash
echo "xfce4-session" > ~/.xsession
systemctl enable xrdp
systemctl restart xrdp
ufw allow 3389/tcp
```

Falls `ufw` nicht aktiv ist, ist auch das in Ordnung — dann ist der Port ohnehin offen.

### C3. Vom iPad verbinden

Dieselbe **„Windows App"** wie in Teil B, aber Benutzer `root` + VPS-Passwort. Du solltest
einen XFCE-Desktop sehen.

### C4. MT5 installieren

**Im Remote-Desktop** ein Terminal öffnen (Anwendungen → Terminal):

```bash
wget https://download.mql5.com/cdn/web/metaquotes.software.corp/mt5/mt5ubuntu.sh
chmod +x mt5ubuntu.sh
./mt5ubuntu.sh
```

Das ist das **offizielle Installationsskript von MetaQuotes**. Es installiert Wine und MT5.
Beim ersten Lauf 10–20 Minuten. Danach mit dem **Demokonto** anmelden.

---

## Schritt D — EA installieren (Teil B und C)

### D1. Datei holen

Im Browser **auf dem VPS** öffnen:

```
https://raw.githubusercontent.com/arthursideload-star/Trade-/refs/heads/claude/trading-bot-plan-4uj86r/mt5/Experts/GoldScalpAssistant.mq5
```

Rechtsklick → **Seite speichern unter**. Wohin? In MT5: **Datei → Datenverzeichnis öffnen** →
Ordner `MQL5/Experts`.

Es ist **eine einzige Datei**, sonst nichts. 1377 Zeilen.

### D2. Kompilieren

In MT5 **F4** → MetaEditor → links `GoldScalpAssistant.mq5` → **F7**.
Erwartet: `0 errors, 0 warnings`.

### D3. Auf den Chart

Wie in A5: XAUUSD, M5, EA draufziehen, *Algo-Trading erlauben*, Knopf grün.

### D4. Damit es nach dem Zumachen weiterläuft

**Wichtig, sonst war alles umsonst:** Trennst du die Remote-Desktop-Verbindung, läuft MT5
weiter. Meldest du dich **ab**, nicht.

- **Windows:** Im Remote-Desktop das **X** oben schließen, *nicht* Start → Abmelden.
- **Linux/xrdp:** Fenster schließen, *nicht* Abmelden.

---

## Schritt E — Der erste Abend

Reihenfolge, die etwas bringt:

1. **Demokonto auf einen realistischen Betrag stellen.** Beim Broker ein Demokonto mit
   **1.000 USD** anlegen. Nicht 100.000 — dann lernst du Größen, die du später nie handeln
   wirst. Und nicht 55, dann lehnt der EA jeden Trade ab (siehe unten).

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

- **Heute:** einrichten, Demo mit 1.000 USD, Advisor-Modus.
- **Heute Abend:** zusehen, mitschreiben. Kostet nichts.
- **Morgen:** Auto-Modus auf Demo, weiter beobachten.
- **Die 55 € behalten.** Sie reichen nicht für Gold nach den Regeln, und sie reichen erst
  recht nicht, um damit VPS-Kosten zurückzuholen.

Zu den Umfragen: Die zahlen realistisch ein paar Euro pro Stunde. 50–100 € sind damit viele
Stunden Arbeit — und die dann in ein System zu stecken, dessen Kante noch nicht belegt ist,
ist die teure Reihenfolge. Wenn das Geld ohnehin da ist, ist gegen ein größeres Demokonto
nichts einzuwenden; das kostet nämlich gar nichts.

### Wenn der VPS ausläuft

Läuft die Laufzeit ab, ist der Container weg — inklusive kompiliertem EA und Journal. Was
du behalten willst, vorher sichern:

- Die `.mq5` liegt ohnehin auf GitHub, die ist sicher.
- **Journal und Kontoauszug** vor dem Ablauf exportieren: MT5 → **Kontohistorie →
  Rechtsklick → Bericht → XLSX**, Datei über den Browser herunterladen.

---

## Häufige Probleme

| Symptom | Ursache |
|---|---|
| Docker: „Öffnen" fragt nach Passwort, keins bekannt | Docker Manager → Verwalten → Umgebungsvariablen (`CUSTOM_USER` / `PASSWORD`) |
| Docker: Seite lädt nicht | Container gestoppt. Docker Manager → Status prüfen, ggf. starten |
| `wget` schreibt „Permission denied" | Im Container-Terminal statt im VPS-Terminal arbeiten (Zugriff → Terminal beim Projekt) |
| `wc -l` zeigt nicht 1377 | Download unvollständig oder falscher Pfad. Datei löschen, erneut laden |
| F4 öffnet nichts | Über VNC fängt der Browser die Taste ab — den **IDE-Knopf** in der Symbolleiste nutzen |
| Remote Desktop verbindet nicht | Port 3389 blockiert. Hostinger-Panel → Firewall → 3389/TCP freigeben |
| Linux: schwarzer Bildschirm nach Login | `echo "xfce4-session" > ~/.xsession` vergessen, dann `systemctl restart xrdp` |
| MT5 startet nicht (Linux) | Wine-Installation unvollständig. `./mt5ubuntu.sh` erneut ausführen |
| EA-Panel erscheint nicht | Algo-Trading nicht grün, oder EA nicht auf den Chart gezogen |
| Panel zeigt dauernd `AVOID` | Wochenende, Rollover (21–23 UTC) oder Markt geschlossen. Richtig so |
| Panel `PRIME`, aber nichts passiert | Kein Setup. Die meisten Kerzen sind keine Gelegenheit |
| „Cannot size" im Journal | Konto zu klein für die Stop-Distanz — siehe oben |
| MT5 weg nach dem Trennen | Du hast dich abgemeldet statt nur das Fenster zu schließen |
