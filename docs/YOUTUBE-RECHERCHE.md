# Was im Netz über Gold-Scalping-Bots steht — und was davon standhält

Recherchestand: 29.07.2026. Durchsucht wurde das öffentlich zugängliche Material zu
Gold-Scalping-Bots: YouTube-Titel und -Beschreibungen zu EA-Reviews und
„90 % Trefferquote"-Strategien, Anbieterseiten, Broker- und Prop-Firm-Blogs,
MQL5-Forum und -Blogs, Aufsichtsdokumente und die akademische Literatur zu
Daytrading-Ergebnissen.

**Was ich nicht konnte, damit das klar ist:** Ich habe die Videos nicht angesehen.
Diese Umgebung kann YouTube-Videoinhalte nicht abspielen. Gelesen habe ich Titel,
Beschreibungen, Suchtreffer-Zusammenfassungen und das schriftliche Material rundherum.
Für die Behauptungen, um die es geht, reicht das — die stehen im Titel. Für eine
Beurteilung der gezeigten Kontoauszüge reicht es nicht, und die beurteile ich deshalb
auch nicht.

## Warum das hier keine Zitatsammlung ist

Fast alles in diesem Themenfeld ist Werbung, und Werbung ist kein Wissen. Was sich
lohnt zu übernehmen, ist der Teil, der eine **überprüfbare Aussage** macht. Jede davon
steht in `metals/claims.py` als Behauptung mit Quelle und Quellenart — und wird dort
gemessen statt wiederholt.

```bash
python -m metals claims            # der Katalog
python -m metals claims --measure  # die prüfbaren Behauptungen tatsächlich messen
```

Drei Quellenarten, bewusst getrennt gehalten:

| Art | Was das ist | Wie damit umgegangen wird |
|---|---|---|
| **Anbieter** | Wer das Ding verkauft: Produktseiten, YouTube-Thumbnails mit Trefferquote | Hypothese, nie Zahl |
| **Fachpresse** | Broker-Blogs, Trading-Schulen, Forenbeiträge | Bei Mechanik (Spread, Sessions, Ausführung) meist richtig, bei Ergebnissen unbelegt |
| **Aufsicht / Wissenschaft** | Zahlen, für die jemand geradestehen musste | Als Fakt zitiert — aber als Basisrate über eine Population, nicht als Prognose für ein Konto |

## Die zwölf Behauptungen

### C1 — „90 % Trefferquote" · Anbieter · **messbar, und das Ergebnis ist der wichtigste Fund**

Die Behauptung stimmt meistens. Sie sagt trotzdem nichts.

Gemessen mit unserer eigenen Strategie, gleicher Markt, gleiche Regeln, nur das
Verhältnis von Ziel zu Stop verschoben:

| | Trefferquote | Erwartungswert je Trade |
|---|---:|---:|
| Standardregeln | 61,6 % | **+0,139 R** |
| auf Quote gedreht (Mitnahme bei 5 %, Stop bei 300 % der Vorhersage) | **94,8 %** | +0,012 R |

Die Trefferquote ist eine Stellschraube. Ziel näher, Stop weiter — fertig ist die
94-Prozent-Zahl fürs Thumbnail, und der Verdienst je Trade ist praktisch weg. Wer eine
Trefferquote nennt, ohne den Erwartungswert danebenzustellen, hat nichts gesagt.

*Einschränkung, die ich nicht verschweige:* In diesem Durchlauf war die gedrehte
Variante auch im schlechtesten Markt nicht schlechter als die Standardvariante. Der
weite Stop wurde selten erreicht, weil vorher der Zeit-Stop griff. Der übliche
Zusatzvorwurf „und dann kommt der eine Riesenverlust" ist hier also **nicht** belegt.
Belegt ist nur — und das reicht —, dass die Quote nichts über den Ertrag aussagt.

### C2 — „Auf einem Konto mit weitem Spread ist die Kante weg" · Fachpresse · **messbar, gilt für uns nicht**

