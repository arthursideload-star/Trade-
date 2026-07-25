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


def test_name_is_forex_analysis():
    assert _frontmatter()["name"] == "forex-analysis"


def test_reference_file_exists_and_is_named():
    assert (SKILL_DIR / "references" / "methodik.md").is_file()
    assert "references/methodik.md" in _text()


def test_documented_modules_all_exist():
    scripts = SKILL_DIR / "scripts"
    for module in ("indicators.py", "regime.py", "levels.py", "patterns.py", "analyze.py"):
        assert (scripts / module).is_file(), f"missing {module}"


def test_document_states_it_only_computes_not_recommends():
    text = _text().lower()
    assert "empfiehlt nicht" in text or "keine" in text
    assert "forex-signal" in text


def test_document_is_honest_about_missing_volume():
    assert "Volumen" in _text()
