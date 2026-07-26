# VPS-Setup — MT5 auf Hostinger, gesteuert vom iPad

Ziel: MetaTrader 5 läuft auf deinem VPS dauerhaft, du bedienst ihn vom iPad, der EA arbeitet
weiter wenn dein iPad aus ist.

---

## Der kürzeste Weg — wenn du keine Lust auf Lesen hast

Bei MT5 ist alles schon installiert. Es fehlt nur der EA. Drei Schritte:

**1.** Docker Manager → beim Projekt `metatrader-5-…` → **Zugriff → Terminal ↗**
(der untere Terminal-Knopf, nicht der oben auf der Seite). Diese zwei Zeilen einfügen:

```sh
curl -sSLO https://raw.githubusercontent.com/arthursideload-star/Trade-/refs/heads/claude/trading-bot-plan-4uj86r/mt5/install-ea.sh
sh install-ea.sh
```

Das Skript lädt den EA, prüft ihn, kompiliert ihn wenn möglich — **und zeigt dir ganz oben
dein Login für Schritt 2 an.**

**2.** Zurück im Docker Manager → **Zugriff → Öffnen ↗**. Beim Anmeldedialog die zwei Werte
eintippen, die das Skript ausgegeben hat. Kommt der Dialog leer zurück, waren sie falsch —
eine andere Fehlermeldung gibt es nicht ([Details in A2](#a2-der-anmeldedialog--und-warum-er-immer-wiederkommt)).

**3.** In MT5: Demokonto verbinden (**1 000 USD**, nicht 55 — sonst lehnt der EA jeden Trade
ab), **XAUUSD** auf **M5** öffnen, `GoldScalpAssistant` auf den Chart ziehen, *Algo-Trading
erlauben* anhaken, den Algo-Trading-Knopf grün schalten.

Fertig ist es, wenn oben links im Chart **`[ADVISOR]`** steht. Ab dann läuft er, meldet
Setups und führt Buch — auch wenn dein iPad aus ist.

Alles andere unten ist die ausführliche Fassung für den Fall, dass einer der drei Schritte
klemmt.

---

## Erst mal: die vier Wörter, die dauernd vorkommen

Ohne die versteht man die Hostinger-Oberfläche nicht. Sie sind harmloser als sie klingen.

| Wort | Was es wirklich bedeutet |
|---|---|
| **VPS** | Dein gemieteter Computer in Frankfurt. Läuft 24/7, auch wenn dein iPad aus ist. |
| **Container** | Ein abgeschottetes Programm-Paket auf diesem Computer. Enthält alles was es braucht — hier: MetaTrader 5 samt Windows-Nachbau. |
| **Docker** | Die Technik, die solche Container startet und laufen lässt. |
| **Docker Manager** | Die Seite im Hostinger-Panel, auf der du deine Container siehst und bedienst. Mehr ist es nicht — eine Übersichtsseite. |

Bild dazu: Der VPS ist die Wohnung, ein Container ist ein fertig eingerichtetes Zimmer darin,
Docker ist der Hausmeister, und der Docker Manager ist die Klingelanlage im Hausflur.

**Wichtig für dich:** In deinem Docker Manager steht schon ein Projekt namens
`metatrader-5-iore` und daneben ein grüner Haken mit **„In Betrieb"**. Das heißt:
**MetaTrader 5 ist bereits installiert und läuft gerade.** Du musst nichts mehr installieren.
Du musst nur noch reinkommen.

Das zweite Projekt (`paperclip-…`) hat mit dem Bot nichts zu tun — ignorieren.

> Der Zusatz `-iore` am Namen ist eine Zufallskennung, die Hostinger beim Bereitstellen
> anhängt. Bei dir heißt es `metatrader-5-iore`, bei jemand anderem `metatrader-5-xkfp`.
> Keine Bedeutung.

---

## Schritt 0 — Welchen Weg hast du?

| Was auf dem VPS läuft | Weg | Zeitbedarf |
|---|---|---|
| **Docker-Projekt `metatrader-5-…` auf „In Betrieb"** | **Teil A ← dein Fall** | ~15 Minuten |
| Windows Server | Teil B | ~30 Minuten |
| Nacktes Ubuntu/Debian, kein Template | Teil C | ~60 Minuten |

**So kommst du zum Docker Manager** (falls du die Seite wieder suchst):

1. Safari → `hpanel.hostinger.com` → anmelden
2. Oben links das **Menü ☰** → **VPS**
3. Auf deinen Server tippen (`srv…….hstgr.cloud`)
4. Links bzw. im Menü: **Docker Manager**

Die Brotkrümel-Leiste oben zeigt dann: `🏠 › VPS › srv…….hstgr.cloud › Docker Manager`.
Wenn das dasteht, bist du richtig.

---

## Teil A — MT5 läuft schon als Docker-Container

Das Hostinger-Template ist MetaTrader 5, das über einen Windows-Nachbau (Wine) auf Linux
läuft und dessen Bildschirm ins Web übertragen wird (KasmVNC). Praktische Folge: **Du
brauchst keine App.** Safari reicht. Du siehst das MT5-Fenster wie einen Screenshot, der
sich bewegt, und tippst hinein.

### Die Seite, auf der du stehst — was die Knöpfe tun

Auf der Docker-Manager-Seite steht bei deinem Projekt Folgendes. Was jede Zeile bedeutet:

| Was du siehst | Was es tut |
|---|---|
| **metatrader-5-iore**, „1 Container" | Der Name deines Projekts. Ein Container darin — MT5. |
| **Status: ✅ In Betrieb** | Läuft gerade. Muss so bleiben. |
| **Zugriff → Öffnen ↗** | **Der wichtigste Knopf.** Öffnet MT5 im Browser. |
| **Zugriff → Terminal ↗** | Öffnet eine Eingabezeile **im Container**. Brauchst du in A4. |
| **Anleitung → Dokumentation ↗** | Hostingers eigene Hilfeseite. Kannst du ignorieren. |
| **Verwalten** | Detailseite: Umgebungsvariablen, Logs, Neustart. Nur für A2 nötig. |
| **Weitere Aktionen** | Stoppen, Löschen, Neu bereitstellen. **Hier nichts anklicken.** |
| **Compose ⌄** (schwarzer Knopf oben) | Neue Projekte anlegen. **Brauchst du nicht** — deins existiert schon. |

Der Knopf **„Terminal ↗"** ganz oben auf der Seite (über „Docker-Projekte") ist **ein
anderer** als der bei „Zugriff". Der obere führt auf den VPS selbst, der untere in den
Container. Das ist die häufigste Verwechslung — dazu gleich mehr in A4.

---

### A1. MT5 im Browser öffnen

Beim Projekt `metatrader-5-iore` auf **Zugriff → Öffnen ↗** tippen.

Es öffnet sich ein neuer Tab mit einer Adresse wie `http://<deine-IP>:32768`. Die Zahl hinten
ist die Tür-Nummer, hinter der MT5 sitzt — nicht wundern.

> In den Containerdetails steht sie als **`32768:3000`**. Links die Tür von außen, rechts die
> von innen. Nach außen zählt die linke.

**Was jetzt passiert, hängt davon ab, wie das Template eingerichtet wurde:**

- **Es fragt nach Benutzername und Passwort** → weiter bei A2.
- **Es kommt direkt ein Desktop mit MT5** → sehr gut, weiter bei A3.
  Aber lies A2 trotzdem, der Sicherheitshinweis gilt dann erst recht.
- **Es lädt gar nicht / „Verbindung fehlgeschlagen"** → siehe „Häufige Probleme" unten.

### A2. Der Anmeldedialog — und warum er immer wiederkommt

Es erscheint ein dunkles Kästchen: **„Bei 168.…….… anmelden — Dein Passwort wird
unverschlüsselt übertragen"**, darunter *Benutzername* und *Passwort*.

**Das ist die häufigste Sackgasse der ganzen Einrichtung.** Typischer Ablauf: man tippt
seinen Namen oder seine E-Mail ein, tippt auf *Anmelden*, die Seite lädt kurz — und derselbe
Dialog steht wieder da, diesmal leer. Es sieht aus, als würde nichts passieren.

**Es passiert sehr wohl etwas.** Der Server prüft, lehnt ab und fragt erneut. Das ist eine
HTTP-Basisauthentifizierung; abgelehnt heißt hier „nochmal", nicht „Fehler". Es gibt keine
Meldung *„Passwort falsch"* — der leere Dialog **ist** die Meldung.

**Es sind weder dein Name noch deine E-Mail, weder dein Hostinger-Login noch das
Root-Passwort.** Es sind zwei Werte namens `CUSTOM_USER` und `PASSWORD`, die beim
Bereitstellen des Templates gesetzt wurden.

**Weg 1 — im YAML-Editor nachsehen (ohne Tippen):**

Docker Manager → beim Projekt **Verwalten** → auf der Seite nach unten scrollen, bis unter
den Containerdetails die Reiter **Visueller Editor** / **`.yaml-Editor`** erscheinen →
auf **`.yaml-Editor`** tippen. Dort steht die Konfiguration im Klartext, darin zwei Zeilen
dieser Art:

```yaml
    environment:
      - CUSTOM_USER=…
      - PASSWORD=…
```

Was hinter dem `=` steht, gehört in den Dialog.

**Weg 2 — den Container selbst fragen:**

In den Containerdetails auf **Terminal ↗** und eintippen:

```bash
env | grep -iE "custom_user|password"
```

Es kommen zwei Zeilen der Form `CUSTOM_USER=…` und `PASSWORD=…`.

> **Das Terminal fragt nicht nach diesem Passwort.** Es geht über das Hostinger-Panel, an der
> Anmeldung vorbei. Praktische Folge: Du kannst **A4 (EA installieren) sofort machen**, auch
> wenn du noch nicht in MT5 hineinkommst.

**Weg 3 — falls beide Werte leer oder gar nicht vorhanden sind:** Dann probiere
Benutzername `abc`, Passwort `abc`. Das ist der Standard der Basis-Images, auf denen dieses
Template aufbaut. Falls auch das nicht geht: im `.yaml-Editor` eigene Werte eintragen und
das Projekt neu bereitstellen.

**Beim Eintippen aufpassen:** iOS macht aus dem ersten Buchstaben gern einen Großbuchstaben
und hängt Leerzeichen an. Beides bricht die Anmeldung. Groß-/Kleinschreibung zählt.

> **Kurz und ernst gemeint:** Der Dialog sagt selbst, dass das Passwort **unverschlüsselt**
> übertragen wird (`http://`, nicht `https://`), und gleich hängt ein Handelskonto daran.
> Für ein Demokonto in zwei Tagen ist das vertretbar. Für echtes Geld ist es das nicht —
> dann braucht es vorher einen verschlüsselten Zugang. Und nimm hier **nicht** dasselbe
> Passwort wie beim Root-Zugang oder beim Broker.

### A3. Beim Broker anmelden

Du siehst jetzt MetaTrader 5. Falls dort schon ein Konto verbunden ist, das nicht deins ist:
trotzdem weitermachen, du legst deins einfach daneben.

In MT5 oben im Menü: **Datei → Mit Handelskonto verbinden** (in manchen Versionen
*Datei → Handelskonto öffnen → Bestehendes Konto*).

Drei Felder:
- **Login** — die Kontonummer aus deiner Broker-Mail (nur Ziffern)
- **Passwort** — das Kontopasswort, nicht dein Broker-Website-Passwort
- **Server** — z. B. `PUPrime-Demo`. Steht in derselben Mail.

Steht dein Server nicht in der Liste: **Namen von Hand eintippen**, exakt wie in der Mail.

Unten rechts in MT5 muss danach eine Verbindung mit Zahlen (kb/s) stehen, nicht „Keine
Verbindung". Und oben in der Kontoübersicht muss **Demo** stehen.

> **Nimm ein Demokonto mit 1.000 USD.** Nicht 100.000 (dann übst du Größen, die du nie
> handeln wirst) und nicht 55 (dann lehnt der EA jeden Trade ab, siehe ganz unten).
> Ein neues Demokonto legst du im Kundenbereich deines Brokers in zwei Minuten an.

### A4. Den EA in den Container holen

> **Das geht auch, wenn A2 noch klemmt.** Das Terminal läuft über das Hostinger-Panel und
> fragt nicht nach dem MT5-Passwort. Wenn du im Anmeldedialog feststeckst, mach hier weiter
> und hol A2 danach nach — dann ist die Datei schon da, wenn du reinkommst.
> **Mehr noch: das Skript unten zeigt dir die Zugangsdaten aus A2 an.**

**Ein „Terminal" ist ein schwarzes Fenster mit einer Eingabezeile.** Du schreibst einen
Befehl, drückst **Enter**, und der Computer antwortet mit Text. Kein Doppelklick, keine Maus.

**Das richtige Terminal öffnen:** Docker Manager → beim Projekt `metatrader-5-iore` →
**Zugriff → Terminal ↗**. Nicht den Terminal-Knopf ganz oben auf der Seite — der führt auf
den VPS statt in den Container.

---

#### Der kurze Weg — zwei Zeilen

Diese beiden Zeilen einfügen, Enter:

```sh
curl -sSLO https://raw.githubusercontent.com/arthursideload-star/Trade-/refs/heads/claude/trading-bot-plan-4uj86r/mt5/install-ea.sh
sh install-ea.sh
```

Das Skript macht alles, was ohne Fenster geht, und sagt bei jedem Schritt, was es tut:

1. **Zeigt dir `CUSTOM_USER` und `PASSWORD`** — die Zugangsdaten aus A2, im Klartext.
2. Prüft, ob du im Container bist (und sagt es dir, wenn nicht).
3. Sucht den `MQL5/Experts`-Ordner.
4. Lädt den EA und **zählt nach, ob er vollständig ist** — bei falscher Zeilenzahl wird
   nichts installiert, statt eine halbe Datei liegen zu lassen.
5. Versucht zu kompilieren. Klappt das, ist A5 schon erledigt.

Am Ende steht, was noch von Hand zu tun ist. Das Skript handelt nichts, ändert kein
Risikolimit und rührt kein Konto an — du kannst es beliebig oft laufen lassen.

**Erwartete Ausgabe an der wichtigsten Stelle:**

```
3. Downloading the expert advisor
------------------------------------------------------------
  OK    1649 lines, complete
  OK    installed at /config/.wine/drive_c/.../MQL5/Experts/GoldScalpAssistant.mq5
```

Steht dort `FAIL`, lies die Zeile darunter — dort steht, was zu tun ist. Wenn du nicht
weiterkommst: abfotografieren und schicken.

Wenn im Abschnitt `4. Compiling` ein **`OK compiled`** steht, überspringst du A5 und machst
bei **A6** weiter.

---

#### Der lange Weg — von Hand, Zeile für Zeile

Nur nötig, wenn das Skript nicht läuft (kein `curl`, kein Netz im Container). Immer nur
**eine Zeile auf einmal**, jeweils Enter.

**Schritt 1: prüfen, dass du drin bist.** Erste Zeile eintippen und Enter:

```bash
ls -d /config/.wine && echo "RICHTIG-IM-CONTAINER"
```

- Antwortet er mit `/config/.wine` und `RICHTIG-IM-CONTAINER` → passt, weiter.
- Antwortet er `No such file or directory` → du bist im VPS-Terminal, nicht im Container.
  Tab schließen, den **unteren** Terminal-Knopf nehmen.

**Schritt 2: den Zielordner finden.**

```bash
find / -type d -path "*MQL5/Experts" 2>/dev/null
```

Das durchsucht die Festplatte nach dem Ordner, in den MT5 seine Expert Advisors legt.
Dauert ein paar Sekunden. Heraus kommt eine Zeile, meistens genau diese:

```
/config/.wine/drive_c/Program Files/MetaTrader 5/MQL5/Experts
```

- **Mehrere Zeilen?** Nimm die mit `Program Files/MetaTrader 5/` darin.
- **Gar keine Zeile?** In MT5 auf **Datei → Datenverzeichnis öffnen** — der Pfad steht dann
  oben im Fenster. Den nimmst du dann unten statt meinem.

**Schritt 3: in den Ordner wechseln.** Der Pfad hat Leerzeichen, deshalb die
Anführungszeichen — die gehören dazu:

```bash
cd "/config/.wine/drive_c/Program Files/MetaTrader 5/MQL5/Experts"
```

Wenn nichts passiert und einfach die nächste Eingabezeile kommt: **genau richtig.** Ein
Terminal meldet Erfolg durch Schweigen.

**Schritt 4: die Datei herunterladen.** Das ist ein Befehl über zwei Zeilen — der
Rückstrich `\` am Ende sagt „geht in der nächsten Zeile weiter". Beide Zeilen tippen bzw.
einfügen, dann Enter:

```bash
wget -O GoldScalpAssistant.mq5 \
  https://raw.githubusercontent.com/arthursideload-star/Trade-/refs/heads/claude/trading-bot-plan-4uj86r/mt5/Experts/GoldScalpAssistant.mq5
```

`wget` holt eine Datei aus dem Internet. Die lange Adresse zeigt auf unser GitHub. Du siehst
einen Fortschrittsbalken und am Ende `saved`.

**Schritt 5: nachzählen.** Der wichtigste Befehl von allen:

```bash
wc -l GoldScalpAssistant.mq5
```

`wc -l` zählt die Zeilen der Datei.

**Es muss `1649 GoldScalpAssistant.mq5` dastehen.**

- Steht dort `1649` → die Datei ist vollständig angekommen. Weiter bei A5.
- Steht dort eine **andere Zahl** oder eine Fehlermeldung → nicht weitermachen.
  Datei löschen (`rm GoldScalpAssistant.mq5`) und Schritt 4 wiederholen. Bleibt es dabei:
  Ausgabe abfotografieren und mir schicken.

Diese Zahl ist bewusst als Test eingebaut — ein Test im Projekt prüft, dass sie zur echten
Datei passt. Wenn sie stimmt, hast du garantiert die richtige, vollständige Datei.

### A5. Kompilieren

MT5 versteht die Datei noch nicht — `.mq5` ist Quelltext, den man erst übersetzen muss. Das
macht MetaEditor, ein Programm das in MT5 eingebaut ist.

**Zurück im MT5-Tab.** In der Symbolleiste den **IDE-Knopf** suchen (er heißt manchmal auch
*MetaEditor*; das Symbol ist ein kleines Blatt mit Stift).

> **F4 funktioniert hier meistens nicht.** Über den Browser fängt Safari die Taste ab, bevor
> MT5 sie sieht. Deshalb der Knopf statt der Tastenkombination.

Im MetaEditor links im **Navigator** den Ordner **Experts** aufklappen →
`GoldScalpAssistant.mq5` antippen → oben auf **Kompilieren** (oder F7).

Unten erscheint ein Fenster mit dem Ergebnis. **Erwartet: `0 errors, 0 warnings`.**

- **`0 errors`** → fertig, weiter bei A6.
- **Fehler mit Zeilennummern** → abfotografieren und mir schicken. Ich kann MQL5 hier nicht
  kompilieren, also ist das der erste echte Test des EA. Fehler sind an dieser Stelle normal
  und schnell behoben — schick sie einfach.

Danach liegt neben der `.mq5` eine `.ex5`. Die ist die übersetzte Fassung, die MT5 ausführt.

### A6. Auf den Chart ziehen

1. In MT5 die **Marktübersicht** öffnen (Ansicht → Marktübersicht) und **XAUUSD** suchen.
   Heißt bei manchen Brokern `XAUUSD.r`, `GOLD` oder `XAUUSDm` — dann eben so.
2. Rechtsklick darauf → **Chartfenster** → der Gold-Chart öffnet sich.
3. Oben den Zeitrahmen auf **M5** stellen (5 Minuten). Das ist Pflicht, der EA rechnet auf M5.
4. Links im **Navigator** unter *Expert Advisors* den `GoldScalpAssistant` **auf den Chart
   ziehen**.
5. Im Fenster das aufgeht, Reiter **Allgemein**: Haken bei **Algo-Trading erlauben** → **OK**.
6. In der Symbolleiste oben den Knopf **Algo-Trading** antippen, bis er **grün** ist.

**Woran du erkennst, dass es läuft:**
- Oben rechts im Chart steht ein kleines Gesicht 🙂 (nicht 😞) neben dem EA-Namen.
- Oben links im Chart erscheint das Panel des EA, und dort steht **`[ADVISOR]`**.

`[ADVISOR]` heißt: Er rechnet, zeichnet und meldet Setups, **platziert aber keine Order**.
Genau so soll es anfangen. Der Auto-Modus ist eine bewusste Umschaltung, kein Standard.

### A7. Weiterlaufen lassen

Der bequemste Teil: **Browser-Tab einfach zumachen.**

MT5 läuft auf dem VPS weiter, nicht auf deinem iPad. Der Browser war nur die Fernbedienung.
Du kannst das iPad ausschalten, es ändert nichts.

**Was du nicht tun darfst:** im Docker Manager auf *Stoppen*, *Neu starten* oder unter
*Weitere Aktionen* irgendetwas anklicken. Das beendet den Container und damit MT5.

**Gegenprobe:** Tab schließen, zehn Minuten warten, über *Öffnen* wieder rein. Steht MT5
noch da und zeigt das Panel eine aktuelle Uhrzeit — läuft.

### A8. Checkliste

Alles erledigt, wenn du jedes Häkchen setzen kannst:

- [ ] MT5 öffnet sich über *Zugriff → Öffnen* im Browser
- [ ] Demokonto verbunden, unten rechts steht eine Verbindung, oben steht **Demo**
- [ ] Kontostand rund **1.000 USD**
- [ ] `wc -l` hat **1649** ausgegeben
- [ ] MetaEditor meldet **0 errors, 0 warnings**
- [ ] XAUUSD-Chart auf **M5**, EA drauf, 🙂 oben rechts
- [ ] Knopf **Algo-Trading** ist grün
- [ ] Panel oben links zeigt **`[ADVISOR]`**
- [ ] Nach dem ersten Setup: `GoldScalpAssistant.csv` liegt in `MQL5/Files`

Der letzte Punkt braucht Geduld — die Datei entsteht erst, wenn der EA das erste Setup
sieht. In einer ruhigen Stunde kann das dauern; das ist kein Fehler.

**Weiter bei Schritt E** — was du am ersten Abend damit machst.
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

Es ist **eine einzige Datei**, sonst nichts. 1649 Zeilen.

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

### Was du im Panel siehst und was es heißt

Das Panel oben links im Chart bewertet zuerst die **Uhrzeit** — noch bevor es um ein Setup
geht. Vier Zustände, genau diese Wörter:

| Anzeige | Bedeutung |
|---|---|
| **`PRIME`** | London, New York oder die Überlappung. Die Stunden mit Bewegung. |
| **`good`** | Handelbar, aber nicht die beste Zeit. |
| **`marginal`** | Dünn. Asiatische Stunden. |
| **`AVOID`** | Gesperrt. Wochenende, Rollover (21–23 UTC) oder Markt zu. Kein Fehler — das ist die Regel, die greift. |

Daneben steht `[ADVISOR]` oder `[AUTO]` (der Modus) und der Zustand einer offenen Position.
Greift zusätzlich ein Limit — Tagesverlust, Trade-Zahl, Verlustserie — nennt das Panel den
Grund im Klartext.

**`PRIME` heißt nicht „gleich kommt ein Trade".** Die meisten Kerzen sind keine Gelegenheit.
Wenn stundenlang nichts passiert, arbeitet der EA korrekt — Nichtstun ist der Normalfall.

### Wo du siehst, was der EA gemacht hat

In MT5 unten das Fenster **Werkzeugkasten** (Ansicht → Werkzeugkasten):

- Reiter **Experten** — alles was der EA meldet. Hier stehen die Setups.
- Reiter **Journal** — was das Terminal selbst tut, Verbindungen, Fehler.
- Reiter **Handel** — offene Positionen. Im Advisor-Modus bleibt der leer, das ist richtig.

Wenn du am nächsten Tag wissen willst, was war: Reiter **Experten**, hochscrollen.

### Das Journal — die Datei, die der EA für dich führt

Hochscrollen ist auf Dauer nichts. Deshalb schreibt der EA **automatisch mit**, ab dem ersten
Setup, auch im Advisor-Modus. Die Datei heißt `GoldScalpAssistant.csv` und liegt in
`MQL5/Files` (in MT5: **Datei → Datenverzeichnis öffnen**, dann Ordner `Files`).

Darin steht jede Zeile, die zählt:

- **Jedes erkannte Setup** — mit Einstieg, Stop, beiden Zielen, ATR, Spread, Session, Größe.
- **Jedes abgelehnte Setup mit dem Grund.** Das ist die interessantere Hälfte: Sie zeigt,
  welcher Filter arbeitet. Steht dort 40-mal *„position size below the broker minimum"*, ist
  das Konto zu klein — und keine Einstellung der Welt behebt das.
- **Jeder geschlossene Trade** — mit dem Ergebnis in **R** und dem Ausstiegsgrund.

Auswerten kannst du sie im Chat mit:

```
python -m metals journal --file GoldScalpAssistant.csv
```

Die Ausgabe sagt nicht nur, was passiert ist, sondern auch **was das belegt** — mit
Unsicherheitsbändern und einer klaren Ansage, wenn die Stichprobe zu klein ist. Genau darauf
kommt es an: Acht Gewinner am Stück fühlen sich nach Beweis an und sind keiner.

> **Der Bot stellt sich davon nicht selbst um.** Das ist Absicht, keine fehlende Funktion.
> Warum das bei diesen Datenmengen schaden würde, steht in
> **[../docs/LERNEN.md](../docs/LERNEN.md)** — mit der Rechnung dazu.

**Datei sichern, bevor der VPS abläuft** (siehe unten) — sie ist das Einzige, was du dir mit
Zeit erarbeitest.

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
- **`GoldScalpAssistant.csv` aus `MQL5/Files`** — das ist das Wichtigste. Der EA ist in zwei
  Minuten wieder installiert; die Aufzeichnung deiner Trades ist es nicht. Im
  Container-Terminal ausgeben und den Text kopieren:
  ```sh
  cat "$(find / -name GoldScalpAssistant.csv 2>/dev/null | head -n 1)"
  ```
- **Kontoauszug** exportieren: MT5 → **Kontohistorie → Rechtsklick → Bericht → XLSX**,
  Datei über den Browser herunterladen.

---

## Häufige Probleme

| Symptom | Was los ist und was du tust |
|---|---|
| **Anmeldedialog kommt nach jedem Versuch leer zurück** | Zugangsdaten falsch. Das ist die Fehlermeldung — eine andere gibt es nicht. Siehe A2 |
| „Öffnen" fragt nach Passwort, du kennst keins | **Verwalten → `.yaml-Editor`**, Zeilen `CUSTOM_USER=` und `PASSWORD=`. Oder im Container-Terminal `env \| grep -iE "custom_user\|password"` |
| Zugangsdaten stimmen, es geht trotzdem nicht | iOS-Autokorrektur: Großbuchstabe am Anfang oder Leerzeichen am Ende. Groß-/Kleinschreibung zählt |
| „Öffnen" lädt nicht, „Verbindung fehlgeschlagen" | Container gestoppt. Docker Manager → Status prüfen. Steht dort nicht „In Betrieb": *Weitere Aktionen → Starten* |
| Terminal antwortet `No such file or directory` bei `ls -d /config/.wine` | Du bist im **VPS-Terminal** statt im Container. Tab zu, den Terminal-Knopf **bei „Zugriff"** nehmen, nicht den oben auf der Seite |
| `wget: command not found` | Seltener Fall, anderes Image. Stattdessen `curl -L -o GoldScalpAssistant.mq5 <dieselbe Adresse>` |
| `wget` schreibt „Permission denied" | Falscher Ordner oder falsches Terminal. `pwd` eingeben — muss auf `…/MQL5/Experts` enden |
| `wc -l` zeigt nicht 1649 | Datei unvollständig. `rm GoldScalpAssistant.mq5`, dann Schritt 4 wiederholen |
| Datei ist da, MetaEditor zeigt sie nicht | Falscher `Experts`-Ordner erwischt. In MT5 **Datei → Datenverzeichnis öffnen**, den Pfad von dort nehmen |
| F4 öffnet nichts | Über den Browser fängt Safari die Taste ab — den **IDE-Knopf** in der Symbolleiste nutzen |
| Kein XAUUSD in der Marktübersicht | Rechtsklick → *Alle anzeigen*. Heißt bei manchen Brokern `GOLD`, `XAUUSD.r` oder `XAUUSDm` |
| Trauriges Gesicht 😞 statt 🙂 am Chart | *Algo-Trading erlauben* nicht angehakt, oder der Knopf in der Symbolleiste ist nicht grün |
| Remote Desktop verbindet nicht | Port 3389 blockiert. Hostinger-Panel → Firewall → 3389/TCP freigeben |
| Linux: schwarzer Bildschirm nach Login | `echo "xfce4-session" > ~/.xsession` vergessen, dann `systemctl restart xrdp` |
| MT5 startet nicht (Linux) | Wine-Installation unvollständig. `./mt5ubuntu.sh` erneut ausführen |
| EA-Panel erscheint nicht | Algo-Trading nicht grün, oder EA nicht auf den Chart gezogen |
| Panel zeigt dauernd `AVOID` | Wochenende, Rollover (21–23 UTC) oder Markt geschlossen. Richtig so |
| Panel `PRIME`, aber nichts passiert | Kein Setup. Die meisten Kerzen sind keine Gelegenheit — Nichtstun ist der Normalfall |
| „Cannot size" im Journal | Konto zu klein für die Stop-Distanz — siehe oben |
| MT5 weg nach dem Trennen | Du hast dich abgemeldet statt nur das Fenster zu schließen |
