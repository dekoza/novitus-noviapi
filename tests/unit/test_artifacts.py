from __future__ import annotations

import tarfile
import zipfile
from pathlib import Path

import pytest

from noviapi import __version__

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DIST_DIR = PROJECT_ROOT / 'dist'
WHEEL_PATTERN = f'novitus_noviapi-{__version__}-*.whl'
SDIST_PATTERN = f'novitus_noviapi-{__version__}.tar.gz'


def _find_single_artifact(dist_dir: Path, pattern: str, *, kind: str) -> Path:
    matches = sorted(dist_dir.glob(pattern))
    if len(matches) == 1:
        return matches[0]

    found = ', '.join(path.name for path in matches) if matches else 'none'
    raise AssertionError(
        f'Expected exactly one {kind} matching {pattern} in {dist_dir}, found {found}'
    )


def _wheel_members() -> list[str]:
    wheel_path = _find_single_artifact(DIST_DIR, WHEEL_PATTERN, kind='wheel')
    with zipfile.ZipFile(wheel_path) as archive:
        return sorted(archive.namelist())


def _sdist_members() -> list[str]:
    sdist_path = _find_single_artifact(DIST_DIR, SDIST_PATTERN, kind='sdist')
    with tarfile.open(sdist_path, 'r:gz') as archive:
        return sorted(member.name for member in archive.getmembers() if member.isfile())


def test_find_single_artifact_selects_current_version_from_stale_dist_dir(
    tmp_path: Path,
) -> None:
    stale_wheel = tmp_path / 'novitus_noviapi-0.1.0-py3-none-any.whl'
    stale_wheel.write_bytes(b'')
    current_wheel = tmp_path / f'novitus_noviapi-{__version__}-py3-none-any.whl'
    current_wheel.write_bytes(b'')

    selected = _find_single_artifact(tmp_path, WHEEL_PATTERN, kind='wheel')

    assert selected == current_wheel


def test_find_single_artifact_raises_clear_error_when_current_version_is_missing(
    tmp_path: Path,
) -> None:
    with pytest.raises(AssertionError, match='Expected exactly one wheel matching'):
        _find_single_artifact(tmp_path, WHEEL_PATTERN, kind='wheel')


def test_wheel_contains_only_runtime_package_files() -> None:
    members = _wheel_members()

    assert 'noviapi/__init__.py' in members
    assert 'noviapi/_release_smoke.py' in members
    assert 'noviapi/client.py' in members
    assert 'noviapi/models.py' in members
    assert 'noviapi/exceptions.py' in members
    assert 'noviapi/py.typed' in members
    assert all('tests/' not in member for member in members)
    assert all('contracts/' not in member for member in members)
    assert all('examples/' not in member for member in members)
    assert all('scripts/' not in member for member in members)


def test_sdist_contains_only_runtime_sources_and_metadata() -> None:
    members = _sdist_members()

    assert any(member.endswith('/pyproject.toml') for member in members)
    assert any(member.endswith('/README.md') for member in members)
    assert any(member.endswith('/LICENSE') for member in members)
    assert any(member.endswith('/src/noviapi/__init__.py') for member in members)
    assert any(member.endswith('/src/noviapi/_release_smoke.py') for member in members)
    assert any(member.endswith('/src/noviapi/client.py') for member in members)
    assert any(member.endswith('/src/noviapi/models.py') for member in members)
    assert any(member.endswith('/src/noviapi/exceptions.py') for member in members)
    assert all('/tests/' not in member for member in members)
    assert all('/contracts/' not in member for member in members)
    assert all('/examples/' not in member for member in members)
    assert all('/scripts/' not in member for member in members)
