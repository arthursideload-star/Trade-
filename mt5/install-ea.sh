#!/bin/sh
# Install GoldScalpAssistant into the MetaTrader 5 docker container.
#
# Run this in the container terminal (Hostinger: Docker Manager -> the
# metatrader project -> Zugriff -> Terminal). It does, in order:
#
#   1. prints the CUSTOM_USER / PASSWORD the browser login asks for
#   2. finds the terminal's MQL5/Experts folder
#   3. downloads the expert advisor and verifies it arrived complete
#   4. compiles it, if MetaEditor can be driven from the command line
#
# Nothing here places a trade, changes a risk limit, or touches an account.
# It is safe to run more than once.
#
# POSIX sh on purpose: the image is not guaranteed to have bash.
#
# Written for https://github.com/arthursideload-star/Trade-

set -u

BRANCH="claude/trading-bot-plan-4uj86r"
RAW="https://raw.githubusercontent.com/arthursideload-star/Trade-/refs/heads/${BRANCH}/mt5/Experts/GoldScalpAssistant.mq5"

# Checked against the real file by tests/test_mt5_parity.py, so that a
# truncated download is caught here rather than by a confusing compiler error
# forty minutes later.
EXPECTED_LINES=1649

say()  { printf '%s\n' "$*"; }
rule() { say "------------------------------------------------------------"; }
ok()   { printf '  OK    %s\n' "$*"; }
bad()  { printf '  FAIL  %s\n' "$*"; }

say ""
say "GoldScalpAssistant -- container install"
rule

# --- 1. The credentials the browser login wants ----------------------------
#
# This is the step that strands people. The KasmVNC page uses HTTP basic
# auth, and a rejected attempt re-displays the same empty dialog with no
# error -- so a wrong password looks exactly like a broken page. These two
# values are what it wants. They are read from the running container's
# environment and printed here; they are not stored anywhere by this script.

say ""
say "1. Login for the MT5 browser window"
rule
CU=$(printenv CUSTOM_USER 2>/dev/null || true)
PW=$(printenv PASSWORD 2>/dev/null || true)

if [ -n "${CU}" ] || [ -n "${PW}" ]; then
    say "  username: ${CU:-<empty>}"
    say "  password: ${PW:-<empty>}"
    say ""
    say "  Type them exactly. Case matters, and a trailing space added by a"
    say "  phone keyboard is enough to be rejected."
else
    say "  CUSTOM_USER and PASSWORD are not set in this container."
    say "  Try username 'abc' with password 'abc' -- the default of the base"
    say "  image this template builds on."
fi

# --- 2. Where MetaTrader keeps its experts ---------------------------------

say ""
say "2. Locating the terminal's MQL5/Experts folder"
rule

if [ ! -d /config/.wine ]; then
    say "  /config/.wine does not exist here."
    say ""
    say "  That almost always means this is the VPS terminal rather than the"
    say "  container terminal. They are two different buttons: the one at the"
    say "  top of the Docker Manager page opens the VPS, the one under"
    say "  'Zugriff' next to the metatrader project opens the container."
    say "  Close this tab and use the lower one."
    exit 1
fi
ok "inside the container"

EXPERTS=$(find / -type d -path "*MQL5/Experts" 2>/dev/null | head -n 1)
if [ -z "${EXPERTS}" ]; then
    bad "no MQL5/Experts folder found"
    say ""
    say "  MetaTrader may not have finished its first start. Open the MT5"
    say "  window once, let it settle, then run this again. If it is running,"
    say "  read the path from File -> Open Data Folder and copy the file there"
    say "  by hand."
    exit 1
fi
ok "${EXPERTS}"

# --- 3. Download, and prove it arrived whole -------------------------------

say ""
say "3. Downloading the expert advisor"
rule

TARGET="${EXPERTS}/GoldScalpAssistant.mq5"
TMP="${TARGET}.part"

if command -v wget >/dev/null 2>&1; then
    wget -q -O "${TMP}" "${RAW}"
    RC=$?
