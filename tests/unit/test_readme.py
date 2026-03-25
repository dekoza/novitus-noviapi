from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
README_PATH = PROJECT_ROOT / 'README.md'


def test_readme_covers_async_auth_errors_and_hardware_section() -> None:
    readme = README_PATH.read_text(encoding='utf-8')

    assert '## Async quick start' in readme
    assert 'NoviApiAsyncClient' in readme
    assert "NoviApiClient('http://127.0.0.1:8888/api/v1')" in readme
    assert "NoviApiAsyncClient('http://127.0.0.1:8888/api/v1')" in readme
    assert 'await client.comm_test()' in readme
    assert 'if not await client.comm_test()' in readme
    assert '## Authentication' in readme
    assert 'token_get()' in readme
    assert 'token_refresh()' in readme
    assert '`comm_test()` returns `True` for `200 OK`' in readme
    assert 'returns `False` for unusual non-error' in readme
    assert 'responses such as redirects' in readme
    assert 'raises on transport errors or HTTP responses' in readme
    assert '`>= 400`.' in readme
    assert '## Error handling' in readme
    assert 'AuthenticationError' in readme
    assert 'TooManyTokenRequestsError' in readme
    assert 'trio-based apps' not in readme
    assert 'uvloop' not in readme
    assert '## Hardware testing' in readme
    assert '--run-hardware' in readme
    assert 'NOVIAPI_BASE_URL' in readme
    assert 'export NOVIAPI_BASE_URL="http://192.168.1.50:8888/api/v1"' in readme
    assert 'non-fiscal printout' in readme
    assert 'Greetings from the test suite!' in readme
    assert 'points either at the printer root' in readme
    assert 'rejects ambiguous subpaths' in readme
    assert (
        'hardware acceptance tests and additional release automation are still planned'
        not in readme
    )
    assert 'broader hardware coverage' in readme
    assert 'additional release' in readme
    assert 'hardware test suite' in readme
