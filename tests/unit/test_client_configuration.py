from __future__ import annotations

import httpx
import pytest

from noviapi import NoviApiAsyncClient, NoviApiClient
from noviapi.client import _AsyncTokenProvider, _normalize_base_url, _SyncTokenProvider


def _unexpected_request(request: httpx.Request) -> httpx.Response:
    raise AssertionError(f'Unexpected request {request.method} {request.url!s}')


@pytest.mark.parametrize(
    ('value', 'expected'),
    [
        ('http://127.0.0.1:8888', 'http://127.0.0.1:8888/api/v1'),
        ('http://127.0.0.1:8888/', 'http://127.0.0.1:8888/api/v1'),
        ('https://printer.test/api/v1', 'https://printer.test/api/v1'),
        ('https://printer.test/api/v1/', 'https://printer.test/api/v1'),
        ('https://printer.test/proxy/api/v1/', 'https://printer.test/proxy/api/v1'),
    ],
)
def test_normalize_base_url_accepts_root_and_explicit_api_paths(
    value: str, expected: str
) -> None:
    assert _normalize_base_url(value) == expected


@pytest.mark.parametrize(
    'value',
    [
        '',
        'printer.test/api/v1',
        '127.0.0.1:8888',
        'https://printer.test/proxy',
        'https://printer.test/api/v1/extra',
        'https://printer.test/api/v1?debug=1',
        'https://printer.test/api/v1#frag',
        'ftp://printer.test/api/v1',
    ],
)
def test_normalize_base_url_rejects_invalid_or_ambiguous_inputs(value: str) -> None:
    with pytest.raises(ValueError, match='base_url'):
        _normalize_base_url(value)


@pytest.mark.parametrize('client_type', [NoviApiClient, NoviApiAsyncClient])
def test_clients_reject_ambiguous_base_url_subpaths(client_type: type[object]) -> None:
    with pytest.raises(
        ValueError, match="base_url path must be root or end with '/api/v1'"
    ):
        client_type('https://printer.test/proxy')


def test_sync_token_provider_raises_runtime_error_when_valid_token_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = httpx.Client(
        base_url='https://printer.test',
        transport=httpx.MockTransport(_unexpected_request),
    )
    provider = _SyncTokenProvider(client)
    monkeypatch.setattr(provider, '_token_is_valid', lambda: True)

    with pytest.raises(RuntimeError, match='Token cache invariant violated'):
        provider.get_valid_token()

    client.close()


@pytest.mark.anyio
async def test_async_token_provider_raises_runtime_error_when_valid_token_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = httpx.AsyncClient(
        base_url='https://printer.test',
        transport=httpx.MockTransport(_unexpected_request),
    )
    provider = _AsyncTokenProvider(client)
    monkeypatch.setattr(provider, '_token_is_valid', lambda: True)

    with pytest.raises(RuntimeError, match='Token cache invariant violated'):
        await provider.get_valid_token()

    await client.aclose()
