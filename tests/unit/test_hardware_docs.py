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
    assert 'either the printer root' in guide
    assert '`http://192.168.1.50:8888/api/v1`' in guide
    assert 'normalized to `/api/v1` automatically' in guide
    assert 'trailing slash after `/api/v1` is also accepted' in guide
    assert '--run-hardware' in guide
    assert 'uv run pytest tests/hardware -m hardware --run-hardware' in guide
    assert '--run-hardware-stateful' in guide
    assert 'comm_test' in guide
    assert 'queue_check' in guide
    assert 'status_send' in guide
    assert 'status_confirm' in guide
    assert 'status_check' in guide
    assert 'nf_printout_send' in guide
    assert 'nf_printout_confirm' in guide
    assert 'nf_printout_check' in guide
    assert 'Greetings from the test suite!' in guide
    assert 'PENDING' in guide
    assert 'QUEUED' in guide
    assert 'up to three' in guide
    assert 'attempts total' in guide
    assert 'milliseconds' in guide
    assert '30_000' in guide
    assert 'Run the full hardware suite' not in guide
    assert 'Run the default hardware suite' in guide
    assert (
        'Stateful tests stay skipped unless you pass `--run-hardware-stateful`.'
        in guide
    )
    assert 'Do not run hardware tests against a production printer' in guide
    assert 'PYTEST_XDIST_WORKER' in guide or 'parallel' in guide
