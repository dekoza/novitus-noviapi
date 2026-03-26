# novitus-noviapi

[![PyPI version](https://img.shields.io/pypi/v/novitus-noviapi.svg)](https://pypi.org/project/novitus-noviapi/) [![CI](https://github.com/dekoza/novitus-noviapi/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/dekoza/novitus-noviapi/actions/workflows/ci.yml) [![Python versions](https://img.shields.io/pypi/pyversions/novitus-noviapi.svg)](https://pypi.org/project/novitus-noviapi/) [![License](https://img.shields.io/pypi/l/novitus-noviapi.svg)](https://pypi.org/project/novitus-noviapi/) [![PEP 561](https://img.shields.io/badge/PEP%20561-typed-blue.svg)](https://peps.python.org/pep-0561/)

Python client library for the Novitus NoviAPI fiscal printer REST API.

`novitus-noviapi` is the package name on PyPI. Import it as `noviapi`.

## Features

- Sync and async clients with explicit endpoint methods
- Strict Pydantic request and response models
- Token lifecycle handling with retry on expired tokens
- Async client built on `httpx` and `anyio`
- Offline contract tests against a frozen NoviAPI OpenAPI snapshot

## Installation

```bash
uv add novitus-noviapi
```

Pass an `http://` or `https://` base URL that points either at the printer root
or directly at a path ending with `/api/v1`. The client normalizes root URLs to
`/api/v1`, strips a trailing slash from `/api/v1/`, and rejects ambiguous subpaths.

```python
from noviapi import NoviApiClient

with NoviApiClient('http://127.0.0.1:8888') as client:
    client.comm_test()
```

## Quick start

```python
from decimal import Decimal

from noviapi import NoviApiClient
from noviapi.models import Article, Item, Receipt, Summary

client = NoviApiClient('http://127.0.0.1:8888/api/v1')

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
from noviapi.exceptions import NoviApiTransportError


async def main() -> None:
    async with NoviApiAsyncClient('http://127.0.0.1:8888/api/v1') as client:
        try:
            if not await client.comm_test():
                raise RuntimeError('Printer returned an unexpected non-200 response')
        except NoviApiTransportError:
            raise RuntimeError('Printer is not reachable') from None
```

## Authentication

- Most endpoint methods fetch and refresh tokens automatically.
- `comm_test()` is the exception: it is intentionally auth-free.
- `comm_test()` returns `True` for `200 OK`, returns `False` for unusual non-error
  responses such as redirects, and raises on transport errors or HTTP responses
  `>= 400`.
- Use `token_get()` when you need to inspect or bootstrap a token explicitly.
- Use `token_refresh()` when you need to force a refresh cycle yourself.

```python
from noviapi import NoviApiClient

with NoviApiClient('http://127.0.0.1:8888/api/v1') as client:
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

with NoviApiClient('http://127.0.0.1:8888/api/v1') as client:
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
device. The default hardware suite only covers `comm_test()` and `queue_check()`
so it does not print fiscal documents by accident.

Optional stateful coverage includes a read-only
`status_send()` / `status_confirm()` / `status_check()` device-status flow and a
non-fiscal document test in `tests/hardware/test_nf_printout.py` that prints
`Greetings from the test suite!`. Those tests require the extra
`--run-hardware-stateful` flag.

The non-fiscal document test still consumes paper, so run it only when that
output is acceptable.

These hardware checks are manual and are not part of GitHub Actions. CI only
covers contract, unit, integration, and packaging validation.

Long-poll `timeout` parameters are forwarded in milliseconds, matching the
NoviAPI contract.

The current supported printer matrix below reflects the minimum firmware
versions declared by the printer manufacturer for NoviAPI support:

- `POINT` firmware `1.00`
- `HD II Online` firmware `3.50`
- `Deon Online` firmware `310`
- `Bono Online` firmware `300`
- `INFIS` firmware `1.30`

This library has been personally verified on `POINT` firmware `1.00`. Treat the
other entries as manufacturer-declared minimum supported versions until they are
individually exercised by this project's hardware validation.

Set the printer base URL and enable the hardware test marker explicitly:

```bash
export NOVIAPI_BASE_URL="http://192.168.1.50:8888/api/v1"
uv run pytest tests/hardware --run-hardware -m hardware
```

If `--run-hardware` is omitted, hardware tests are skipped. If
`NOVIAPI_BASE_URL` is missing, pytest fails fast with a usage error. Stateful
hardware tests also require `--run-hardware-stateful`.

See `docs/hardware-testing.md` for the full checklist, requirements, safety
notes, and recommended execution procedure.

See `RC_CHECKLIST.md` for the current release-candidate gate.

## Status

This library started as one part of a larger project and was later extracted
into a standalone open-source package. It currently ships strict models,
explicit endpoint coverage, contract tests, lean release artifacts, artifact
install smoke checks, and a small hardware test suite. Hardware support remains
intentionally narrow and manual hardware validation still sits outside GitHub
Actions; the supported printer matrix lives in `docs/hardware-testing.md`.

The extraction and open-source work was sponsored by
[Diablaq](https://diablaq.com/), and Novitus provided a development kit for
the project. Thank you!