Für Tick-Scalper stimmt es. Für unsere Strategie nicht, und der Grund ist lehrreich.

| Spread | Erwartungswert |
|---:|---:|
| 0,00 $ | +0,154 R |
| 0,15 $ (ECN) | +0,140 R |
| 0,40 $ (Standardkonto) | +0,136 R |
| 1,20 $ | +0,080 R |

Keine Nulllinie im gesamten geprüften Bereich. Grund: unser Ziel liegt im Schnitt
**31,23 $/oz** entfernt, ein Standard-Spread ist davon 1,3 %. Ein Tick-Scalper mit
0,10 $ Ziel zahlt beim selben Spread das **Vierfache seines Ziels** — dort stimmt die
Behauptung, und genau deshalb gilt sie für uns nicht.

Das ist ein Vorteil der Taktik, die du vorgegeben hast: Wer eine größere Bewegung
vorhersagt und die Hälfte davon mitnimmt, ist gegen Brokerkosten weitgehend
unempfindlich. Ein billiger Broker bleibt besser, aber er entscheidet nicht.

### C3 — „London/New-York-Overlap handeln, Asien meiden" · Fachpresse · **messbar, bringt hier nichts**

| Fenster | Erwartungswert | Trades |
|---|---:|---:|
| alle Stunden | +0,171 R | 28 |
| Overlap 12–16 UTC | +0,142 R | 10 |
| Asien 0–6 UTC | +0,049 R | 6 |

Der Filter kostet 63 % der Trades und bringt keinen besseren Erwartungswert.

Mechanismus: Unser Stop skaliert mit der vorhergesagten Bewegung. In einer volatilen
Stunde ist die Vorhersage größer, der Stop entsprechend weiter — die Volatilität kürzt
sich aus dem R heraus. Die übliche Empfehlung stammt von Strategien mit **festem
Pip-Ziel**, wo sie sich nicht auskürzt.

*Vorbehalt:* Der Simulator hat ein Sessionprofil eingebaut, weil Gold eines hat. Dieser
Test ist damit teilweise zirkulär. Der Mechanismus überträgt sich trotzdem, weil er
Arithmetik ist.

### C4 — „M1 ist zu verrauscht, nimm M5 oder M15" · Fachpresse · **messbar, Ergebnis voreingenommen**

Dieselben Märkte, aus denselben M1-Kerzen zusammengefasst:

| Zeiteinheit | Erwartungswert | Trades |
|---|---:|---:|
| M1 | +0,069 R | 68 |
| M5 | +0,061 R | 43 |
| M15 | +0,026 R | 21 |

M1 gewinnt — **und das Ergebnis ist nicht zu trauen.** Der Simulator kennt weder
Requotes noch Slippage noch schwankende Spreads. Genau das macht M1 in der Realität
teuer. Der Vorsprung von M1 ist hier eine Obergrenze, kein Befund. Die Frage gehört auf
echte Tickdaten, und die gibt es am PC.

### C5 — „Grid und Martingale erzeugen lange Gewinnserien und dann die Null" · Fachpresse · **belegt, an anderer Stelle**

Gemessen in [MICRO-SCALPING.md](./MICRO-SCALPING.md) und in der
[Werbevideo-Analyse](./WERBEVIDEO-ANALYSE.md): 0,02 Lot, acht Positionen, winziges Ziel,
kein Stop — 95 % Treffer, Median **−92,6 %**, 92 % Stop-out. Genau das Muster, das die
Foren beschreiben.

### C6 — „74–89 % der Retail-CFD-Konten verlieren Geld" · **Aufsicht**

Aus der ESMA-Produktinterventionsmaßnahme; jeder EU-Broker muss seinen eigenen Wert
ausweisen. Aktuelle Broker-Warnhinweise liegen meist zwischen 65 % und 82 %.

Das ist eine Basisrate über eine Population, keine Prognose für ein Konto. Sie sagt
nicht „du wirst verlieren". Sie sagt, dass die Ausgangswahrscheinlichkeit gegen einen
läuft und ein Verfahren, das das umkehrt, das erst zeigen muss.

