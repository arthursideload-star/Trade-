#!/bin/sh
# Trade- : dasselbe wie START-WINDOWS.bat, fuer macOS und Linux.
#
#   chmod +x start-mac-linux.sh && ./start-mac-linux.sh
#
# Installiert nichts, laedt nichts herunter, handelt nichts. Es beantwortet
# die eine Frage: lohnt sich der Rest ueberhaupt?
#
# POSIX sh, weil nicht jede Kiste bash hat.
set -u
cd "$(dirname "$0")"

echo
echo "==================================================================="
echo "  Trade- : Gold-Bot pruefen"
echo "==================================================================="
echo

# --- 1. Python finden ------------------------------------------------
PY=""
for candidate in python3 python; do
    if command -v "$candidate" >/dev/null 2>&1; then
        if "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)' 2>/dev/null; then
            PY="$candidate"
            break
        fi
    fi
done

if [ -z "$PY" ]; then
    echo "  [FEHLT] Kein Python 3.11 oder neuer gefunden."
    echo
    echo "    macOS:  brew install python@3.12"
    echo "    Debian: sudo apt install python3"
    echo
    exit 1
fi
echo "  [OK] $("$PY" --version 2>&1)"
echo

# --- 2. Laeuft das Paket? --------------------------------------------
echo "  Pruefe, ob das Paket funktioniert ..."
if ! "$PY" -m unittest tests.test_specs_and_risk tests.test_cli_smoke -q >/dev/null 2>&1; then
    echo "  [FEHLER] Die Selbstpruefung ist fehlgeschlagen. Ausgabe:"
    echo
    "$PY" -m unittest tests.test_specs_and_risk tests.test_cli_smoke 2>&1
    exit 1
fi
echo "  [OK] Paket laeuft."
echo

# --- 3. Die Golddatei ------------------------------------------------
CSV=""
for path in XAU_5m_data.csv data/XAU_5m_data.csv; do
    [ -f "$path" ] && CSV="$path" && break
done

if [ -z "$CSV" ]; then
    cat <<EOF
  ---------------------------------------------------------------
  Es fehlt nur noch eins: die Golddatei.
  ---------------------------------------------------------------

  Kostenlos bei Kaggle:
    Suche nach "XAU USD Gold Price Historical Data"
    von novandraanugrah  ->  XAU_5m_data.csv

  Datei in DIESEN Ordner legen:
    $(pwd)

  Dann dieses Skript nochmal starten.

  Warum das die wichtigste Datei des Projekts ist:
    docs/REPO-AUDIT.md, Befund A27
EOF
    exit 0
fi

echo "  [OK] Golddatei gefunden: $CSV"
echo
echo "  Das Urteil wird berechnet. Das dauert ein bis zwei Minuten."
echo
"$PY" -m metals verdict --file "$CSV" --tz broker_gmt3 --equity 400

cat <<EOF

===================================================================
  Fertig. Das komplette Ergebnis steht oben.

  Sagt es "NICHT INSTALLIEREN", dann ist das ein Ergebnis und kein
  Rueckschlag - es hat eine halbe Stunde gekostet statt Wochen.

  Zeitzone falsch? Wenn oben eine Warnung zur Zeitzone steht,
  nochmal von Hand mit  --tz broker_gmt2  oder  --tz utc  :
    $PY -m metals verdict --file "$CSV" --tz utc --equity 400
===================================================================
EOF
