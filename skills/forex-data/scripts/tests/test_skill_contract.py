"""Tests that SKILL.md stays in sync with the scripts it documents."""

from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[2]
SKILL_MD = SKILL_DIR / "SKILL.md"

EXPECTED_RESOURCES = (
    "references/twelvedata-api.md",
    "scripts/twelvedata_client.py",
)


def _skill_text() -> str:
    return SKILL_MD.read_text(encoding="utf-8")


def _frontmatter() -> dict:
    text = _skill_text()
    assert text.startswith("---\n"), "SKILL.md must open with YAML frontmatter"
    _prefix, raw_yaml, _body = text.split("---", 2)

    metadata = {}
    for line in raw_yaml.strip().splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            metadata[key.strip()] = value.strip()
    return metadata


def test_frontmatter_names_the_skill():
    assert _frontmatter()["name"] == "forex-data"


def test_description_mentions_the_supported_pairs_and_intervals():
    description = _frontmatter()["description"]

    assert "EUR/USD" in description
    assert "Twelve Data" in description


def test_referenced_files_exist_and_are_named_in_the_document():
    text = _skill_text()

    for rel_path in EXPECTED_RESOURCES:
        assert (SKILL_DIR / rel_path).is_file(), f"missing: {rel_path}"
        assert rel_path in text, f"not referenced in SKILL.md: {rel_path}"


def test_document_states_the_four_data_guarantees():
    """These guarantees are what the later sprints build on."""
    text = _skill_text()

    assert "aelteste zuerst" in text
    assert "null" in text
    assert "EMA200" in text
    assert "warnings" in text


def test_document_states_the_free_tier_limits():
    text = _skill_text()

    assert "8 Abrufe pro Minute" in text
    assert "800 Credits" in text


def test_documented_exit_codes_match_the_script():
    script = (SKILL_DIR / "scripts" / "fetch_candles.py").read_text(encoding="utf-8")

    assert "return 2" in script
    assert "return 1" in script