elif command -v curl >/dev/null 2>&1; then
    curl -sSL -o "${TMP}" "${RAW}"
    RC=$?
else
    bad "neither wget nor curl is available in this container"
    say "  Install one with: apk add curl   (or)   apt-get install -y curl"
    exit 1
fi

if [ ${RC} -ne 0 ] || [ ! -s "${TMP}" ]; then
    bad "download failed (exit ${RC})"
    rm -f "${TMP}"
    say "  Check the container has outbound network access, then retry."
    exit 1
fi

# Download to a temporary name and only move it into place once the line
# count proves it is complete. A half-written .mq5 left in the Experts folder
# is worse than none: it compiles to confusing errors that look like bugs.
LINES=$(wc -l < "${TMP}" | tr -d ' ')
if [ "${LINES}" != "${EXPECTED_LINES}" ]; then
    bad "got ${LINES} lines, expected ${EXPECTED_LINES} -- the file is incomplete"
    rm -f "${TMP}"
    say "  Nothing was installed. Run this script again; if the number is"
    say "  still wrong, send me what it says."
    exit 1
fi

mv "${TMP}" "${TARGET}"
ok "${LINES} lines, complete"
ok "installed at ${TARGET}"

# --- 4. Compile, if that can be done without the GUI -----------------------
#
# Optional by design. When it works it removes the fiddliest step of the
# whole setup; when it does not, the GUI route still works and the script
# must not present a failure here as a failure overall.

say ""
say "4. Compiling"
rule

EDITOR=$(find / -name "metaeditor64.exe" 2>/dev/null | head -n 1)
COMPILED=0

if [ -z "${EDITOR}" ]; then
    say "  MetaEditor was not found, so this step is skipped."
elif ! command -v wine >/dev/null 2>&1; then
    say "  wine is not on PATH, so this step is skipped."
else
    WIN_PATH=$(winepath -w "${TARGET}" 2>/dev/null || printf '%s' "${TARGET}")
    wine "${EDITOR}" /compile:"${WIN_PATH}" /log >/dev/null 2>&1
    LOG="${EXPERTS}/GoldScalpAssistant.log"
    if [ -f "${EXPERTS}/GoldScalpAssistant.ex5" ]; then
        ok "compiled -- GoldScalpAssistant.ex5 created"
        COMPILED=1
    else
        say "  Command-line compile did not produce an .ex5."
        [ -f "${LOG}" ] && { say ""; say "  Compiler said:"; \
            sed -n '1,25p' "${LOG}" | sed 's/^/    /'; }
    fi
fi

[ "${COMPILED}" -eq 0 ] && {
    say ""
    say "  Compile it from the GUI instead -- it takes about a minute:"
    say "    MetaEditor (the IDE button in the MT5 toolbar; F4 is swallowed"
    say "    by the browser) -> Navigator -> Experts ->"
    say "    GoldScalpAssistant.mq5 -> Compile."
    say "    Expected: 0 errors, 0 warnings."
}

# --- What is left, and what it should look like ----------------------------

say ""
say "Remaining steps -- these need the MT5 window"
rule
say "  a. Connect a DEMO account funded with about 1000 USD."
say "     Not 100000 (you would practise sizes you will never trade) and"
say "     not 55 (every gold trade would be refused as over the 1% limit)."
say "  b. Open XAUUSD on the M5 timeframe. M5 is required -- the EA reads it."
say "  c. Drag GoldScalpAssistant onto that chart, tick 'Allow Algo Trading'."
say "  d. Turn on the Algo Trading button in the toolbar until it is green."
say ""
say "  It is working when the chart shows a smiling face top right and the"
say "  panel top left reads [ADVISOR]. Advisor means it finds and reports"
say "  setups without placing orders, which is where this belongs until"
say "  there are numbers to justify anything else."
say ""
say "  From then on it writes every signal and every closed trade to"
say "  MQL5/Files/GoldScalpAssistant.csv. Read that with:"
say "      python -m metals journal --file GoldScalpAssistant.csv"
say ""
rule
say "Done."
say ""
