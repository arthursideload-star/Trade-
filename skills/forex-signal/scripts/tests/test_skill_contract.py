"""Tests that SKILL.md matches the scripts it documents."""

from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[2]
SKILL_MD = SKILL_DIR / "SKILL.md"


def _text():
    return SKILL_MD.read_text(encoding="utf-8")


def _frontmatter() -> dict:
    text = _text()
    assert text.startswith("---\n")
    _p, raw, _b = text.split("---", 2)
    meta = {}
    for line in raw.strip().splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    return meta


def test_name_is_forex_signal():
    assert _frontmatter()["name"] == "forex-signal"


def test_reference_card_exists_and_is_named():
    assert (SKILL_DIR / "references" / "empfehlungskarte.md").is_file()
    assert "references/empfehlungskarte.md" in _text()


def test_scripts_exist():
    scripts = SKILL_DIR / "scripts"
    assert (scripts / "signal_score.py").is_file()
    assert (scripts / "recommend.py").is_file()


def test_document_describes_the_top_down_workflow():
    text = _text()
    assert "Top-Down" in text
    assert "R1-R8" in text


def test_document_states_no_profit_guarantee():
    text = _text().lower()
    assert "keine gewinngarantie" in text


def test_document_names_the_need_input_rules():
    text = _text()
    assert "R2" in text and "R4" in text