### C7 — „Rund 1 % der Daytrader sind dauerhaft profitabel" · **Wissenschaft**

Barber/Lee/Liu/Odean, gesamte Taiwan Stock Exchange 1992–2006: unter 1 % erzielten
dauerhaft positive Erträge nach Kosten. Chague/De-Losso/Giovannetti, 19.646 brasilianische
Index-Futures-Daytrader 2013–2015: von den rund 1.600, die über 300 Handelstage
durchhielten, verloren **97 %** Geld.

*Einschränkung:* Aktien und Index-Futures, nicht Gold-CFDs, und über Menschen, nicht über
einen Bot. Wird als das geführt, was es ist.

### C8 — „Spreads gehen bei CPI/NFP von 1–2 auf 15–20 Punkte, dazu Slippage" · Fachpresse · hier nicht messbar

Braucht Tickdaten mit Nachrichtenkalender. Die Regel R4 (Nachrichtensperre) setzt es
bereits voraus — das ist die richtige Reaktion, auch ohne eigene Messung.

### C9 — „99 % Modellierungsqualität heißt nicht realistisch" · Fachpresse · hier nicht messbar

Erzeugte Ticks schmeicheln Einstiegen, die einen Kurs nur berühren müssen. Betrifft den
Strategietester-Lauf des EA, also den Schritt am PC. Dort gilt: **„Every tick based on
real ticks"**, alles andere ist Dekoration.

### C10 — „Ab etwa 1.000 $ Mindesteinlage" · Anbieter · **messbar, zu niedrig**

Reine Arithmetik, bei 1:20 (EU-Retail-Obergrenze für Gold) und 4.100 $/oz:

| Position | Margin |
|---|---:|
| 0,01 Lot | 205 $ |
| 0,10 Lot | **2.050 $** |

Für 0,01 Lot reichen 1.000 $ bequem. Für 0,10 Lot — die Größe, mit der die meisten
dieser EAs beworben werden — reicht es nicht einmal für die Margin, bevor der Kurs sich
überhaupt bewegt hat.

### C11 — „Swap auf Gold ist schwer und asymmetrisch" · Fachpresse · **messbar, stimmt — und war bei uns gar nicht im Modell**

Long XAUUSD kostet rund **−73,60 $ je Standard-Lot und Nacht**, Short bringt **+30 $**.
Mittwochs dreifach. Das Modell hat diese Kosten vorher **überhaupt nicht berechnet**.

| 0,10 Lot gehalten | long | short |
|---:|---:|---:|
| 1 Nacht | −7,36 $ | +3,00 $ |
| 7 Nächte | −51,52 $ | +21,00 $ |
| 30 Nächte | **−220,80 $** | +90,00 $ |
| 90 Nächte | −662,40 $ | +270,00 $ |

Eingebaut (`swap_long_usd_per_lot`, Rollover 21:00 UTC, Mittwoch dreifach). Gemessene
Wirkung auf unsere Strategie: **0,14 Prozentpunkte** über 20.000 Bars — ein Rundungsfehler,
weil der 4-Stunden-Zeitstop die Positionen gar nicht erst über den Rollover trägt.

Der Befund ist trotzdem wichtig, nur an anderer Stelle: **Ein Stop begrenzt nicht nur den
Verlust, sondern auch die Zeit, in der er finanziert werden muss.** Wer eine Verlustposition
aussitzt — das Prinzip aus den Werbevideos — zahlt Miete, solange sie falsch ist. 0,10 Lot
long, einen Monat gehalten, sind 220,80 $ allein an Finanzierung, also über die Hälfte eines
400-€-Kontos.

Und die Asymmetrie ist nicht neutral: Wer zufällig short feststeckt, **bekommt** Carry. Wer
long feststeckt, blutet. Ein Bot ohne Stop hat damit eine Richtungsabhängigkeit, die nichts
mit seiner Analyse zu tun hat.

