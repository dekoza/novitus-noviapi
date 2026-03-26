from __future__ import annotations

import anyio
import httpx

from noviapi import NoviApiAsyncClient, NoviApiClient


def _handler(request: httpx.Request) -> httpx.Response:
    if request.method == 'GET' and request.url.path == '/api/v1':
        return httpx.Response(200, request=request)
    raise AssertionError(f'Unexpected request {request.method} {request.url!s}')


def main() -> None:
    base_url = 'http://127.0.0.1:8888'
    transport = httpx.MockTransport(_handler)

    with NoviApiClient(base_url, transport=transport) as client:
        if client.comm_test() is not True:
            raise RuntimeError('sync comm_test smoke check failed')

    async def run_async() -> None:
        async with NoviApiAsyncClient(base_url, transport=transport) as client:
            if await client.comm_test() is not True:
                raise RuntimeError('async comm_test smoke check failed')

    anyio.run(run_async)


if __name__ == '__main__':
    main()
