"""Root conftest - put each skill's scripts/ directory on sys.path.

Skill scripts import their siblings as top-level modules (``import cache``) so
they can run standalone via ``python scripts/fetch_candles.py``. Pytest needs
the same directories on sys.path to import them.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent


def _skill_root(filepath: Path) -> "Path | None":
    """Return the directory containing SKILL.md for *filepath*, if any."""
    for parent in filepath.parents:
        if (parent / "SKILL.md").exists():
            return parent
    return None


def _activate_skill(skill: Path) -> None:
    """Ensure this skill's scripts directory is first on sys.path."""
    scripts_dir = str(skill / "scripts")
    if sys.path and sys.path[0] == scripts_dir:
        return
    try:
        sys.path.remove(scripts_dir)
    except ValueError:
        pass
    sys.path.insert(0, scripts_dir)


def pytest_collectstart(collector) -> None:
    fspath = getattr(collector, "path", None) or getattr(collector, "fspath", None)
    if fspath is None:
        return
    path = Path(str(fspath))
    if path.suffix != ".py":
        return
    skill = _skill_root(path)
    if skill is not None:
        _activate_skill(skill)


def pytest_runtest_setup(item) -> None:
    fspath = getattr(item, "path", None) or getattr(item, "fspath", None)
    if fspath is None:
        return
    skill = _skill_root(Path(str(fspath)))
    if skill is not None:
        _activate_skill(skill)
