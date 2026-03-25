from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
README_PATH = PROJECT_ROOT / 'README.md'
DOC_PATH = PROJECT_ROOT / 'docs' / 'hardware-testing.md'


def test_readme_links_to_detailed_hardware_test_guide() -> None:
    readme = README_PATH.read_text(encoding='utf-8')

    assert 'See `docs/hardware-testing.md` for the full checklist' in readme


def test_hardware_guide_covers_requirements_and_execution_steps() -> None:
    guide = DOC_PATH.read_text(encoding='utf-8')

    assert '# Hardware testing' in guide
    assert '## Requirements' in guide
    assert 'real Novitus fiscal printer' in guide
    assert 'NoviAPI service reachable over HTTP' in guide
    assert 'NOVIAPI_BASE_URL' in guide
    assert '--run-hardware' in guide
    assert 'uv run pytest tests/hardware -m hardware --run-hardware' in guide
    assert '--run-hardware-stateful' in guide
    assert 'comm_test' in guide
    assert 'queue_check' in guide
    assert 'status_send' in guide
    assert 'status_confirm' in guide
    assert 'status_check' in guide
    assert 'Do not run hardware tests against a production printer' in guide
    assert 'PYTEST_XDIST_WORKER' in guide or 'parallel' in guide
