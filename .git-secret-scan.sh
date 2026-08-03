#!/bin/sh
# Refuse a commit that carries something private into the repository.
#
# Written after I committed the user's MetaTrader account number, which I
# had read off a screen recording thirty seconds earlier. My check at the
# time was:
#
#     grep -rn -E "<patterns>" . ; echo "SCAN CLEAN"
#
# The echo ran unconditionally. It printed the matches AND the word CLEAN,
# and I read the word. **A check whose output does not change when it finds
# something is not a check.** This one exits non-zero.
#
# Second lesson, from the first version of this very script: `for p in
# $PATTERNS` splits on whitespace, so a pattern containing a space became
# three patterns -- one of which was a bare `[0-9]{8,9}` that matched every
# timestamp in the ledger. Read line by line.
set -u
STATUS=0
HERE=$(basename "$0")

check() {
    # $1 = pattern, $2 = what it is
    if grep -rnE "$1" . --exclude-dir=.git --exclude="$HERE" \
            --exclude="*.jsonl" 2>/dev/null; then
        echo "REFUSED: $2" >&2
        STATUS=1
    fi
}

check 'Aa2DMW7KfuK6'                    "a password"
check 'frankarthur588@gmail\.com'       "a private email address"
check '168\.231\.108\.96'               "a server address"
check 'srv1788943'                      "a server hostname"

# A live MetaTrader account number, in the shape MT5 puts in its title bar.
# Demo or not, it identifies the person and belongs in nobody's checkout.
check '[0-9]{8,9} *- *MetaQuotes'       "a MetaTrader account number"
check '(Kontonummer|account number)[^0-9]{0,12}[0-9]{8,9}' \
                                        "an account number"

if [ "$STATUS" -eq 0 ]; then
    echo "clean"
fi
exit "$STATUS"