### C12 — „Broker erzwingen einen Mindestabstand für Stop und Ziel" · Fachpresse · **messbar, und es trifft genau die Werbevideo-Taktik**

Das **Stops Level** ist der Mindestabstand, den SL und TP vom aktuellen Kurs haben müssen.
Auf Gold typisch **50–100 Punkte = 0,50–1,00 $**. Meldet ein Broker null, heißt das meist
nicht „kein Minimum", sondern dass er ihn live aus dem Spread berechnet — üblich das Zwei-
bis Dreifache.

| Strategie | Ziel | platzierbar bei 50 Punkten? |
|---|---:|---|
| Tagesspanne (unsere) | 31,23 $ | ja, um Faktor 62 |
| Micro-Scalp aus dem Werbevideo | **0,10 $** | **nein — wird abgelehnt** |

Wichtig ist, das richtig zu formulieren: Ein Ziel innerhalb des Mindestabstands lässt sich
nicht als **Order** senden. Es geht trotzdem, indem man bei Gewinn **am Markt schließt** —
und genau das zeigen die Videos ja auch. Nur zahlt man dann den Spread ein zweites Mal und
nimmt die Slippage mit.

Die Taktik wird dadurch also nicht unmöglich, sondern **teurer** — bei einem Ziel von 0,10 $
und einem Spread von 0,34 $ zahlt man mehr als das Dreifache des Ziels an Kosten. Das ist
dieselbe Rechnung wie in C2, nur diesmal von der Plattformseite bestätigt.

## Was daraus in den Bot eingebaut wurde

Nicht die Behauptungen. Die Konsequenzen:

1. **`metals/claims.py`** — der Katalog mit Quellenart und die Messungen. Neue
   Behauptungen kommen dort hinein, nicht in eine Prosa-Datei.
2. **Session- und Zeiteinheit-Regler in `dayrange`** (`trade_hours_utc`, `bars_per_day`)
   — eingebaut, damit die Behauptungen prüfbar sind, **standardmäßig aus**, weil die
   Messung sie nicht stützt. Ein Filter ohne Beleg ist eine Verschlechterung mit
   Begründung.
3. **`metals/candles.resample`** — damit ein Zeiteinheit-Vergleich denselben Markt
   sieht und nicht zwei verschiedene.
4. **Risikobasierte Positionsgröße** (`risk_pct`) — siehe [REPO-AUDIT.md](./REPO-AUDIT.md),
   Befund A1. Das ist der Fund, der aus dieser Recherche am meisten wert war.

## Quellen

