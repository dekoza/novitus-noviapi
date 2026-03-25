from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal

import httpx
import pytest

from noviapi import NoviApiClient
from noviapi.exceptions import (
    MultipleAccessError,
    NoviApiTransportError,
    TooManyTokenRequestsError,
)
from noviapi.models import (
    Article,
    Base64Payload,
    ConfigurationCommand,
    ConfigurationOption,
    DirectIOCommand,
    EFTCommand,
    GraphicCommand,
    Item,
    LockCommand,
    NonFiscal,
    PrintLine,
    Receipt,
    StatusCommand,
    Summary,
    TextLine,
)


def _receipt() -> Receipt:
    return Receipt(
        items=[
            Item(
                article=Article(
                    name='Coffee',
                    ptu='A',
                    quantity=Decimal('1'),
                    price=Decimal('10.00'),
                    value=Decimal('10.00'),
                )
            )
        ],
        summary=Summary(total=Decimal('10.00'), pay_in=Decimal('10.00')),
    )


def _token_payload(value: str) -> dict:
    return {
        'token': value,
        'expiration_date': datetime(2099, 1, 1, tzinfo=UTC)
        .isoformat()
        .replace('+00:00', 'Z'),
    }


def test_sync_client_retries_once_after_401() -> None:
    request_id = '6' * 32
    seen_tokens: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == '/api/v1/token' and request.method == 'GET':
            return httpx.Response(200, json=_token_payload('token-1'), request=request)
        if request.url.path == '/api/v1/token' and request.method == 'PATCH':
            assert request.content == b''
            assert request.headers['Content-Type'] == 'text/plain'
            return httpx.Response(200, json=_token_payload('token-2'), request=request)
        if request.url.path == '/api/v1/receipt' and request.method == 'POST':
            seen_tokens.append(request.headers.get('Authorization'))
            if len(seen_tokens) == 1:
                return httpx.Response(
                    401,
                    json={
                        'exception': {
                            'code': 1,
                            'description': 'Token expired',
                        }
                    },
                    request=request,
                )
            return httpx.Response(
                201,
                json={'request': {'status': 'STORED', 'id': request_id}},
                request=request,
            )
        raise AssertionError(f'Unexpected request {request.method} {request.url!s}')

    transport = httpx.MockTransport(handler)
    with NoviApiClient('https://printer.test/api/v1/', transport=transport) as client:
        response = client.receipt_send(_receipt())

    assert response.request.id == request_id
    assert seen_tokens == ['Bearer token-1', 'Bearer token-2']


def test_sync_client_maps_too_many_token_requests() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            429,
            json={
                'exception': {
                    'code': 429,
                    'description': 'Too many token requests',
                    'allowed_refresh_date': '2026-03-25T12:00:00Z',
                }
            },
            request=request,
        )

    transport = httpx.MockTransport(handler)
    with (
        NoviApiClient('https://printer.test/api/v1/', transport=transport) as client,
        pytest.raises(TooManyTokenRequestsError),
    ):
        client.token_get()


def test_sync_client_comm_test_does_not_trigger_token_fetch() -> None:
    token_calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal token_calls
        if request.url.path == '/api/v1' and request.method == 'GET':
            assert 'Authorization' not in request.headers
            return httpx.Response(200, request=request)
        if request.url.path == '/api/v1/token':
            token_calls += 1
            return httpx.Response(200, json=_token_payload('token-1'), request=request)
        if request.url.path == '/api/v1/queue' and request.method == 'GET':
            return httpx.Response(200, json={'requests_in_queue': 0}, request=request)
        raise AssertionError(f'Unexpected request {request.method} {request.url!s}')

    transport = httpx.MockTransport(handler)
    with NoviApiClient('https://printer.test/api/v1/', transport=transport) as client:
        assert client.comm_test() is True
        client.queue_check()

    assert token_calls == 1


def test_sync_client_comm_test_returns_false_for_redirect() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == '/api/v1' and request.method == 'GET':
            return httpx.Response(
                307,
                headers={'Location': 'https://printer.test/elsewhere'},
                request=request,
            )
        raise AssertionError(f'Unexpected request {request.method} {request.url!s}')

    transport = httpx.MockTransport(handler)
    with NoviApiClient('https://printer.test/api/v1/', transport=transport) as client:
        assert client.comm_test() is False


