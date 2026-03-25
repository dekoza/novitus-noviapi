from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
README_PATH = PROJECT_ROOT / 'README.md'


def test_readme_covers_async_auth_errors_and_hardware_section() -> None:
    readme = README_PATH.read_text(encoding='utf-8')

    assert '## Async quick start' in readme
    assert 'NoviApiAsyncClient' in readme
    assert '## Authentication' in readme
    assert 'token_get()' in readme
    assert 'token_refresh()' in readme
    assert '## Error handling' in readme
    assert 'AuthenticationError' in readme
    assert 'TooManyTokenRequestsError' in readme
    assert '## Hardware testing' in readme
    assert '--run-hardware' in readme
    assert 'NOVIAPI_BASE_URL' in readme


def test_readme_ends_with_novitus_thank_you_note() -> None:
    readme = README_PATH.read_text(encoding='utf-8').rstrip()

    assert readme.endswith(
        'Thank you to Novitus for lending a development kit for this work.'
    )