**Anbieter / YouTube** (als Hypothesen geführt, nicht als Belege)
- [89.2% Win Rate 15 Minute Scalping Strategy (Gold Trading)](https://www.youtube.com/watch?v=Qk1MWbazU7k)
- [This 90% WIN RATE Scalping Strategy Should Be Illegal](https://www.youtube.com/watch?v=ll_9xH10KPY)
- [Scalping EA · Propfirm Version · 90% Win Rate (forward test)](https://www.youtube.com/watch?v=jx3VqTcfb0k)
- [Full Code · GOLD Trading Robot · 90% win · Tight SL](https://www.youtube.com/watch?v=rFNhxfMgQ8o)
- [$99 Gold Scalping Robot: Prime Scalper EA Review](https://www.youtube.com/watch?v=ccrrz62_D0g)
- [XAUBOT Review](https://www.youtube.com/watch?v=lgkpC9ry3qA)
- [The Best Gold Scalping Trading Bots I've Ever Traded](https://www.youtube.com/watch?v=xx8e-KTEBT8)
- [Free Gold EA with NO Grid or Martingale](https://www.youtube.com/watch?v=CUxYFiawVB8)
- [Pro-Scalper — Automated Gold Trading Strategy](https://www.pro-scalper.com/automated-gold-trading-strategy)
- [Trade Wizards — Best Gold Scalping Expert Advisor for XAUUSD](https://tradewizards.org/best-gold-scalping-expert-advisor-for-xauusd-traders/)

**Fachpresse**
- [XS — Gold (XAUUSD) Scalping Trading Strategy 2026](https://www.xs.com/en/blog/gold-scalping-trading-strategy/)
- [Headway — A Comprehensive Review of Gold Scalping Strategies for XAU/USD](https://hw.online/faq/comprehensive-review-gold-scalping-strategies-xauusd-trading/)
- [Headway — Top Expert Advisors for Gold Trading 2026](https://hw.online/faq/best-ea-for-gold-trading/)
- [FXNX — Master XAUUSD Scalping](https://fxnx.com/en/blog/master-xauusd-scalping-for-quick-gold-gains)
- [VaultQuant — Why Your Trading Bot Fails on Gold](https://medium.com/@chemosellesceince/why-your-trading-bot-fails-on-gold-and-what-actually-works-in-2026-84bea84849e7)
- [MQL5 Blogs — How to Choose a Safe Forex/Gold EA (Avoid Grid, Martingale & Over-Optimization)](https://www.mql5.com/en/blogs/post/766446)
- [Forex Robot Lab — ABS GoldGrid EA Review](https://forexrobotlab.com/abs-goldgrid-ea-review/)
- [MQL5 Blogs — Not All 99% Backtests Are Equal](https://www.mql5.com/en/blogs/post/762517)
- [MQL5 Forum — Which XAUUSD broker has the minimal Stops Level?](https://www.mql5.com/en/forum/428176)
- [MQL5 Articles — Broker Reality Check: Why Your EA Works on a Demo and Breaks on a Client's Broker](https://www.mql5.com/en/articles/23327)
- [EarnForex — What Is Freeze Level?](https://www.earnforex.com/guides/what-is-freeze-level/)
- [MQL5 Forum — Discrepancy between Real Ticks and Every Tick modelling](https://www.mql5.com/en/forum/472760)
- [Forex Robot Lab — MT5 Backtest Modeling & History Quality Explained](https://forexrobotlab.com/mt5-backtest-modeling-history-quality/)
- [Afterprime — XAUUSD Swap Rates (Long/Short Overnight Fee)](https://afterprime.com/swaps/xauusd)
- [Vantage — CFD Swap Rates & Overnight Fees Explained](https://www.vantagemarkets.com/en/trading/fees/swap-rates/)
- [Vantage — News Trading XAUUSD: CPI, NFP, and Rate Decisions](https://www.vantagemarkets.com/en/academy/news-trading-gold/)
- [FXNX — Gold News Trading: The 15-Minute Rule for CPI & NFP](https://fxnx.com/en/blog/mastering-xauusd-news-15-minute-rule-cpi-nfp)
- [Telegram Signals Reviews — Gold Scalper Ninja (29 % Trefferquote gegen die beworbene Zahl)](https://www.telegramsignalsreviews.com/post/gold-scalper-ninja-in-depth-review-a-high-risk-scam-channel)

**Aufsicht**
- [ESMA — Prohibition of binary options and restriction of CFDs](https://www.esma.europa.eu/press-news/esma-news/esma-agrees-prohibit-binary-options-and-restrict-cfds-protect-retail-investors)
- [Central Bank of Ireland — CFD Intervention Measure (PDF)](https://www.centralbank.ie/docs/default-source/regulation/industry-market-sectors/investment-firms/mifid-firms/regulatory-requirements-and-guidance/central-bank-cfd-intervention-measure.pdf)
- [The Investors Centre — UK CFD Trading Statistics 2026, 14 Broker verglichen](https://www.theinvestorscentre.co.uk/trading/statistics/cfd-trading/)

**Wissenschaft**
- [Barber, Lee, Liu, Odean — Do Individual Day Traders Make Money? Evidence from Taiwan (PDF)](http://www.econ.yale.edu/~shiller/behfin/2004-04-10/barber-lee-liu-odean.pdf)
- Chague, De-Losso, Giovannetti — *Day Trading for a Living?* (Brasilien, 2013–2015)
