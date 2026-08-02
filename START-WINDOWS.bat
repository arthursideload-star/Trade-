@echo off
REM ===================================================================
REM  Trade- : Doppelklick-Start fuer Windows
REM
REM  Macht drei Dinge, in dieser Reihenfolge:
REM    1. Prueft, ob Python da ist und neu genug (3.11+)
REM    2. Prueft, ob das Paket laeuft   (schnelle Testauswahl)
REM    3. Sucht die Golddatei und faellt das Urteil
REM
REM  Es installiert nichts, laedt nichts herunter und handelt nichts.
REM  Es beantwortet die eine Frage: lohnt sich der Rest ueberhaupt?
REM
REM  ASCII-only mit Absicht: die Windows-Konsole hat je nach Codepage
REM  ihre eigene Meinung zu Umlauten, und eine Anleitung, die als
REM  Zeichensalat startet, ist keine.
REM ===================================================================
setlocal
cd /d "%~dp0"
echo.
echo ===================================================================
echo   Trade- : Gold-Bot pruefen
echo ===================================================================
echo.

REM --- 1. Python finden ---------------------------------------------
set PY=
where py >nul 2>&1 && set PY=py -3
if "%PY%"=="" (
    where python >nul 2>&1 && set PY=python
)
if "%PY%"=="" (
    echo   [FEHLT] Python ist nicht installiert.
    echo.
    echo   Hol es hier:  https://www.python.org/downloads/
    echo   WICHTIG: beim Installieren "Add python.exe to PATH" ankreuzen.
    echo   Danach diese Datei nochmal doppelklicken.
    echo.
    pause
    exit /b 1
)

%PY% -c "import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)" 2>nul
if errorlevel 1 (
    echo   [ZU ALT] Python ist aelter als 3.11.
    %PY% --version
    echo   Bitte von https://www.python.org/downloads/ aktualisieren.
    echo.
    pause
    exit /b 1
)

for /f "delims=" %%v in ('%PY% --version 2^>^&1') do set PYVER=%%v
echo   [OK] %PYVER%
echo.

REM --- 2. Laeuft das Paket? -----------------------------------------
echo   Pruefe, ob das Paket funktioniert ...
%PY% -m unittest tests.test_specs_and_risk tests.test_cli_smoke -q >nul 2>&1
if errorlevel 1 (
    echo   [FEHLER] Die Selbstpruefung ist fehlgeschlagen.
    echo   Ausgabe zum Mitschicken:
    echo.
    %PY% -m unittest tests.test_specs_and_risk tests.test_cli_smoke 2>&1
    echo.
    pause
    exit /b 1
)
echo   [OK] Paket laeuft.
echo.

REM --- 3. Die Golddatei ---------------------------------------------
set CSV=
if exist "XAU_5m_data.csv"      set CSV=XAU_5m_data.csv
if exist "data\XAU_5m_data.csv" set CSV=data\XAU_5m_data.csv

if "%CSV%"=="" (
    echo   ---------------------------------------------------------------
    echo   Es fehlt nur noch eins: die Golddatei.
    echo   ---------------------------------------------------------------
    echo.
    echo   Kostenlos bei Kaggle:
    echo     Suche nach "XAU USD Gold Price Historical Data"
    echo     von novandraanugrah  ^-^>  XAU_5m_data.csv
    echo.
    echo   Datei in DIESEN Ordner legen:
    echo     %CD%
    echo.
    echo   Dann diese Datei nochmal doppelklicken.
    echo.
    echo   Warum das die wichtigste Datei des Projekts ist:
    echo     docs\REPO-AUDIT.md, Befund A27
    echo.
    pause
    exit /b 0
)

echo   [OK] Golddatei gefunden: %CSV%
echo.
echo   Das Urteil wird berechnet. Das dauert ein bis zwei Minuten.
echo.
%PY% -m metals verdict --file "%CSV%" --tz broker_gmt3 --equity 400

echo.
echo ===================================================================
echo   Fertig. Das komplette Ergebnis steht oben.
echo.
echo   Sagt es "NICHT INSTALLIEREN", dann ist das ein Ergebnis und kein
echo   Rueckschlag - es hat eine halbe Stunde gekostet statt Wochen.
echo.
echo   Zeitzone falsch? Wenn oben eine Warnung zur Zeitzone steht,
echo   nochmal von Hand mit  --tz broker_gmt2  oder  --tz utc  :
echo     %PY% -m metals verdict --file "%CSV%" --tz utc --equity 400
echo ===================================================================
echo.
pause
endlocal
