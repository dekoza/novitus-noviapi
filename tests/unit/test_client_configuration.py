from __future__ import annotations

import httpx
import pytest

from noviapi import NoviApiAsyncClient, NoviApiClient
from noviapi.client import (
    CHECK_TIMEOUT_MARGIN_SECONDS,
    _AsyncTokenProvider,
    _normalize_base_url,
    _request_timeout_for_check,
    _SyncTokenProvider,
)


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


def test_request_timeout_for_check_returns_none_when_poll_timeout_is_missing() -> None:
    base_timeout = httpx.Timeout(5.0)

    assert _request_timeout_for_check(base_timeout, None) is None


def test_request_timeout_for_check_returns_none_when_read_timeout_is_unbounded() -> (
    None
):
    base_timeout = httpx.Timeout(connect=5.0, read=None, write=5.0, pool=5.0)

    assert _request_timeout_for_check(base_timeout, 30_000) is None


def test_request_timeout_for_check_returns_none_when_read_timeout_is_long_enough() -> (
    None
):
    poll_timeout_ms = 30_000
    poll_timeout_seconds = (poll_timeout_ms / 1000) + CHECK_TIMEOUT_MARGIN_SECONDS
    base_timeout = httpx.Timeout(
        connect=5.0,
        read=poll_timeout_seconds,
        write=5.0,
        pool=5.0,
    )

    assert _request_timeout_for_check(base_timeout, poll_timeout_ms) is None


def test_request_timeout_for_check_extends_only_the_read_timeout() -> None:
    base_timeout = httpx.Timeout(connect=1.0, read=5.0, write=2.0, pool=3.0)

    timeout = _request_timeout_for_check(base_timeout, 30_000)

    assert timeout == httpx.Timeout(connect=1.0, read=35.0, write=2.0, pool=3.0)
