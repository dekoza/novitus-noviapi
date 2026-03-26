from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PYPROJECT_PATH = PROJECT_ROOT / 'pyproject.toml'
README_PATH = PROJECT_ROOT / 'README.md'


def test_project_classifier_is_no_longer_alpha() -> None:
    pyproject = PYPROJECT_PATH.read_text(encoding='utf-8')

    assert 'Development Status :: 3 - Alpha' not in pyproject
    assert 'Development Status :: 4 - Beta' in pyproject


def test_readme_status_section_no_longer_claims_release_blockers_are_planned() -> None:
    readme = README_PATH.read_text(encoding='utf-8')

    assert 'additional release automation are still planned' not in readme
    assert 'broader hardware coverage' not in readme
    assert 'manual hardware validation' in readme
    assert 'outside GitHub' in readme