@pytest.mark.parametrize('base_url', ['https://printer.test', 'https://printer.test/'])
def test_sync_client_normalizes_root_base_url_for_comm_test_and_queue(
    base_url: str,
) -> None:
    seen_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_paths.append(request.url.path)
        if request.url.path == '/api/v1' and request.method == 'GET':
            return httpx.Response(200, request=request)
        if request.url.path == '/api/v1/token' and request.method == 'GET':
            return httpx.Response(200, json=_token_payload('token-1'), request=request)
        if request.url.path == '/api/v1/queue' and request.method == 'GET':
            return httpx.Response(200, json={'requests_in_queue': 3}, request=request)
        raise AssertionError(f'Unexpected request {request.method} {request.url!s}')

    transport = httpx.MockTransport(handler)
    with NoviApiClient(base_url, transport=transport) as client:
        assert client.comm_test() is True
        queue_status = client.queue_check()

    assert queue_status.requests_in_queue == 3
    assert seen_paths == ['/api/v1', '/api/v1/token', '/api/v1/queue']


def test_sync_client_supports_non_fiscal_printout_flow() -> None:
    request_id = 'f' * 32

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == '/api/v1/token' and request.method == 'GET':
            return httpx.Response(200, json=_token_payload('token-1'), request=request)
        if request.url.path == '/api/v1/nf_printout' and request.method == 'POST':
            payload = json.loads(request.content)
            assert set(payload) == {'printout'}
            assert payload['printout']['lines'][0]['textline']['text'] == (
                'Greetings from the test suite!'
            )
            assert payload['printout']['lines'][0]['textline']['masked'] is False
            return httpx.Response(
                201,
                json={'request': {'status': 'STORED', 'id': request_id}},
                request=request,
            )
        if (
            request.url.path == f'/api/v1/nf_printout/{request_id}'
            and request.method == 'PUT'
        ):
            return httpx.Response(
                200,
                json={'request': {'status': 'CONFIRMED', 'id': request_id}},
                request=request,
            )
        if (
            request.url.path == f'/api/v1/nf_printout/{request_id}'
            and request.method == 'GET'
        ):
            assert request.url.params['timeout'] == '30000'
            return httpx.Response(
                200,
                json={
                    'device': {'status': 'OK'},
                    'request': {'status': 'DONE'},
                },
                request=request,
            )
        raise AssertionError(f'Unexpected request {request.method} {request.url!s}')

    transport = httpx.MockTransport(handler)
    with NoviApiClient('https://printer.test/api/v1/', transport=transport) as client:
        created = client.nf_printout_send(
            NonFiscal(
                lines=[
                    PrintLine(
                        textline=TextLine(
                            text='Greetings from the test suite!',
                            masked=False,
                        )
                    )
                ]
            )
        )
        confirmed = client.nf_printout_confirm(created.request.id)
        checked = client.nf_printout_check(created.request.id, timeout=30_000)

    assert created.request.status == 'STORED'
    assert created.request.id == request_id
    assert confirmed.request.status == 'CONFIRMED'
    assert confirmed.request.id == request_id
    assert checked.request.id is None
    assert checked.request.status == 'DONE'
    assert checked.request.error is None
    assert checked.device.status == 'OK'


def test_sync_client_rejects_receipt_check_payload_from_other_endpoint() -> None:
    request_id = 'b' * 32

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == '/api/v1/token':
            return httpx.Response(200, json=_token_payload('token-1'), request=request)
        if request.url.path == f'/api/v1/receipt/{request_id}':
            return httpx.Response(
                200,
                json={
                    'device': {'status': 'OK'},
                    'request': {
                        'status': 'DONE',
                        'id': request_id,
                        'response': {
                            'packet': {
                                'protocol': 'NOVITUS',
                                'value': 'AA==',
                            }
                        },
                    },
                },
                request=request,
            )
        raise AssertionError(f'Unexpected request {request.method} {request.url!s}')

    transport = httpx.MockTransport(handler)
    with (
        NoviApiClient('https://printer.test/api/v1/', transport=transport) as client,
        pytest.raises(NoviApiTransportError),
    ):
        client.receipt_check(request_id)


