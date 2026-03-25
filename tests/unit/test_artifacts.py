from __future__ import annotations

import tarfile
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DIST_DIR = PROJECT_ROOT / 'dist'


def _wheel_members() -> list[str]:
    wheel_path = next(DIST_DIR.glob('*.whl'))
    with zipfile.ZipFile(wheel_path) as archive:
        return sorted(archive.namelist())


def _sdist_members() -> list[str]:
    sdist_path = next(DIST_DIR.glob('*.tar.gz'))
    with tarfile.open(sdist_path, 'r:gz') as archive:
        return sorted(
            member.name for member in archive.getmembers() if member.isfile()
        )


def test_wheel_contains_only_runtime_package_files() -> None:
    members = _wheel_members()

    assert 'noviapi/__init__.py' in members
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
    assert any(
        member.endswith('/src/noviapi/__init__.py') for member in members
    )
    assert any(member.endswith('/src/noviapi/client.py') for member in members)
    assert any(member.endswith('/src/noviapi/models.py') for member in members)
    assert any(
        member.endswith('/src/noviapi/exceptions.py') for member in members
    )
    assert all('/tests/' not in member for member in members)
    assert all('/contracts/' not in member for member in members)
    assert all('/examples/' not in member for member in members)
    assert all('/scripts/' not in member for member in members)
