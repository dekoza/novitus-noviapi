from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal

import anyio
import httpx
import pytest

from noviapi import NoviApiAsyncClient
from noviapi.exceptions import (
    AuthenticationError,
    ConflictError,
    NoviApiTransportError,
    TooManyTokenRequestsError,
)
from noviapi.models import (
    Article,
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

pytestmark = pytest.mark.anyio


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


def _stored_response(request_id: str) -> dict:
    return {'request': {'status': 'STORED', 'id': request_id}}


def _confirmed_response(request_id: str) -> dict:
    return {'request': {'status': 'CONFIRMED', 'id': request_id}}


def _deleted_response() -> dict:
    return {'request': {'status': 'DELETED'}}


def _token_payload(value: str) -> dict:
    return {
        'token': value,
        'expiration_date': datetime(2099, 1, 1, tzinfo=UTC)
        .isoformat()
        .replace('+00:00', 'Z'),
    }


async def test_async_client_retries_once_after_401() -> None:
    request_id = '1' * 32
    seen_tokens: list[str | None] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == '/api/v1/token' and request.method == 'GET':
            return httpx.Response(
                200, json=_token_payload('token-1'), request=request
            )
        if request.url.path == '/api/v1/token' and request.method == 'PATCH':
            assert request.content == b''
            assert request.headers['Content-Type'] == 'text/plain'
            return httpx.Response(
                200, json=_token_payload('token-2'), request=request
            )
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
            payload = json.loads(request.content)
            assert payload['receipt']['summary']['total'] == '10.00'
            return httpx.Response(
                201, json=_stored_response(request_id), request=request
            )
        raise AssertionError(
            f'Unexpected request {request.method} {request.url!s}'
        )

    transport = httpx.MockTransport(handler)
    async with NoviApiAsyncClient(
        'https://printer.test/api/v1/', transport=transport
    ) as client:
        response = await client.receipt_send(_receipt())

    assert response.request.status == 'STORED'
    assert response.request.id == request_id
    assert seen_tokens == ['Bearer token-1', 'Bearer token-2']


async def test_async_client_supports_timeout_query_for_check() -> None:
    request_id = '2' * 32

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == '/api/v1/token':
            return httpx.Response(
                200, json=_token_payload('token-1'), request=request
            )
        if request.url.path == f'/api/v1/receipt/{request_id}':
            assert request.url.params['timeout'] == '30'
            return httpx.Response(
                200,
                json={
                    'device': {'status': 'OK'},
                    'request': {'status': 'DONE', 'id': request_id},
                },
                request=request,
            )
        raise AssertionError(
            f'Unexpected request {request.method} {request.url!s}'
        )

    transport = httpx.MockTransport(handler)
    async with NoviApiAsyncClient(
        'https://printer.test/api/v1/', transport=transport
    ) as client:
        response = await client.receipt_check(request_id, timeout=30)

    assert response.request.status == 'DONE'


async def test_async_client_maps_too_many_token_requests() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
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
    async with NoviApiAsyncClient(
        'https://printer.test/api/v1/', transport=transport
    ) as client:
        with pytest.raises(TooManyTokenRequestsError) as exc_info:
            await client.token_get()

    assert exc_info.value.status_code == 429
    assert exc_info.value.detail is not None
    assert exc_info.value.detail.exception.allowed_refresh_date == datetime(
        2026,
        3,
        25,
        12,
        0,
        tzinfo=UTC,
    )


async def test_async_client_maps_multiple_access_denied_on_confirm() -> None:
    request_id = '3' * 32

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == '/api/v1/token':
            return httpx.Response(
                200, json=_token_payload('token-1'), request=request
            )
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
        raise AssertionError(
            f'Unexpected request {request.method} {request.url!s}'
        )

    transport = httpx.MockTransport(handler)
    async with NoviApiAsyncClient(
        'https://printer.test/api/v1/', transport=transport
    ) as client:
        with pytest.raises(AuthenticationError) as exc_info:
            await client.receipt_confirm(request_id)

    assert exc_info.value.status_code == 403


async def test_async_client_maps_daily_report_conflict() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == '/api/v1/token':
            return httpx.Response(
                200, json=_token_payload('token-1'), request=request
            )
        if request.url.path == '/api/v1/receipt':
            return httpx.Response(
                409,
                json={
                    'exception': {
                        'code': 409,
                        'description': 'Waiting for execute daily report',
                    },
                    'daily_report_id': '4' * 32,
                },
                request=request,
            )
        raise AssertionError(
            f'Unexpected request {request.method} {request.url!s}'
        )

    transport = httpx.MockTransport(handler)
    async with NoviApiAsyncClient(
        'https://printer.test/api/v1/', transport=transport
    ) as client:
        with pytest.raises(ConflictError) as exc_info:
            await client.receipt_send(_receipt())

    assert exc_info.value.detail is not None
    assert exc_info.value.detail.daily_report_id == '4' * 32


@pytest.mark.parametrize(
    ('method_name', 'model_factory', 'path'),
    [
        ('receipt_send', _receipt, '/api/v1/receipt'),
        (
            'invoice_send',
            lambda: {
                'info': {'number': 'FV/1/2026'},
                'buyer': {
                    'name': 'Acme',
                    'id': '1234567890',
                    'address': ['Main Street 1'],
                },
                'items': [
                    {
                        'article': _receipt()
                        .items[0]
                        .article.model_dump(mode='json')
                    }
                ],
                'summary': {'total': '10.00', 'pay_in': '10.00'},
            },
            '/api/v1/invoice',
        ),
        (
            'nf_printout_send',
            lambda: NonFiscal(
                lines=[
                    PrintLine(textline=TextLine(text='Hello', masked=False))
                ]
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
            lambda: DirectIOCommand(nov_cmd={'base64': 'AA=='}),
            '/api/v1/direct_io',
        ),
        (
            'lock_send',
            lambda: LockCommand(operation='disable'),
            '/api/v1/lock',
        ),
    ],
)
async def test_async_client_covers_all_send_endpoints(
    method_name: str,
    model_factory: Callable[[], object],
    path: str,
) -> None:
    request_id = '5' * 32

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == '/api/v1/token':
            return httpx.Response(
                200, json=_token_payload('token-1'), request=request
            )
        assert request.url.path == path
        assert request.method == 'POST'
        return httpx.Response(
            201, json=_stored_response(request_id), request=request
        )

    transport = httpx.MockTransport(handler)
    async with NoviApiAsyncClient(
        'https://printer.test/api/v1/', transport=transport
    ) as client:
        model = model_factory()
        if isinstance(model, dict):
            response = await getattr(client, method_name)(model)
        else:
            response = await getattr(client, method_name)(model)

    assert response.request.id == request_id


async def test_async_client_supports_queue_and_comm_test() -> None:
    token_calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        if (
            request.url.path in {'/api/v1', '/api/v1/'}
            and request.method == 'GET'
        ):
            assert 'Authorization' not in request.headers
            return httpx.Response(200, request=request)
        if request.url.path == '/api/v1/token':
            nonlocal token_calls
            token_calls += 1
            return httpx.Response(
                200, json=_token_payload('token-1'), request=request
            )
        if request.url.path == '/api/v1/queue' and request.method == 'GET':
            return httpx.Response(
                200, json={'requests_in_queue': 7}, request=request
            )
        if request.url.path == '/api/v1/queue' and request.method == 'DELETE':
            return httpx.Response(
                200, json={'status': 'DELETED'}, request=request
            )
        raise AssertionError(
            f'Unexpected request {request.method} {request.url!s}'
        )

    transport = httpx.MockTransport(handler)
    async with NoviApiAsyncClient(
        'https://printer.test/api/v1/', transport=transport
    ) as client:
        assert await client.comm_test() is True
        queue_status = await client.queue_check()
        queue_delete = await client.queue_clear()

    assert queue_status.requests_in_queue == 7
    assert queue_delete.status == 'DELETED'
    assert token_calls == 1


async def test_async_client_fetches_single_token_for_concurrent_requests() -> (
    None
):
    request_ids = ['8' * 32, '9' * 32]
    token_calls = 0
    request_calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal token_calls, request_calls
        if request.url.path == '/api/v1/token':
            token_calls += 1
            await anyio.sleep(0)
            return httpx.Response(
                200, json=_token_payload('token-1'), request=request
            )
        if request.url.path == '/api/v1/receipt':
            request_calls += 1
            return httpx.Response(
                201,
                json=_stored_response(request_ids[request_calls - 1]),
                request=request,
            )
        raise AssertionError(
            f'Unexpected request {request.method} {request.url!s}'
        )

    transport = httpx.MockTransport(handler)
    async with NoviApiAsyncClient(
        'https://printer.test/api/v1/', transport=transport
    ) as client:
        results: list[str] = []

        async def send_receipt() -> None:
            response = await client.receipt_send(_receipt())
            assert response.request.id is not None
            results.append(response.request.id)

        async with anyio.create_task_group() as task_group:
            task_group.start_soon(send_receipt)
            task_group.start_soon(send_receipt)

    assert token_calls == 1
    assert request_calls == 2
    assert set(results) == set(request_ids)


async def test_async_client_rejects_receipt_check_payload_from_other_endpoint() -> (
    None
):
    request_id = 'a' * 32

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == '/api/v1/token':
            return httpx.Response(
                200, json=_token_payload('token-1'), request=request
            )
        if request.url.path == f'/api/v1/receipt/{request_id}':
            return httpx.Response(
                200,
                json={
                    'device': {'status': 'OK'},
                    'request': {
                        'status': 'DONE',
                        'id': request_id,
                        'response': {
                            'eft': {
                                'agent': 'AG',
                                'amount': '10.00',
                                'card_token': 'token',
                                'cashback': '0.00',
                                'code': 0,
                                'eft_id': 'eft-1',
                                'error_code': 0,
                                'message': 'OK',
                                'transaction_id': 'trx-1',
                            }
                        },
                    },
                },
                request=request,
            )
        raise AssertionError(
            f'Unexpected request {request.method} {request.url!s}'
        )

    transport = httpx.MockTransport(handler)
    async with NoviApiAsyncClient(
        'https://printer.test/api/v1/', transport=transport
    ) as client:
        with pytest.raises(NoviApiTransportError):
            await client.receipt_check(request_id)