def test_sync_client_extends_read_timeout_for_check_requests() -> None:
    request_id = 'c' * 32
    seen_timeout: dict[str, float | None] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == '/api/v1/token':
            return httpx.Response(200, json=_token_payload('token-1'), request=request)
        if request.url.path == f'/api/v1/receipt/{request_id}':
            assert request.url.params['timeout'] == '30000'
            seen_timeout.update(request.extensions['timeout'])
            return httpx.Response(
                200,
                json={
                    'device': {'status': 'OK'},
                    'request': {'status': 'DONE', 'id': request_id},
                },
                request=request,
            )
        raise AssertionError(f'Unexpected request {request.method} {request.url!s}')

    transport = httpx.MockTransport(handler)
    with NoviApiClient(
        'https://printer.test/api/v1/', timeout=5.0, transport=transport
    ) as client:
        response = client.receipt_check(request_id, timeout=30_000)

    assert response.request.status == 'DONE'
    assert seen_timeout == {
        'connect': 5.0,
        'read': 35.0,
        'write': 5.0,
        'pool': 5.0,
    }


def test_sync_client_maps_multiple_access_denied_on_confirm() -> None:
    request_id = 'd' * 32

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == '/api/v1/token':
            return httpx.Response(200, json=_token_payload('token-1'), request=request)
        if request.url.path == f'/api/v1/receipt/{request_id}':
            return httpx.Response(
                403,
                json={
                    'exception': {
                        'code': 403,
                        'description': (
                            'Multiple access denied. Token has been '
                            'deleted, download a new one.'
                        ),
                    }
                },
                request=request,
            )
        raise AssertionError(f'Unexpected request {request.method} {request.url!s}')

    transport = httpx.MockTransport(handler)
    with (
        NoviApiClient('https://printer.test/api/v1/', transport=transport) as client,
        pytest.raises(MultipleAccessError) as exc_info,
    ):
        client.receipt_confirm(request_id)

    assert exc_info.value.status_code == 403


def test_sync_client_maps_generic_403_to_multiple_access_error() -> None:
    request_id = 'e' * 32

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == '/api/v1/token':
            return httpx.Response(200, json=_token_payload('token-1'), request=request)
        if request.url.path == f'/api/v1/receipt/{request_id}':
            return httpx.Response(
                403,
                json={
                    'exception': {
                        'code': 403,
                        'description': 'Multiple access denied by policy.',
                    }
                },
                request=request,
            )
        raise AssertionError(f'Unexpected request {request.method} {request.url!s}')

    transport = httpx.MockTransport(handler)
    with (
        NoviApiClient('https://printer.test/api/v1/', transport=transport) as client,
        pytest.raises(MultipleAccessError) as exc_info,
    ):
        client.receipt_confirm(request_id)

    assert exc_info.value.status_code == 403


@pytest.mark.parametrize(
    ('method_name', 'model_factory', 'path'),
    [
        ('receipt_send', _receipt, '/api/v1/receipt'),
        (
            'nf_printout_send',
            lambda: NonFiscal(
                lines=[PrintLine(textline=TextLine(text='Hello', masked=False))]
            ),
            '/api/v1/nf_printout',
        ),
        (
            'daily_report_send',
            lambda: {'date': '25-03-2026'},
            '/api/v1/daily_report',
        ),
        (
            'eft_send',
            lambda: EFTCommand(operation='communication_test'),
            '/api/v1/eft',
        ),
        (
            'graphic_send',
            lambda: GraphicCommand(operation='read_indexes'),
            '/api/v1/graphic',
        ),
        (
            'configuration_send',
            lambda: ConfigurationCommand(
                operation='program',
                options=[ConfigurationOption(key=1, value='x')],
            ),
            '/api/v1/configuration',
        ),
        (
            'status_send',
            lambda: StatusCommand(type='device'),
            '/api/v1/status',
        ),
        (
            'direct_io_send',
            lambda: DirectIOCommand(nov_cmd=Base64Payload(base64='AA==')),
            '/api/v1/direct_io',
        ),
        (
            'lock_send',
            lambda: LockCommand(operation='disable'),
            '/api/v1/lock',
        ),
    ],
)
def test_sync_client_covers_send_endpoints(
    method_name: str,
    model_factory: Callable[[], object],
    path: str,
) -> None:
    request_id = '7' * 32

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == '/api/v1/token':
            return httpx.Response(200, json=_token_payload('token-1'), request=request)
        assert request.url.path == path
        return httpx.Response(
            201,
            json={'request': {'status': 'STORED', 'id': request_id}},
            request=request,
        )

    transport = httpx.MockTransport(handler)
    with NoviApiClient('https://printer.test/api/v1/', transport=transport) as client:
        response = getattr(client, method_name)(model_factory())

    assert response.request.id == request_id
