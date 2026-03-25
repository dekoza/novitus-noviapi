# novitus-noviapi

Python client library for the Novitus NoviAPI fiscal printer REST API.

`novitus-noviapi` is the package name on PyPI. Import it as `noviapi`.

## Features

- Sync and async clients with explicit endpoint methods
- Strict Pydantic request and response models
- Token lifecycle handling with retry on expired tokens
- Backend-neutral async support for asyncio, uvloop, and trio-based apps
- Offline contract tests against a frozen NoviAPI OpenAPI snapshot

## Installation

```bash
uv add novitus-noviapi
```

## Quick start

```python
from decimal import Decimal

from noviapi import NoviApiClient
from noviapi.models import Article, Item, Receipt, Summary

client = NoviApiClient('http://127.0.0.1:8888/api/v1/')

receipt = Receipt(
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

created = client.receipt_send(receipt)
client.receipt_confirm(created.request.id)
```

## Async quick start

```python
from noviapi import NoviApiAsyncClient


async def main() -> None:
    async with NoviApiAsyncClient('http://127.0.0.1:8888/api/v1/') as client:
        is_reachable = await client.comm_test()
        if not is_reachable:
            raise RuntimeError('Printer is not reachable')
```

## Authentication

- Most endpoint methods fetch and refresh tokens automatically.
- `comm_test()` is the exception: it is intentionally auth-free.
- Use `token_get()` when you need to inspect or bootstrap a token explicitly.
- Use `token_refresh()` when you need to force a refresh cycle yourself.

```python
from noviapi import NoviApiClient

with NoviApiClient('http://127.0.0.1:8888/api/v1/') as client:
    token = client.token_get()
    client.token_refresh(token.token)
```

## Error handling

Transport problems and API errors are separated.

```python
from noviapi import NoviApiClient
from noviapi.exceptions import (
    AuthenticationError,
    NoviApiTransportError,
    TooManyTokenRequestsError,
)

with NoviApiClient('http://127.0.0.1:8888/api/v1/') as client:
    try:
        queue = client.queue_check()
    except TooManyTokenRequestsError as exc:
        allowed_refresh_date = (
            exc.detail.exception.allowed_refresh_date
            if exc.detail is not None
            else None
        )
        print(allowed_refresh_date)
    except AuthenticationError:
        print('Token rejected by printer')
    except NoviApiTransportError:
        print('Network error or invalid JSON response')
    else:
        print(queue.requests_in_queue)
```

## Hardware testing

Hardware tests are opt-in and intended only for development against a real
device. The default hardware smoke test only checks `comm_test()` so the suite
does not print fiscal documents by accident.

The current hardware suite also covers `queue_check()` and a read-only
`status_send()` / `status_confirm()` / `status_check()` device-status flow.
That status flow is treated as stateful and requires an extra explicit flag.

Set the printer base URL and enable the hardware test marker explicitly:

```bash
export NOVIAPI_BASE_URL="http://192.168.1.50:8888/api/v1/"
uv run pytest tests/hardware --run-hardware -m hardware
```

If `--run-hardware` is omitted, hardware tests are skipped. If
`NOVIAPI_BASE_URL` is missing, pytest fails fast with a usage error. Stateful
hardware tests also require `--run-hardware-stateful`.

See `docs/hardware-testing.md` for the full checklist, requirements, safety
notes, and recommended execution procedure.

## Status

The project currently ships a rebuilt standalone core package with strict
models, explicit endpoint coverage, contract tests, and lean release artifacts.
Hardware acceptance tests and additional release automation are still planned.

Thank you to Novitus for lending a development kit for this work.
