from __future__ import annotations

import threading
from datetime import UTC, datetime
from typing import Any, TypeVar
from urllib.parse import urlsplit, urlunsplit

import anyio
import httpx
from pydantic import ValidationError as PydanticValidationError

from noviapi.exceptions import (
    AuthenticationError,
    ConflictError,
    InternalServerError,
    MultipleAccessError,
    NotFoundError,
    NoviApiResponseError,
    NoviApiTransportError,
    ProtectedMemoryFullError,
    TooManyTokenRequestsError,
    ValidationErrorResponse,
)
from noviapi.models import (
    CheckResponse,
    ConfigurationCommand,
    ConfirmedResponse,
    CreatedResponse,
    DailyReport,
    DeleteResponse,
    DirectIOCommand,
    EFTCommand,
    ErrorEnvelope,
    GraphicCommand,
    Invoice,
    LockCommand,
    NonFiscal,
    QueueDeleteResponse,
    QueueStatusResponse,
    Receipt,
    ResponsePayload,
    StatusCommand,
    TokenResponse,
)

SendModel = TypeVar(
    'SendModel',
    Receipt,
    Invoice,
    NonFiscal,
    DailyReport,
    EFTCommand,
    GraphicCommand,
    ConfigurationCommand,
    StatusCommand,
    DirectIOCommand,
    LockCommand,
)

CHECK_TIMEOUT_MARGIN_SECONDS = 5.0
TOKEN_CACHE_INVARIANT_MESSAGE = (
    'Token cache invariant violated: token marked valid but missing'
)


def _normalize_base_url(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError('base_url must not be empty')

    parsed = urlsplit(stripped)
    if parsed.scheme not in {'http', 'https'}:
        raise ValueError('base_url must use http or https')
    if not parsed.netloc:
        raise ValueError('base_url must include a host')
    if parsed.query or parsed.fragment:
        raise ValueError('base_url must not include a query string or fragment')

    normalized_path = parsed.path.rstrip('/')
    if normalized_path in {'', '/'}:
        normalized_path = '/api/v1'
    elif normalized_path.endswith('/api/v1'):
        normalized_path = normalized_path
    else:
        raise ValueError("base_url path must be root or end with '/api/v1'")

    return urlunsplit((parsed.scheme, parsed.netloc, normalized_path, '', ''))


def _timeout_to_poll_timeout(timeout: httpx.Timeout | float) -> httpx.Timeout:
    return timeout if isinstance(timeout, httpx.Timeout) else httpx.Timeout(timeout)


def _timeout_component(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, int | float):
        return float(value)
    raise TypeError('httpx.Timeout components must be numeric or None')


def _request_timeout_for_check(
    base_timeout: httpx.Timeout, poll_timeout_ms: int | None
) -> httpx.Timeout | None:
    if poll_timeout_ms is None:
        return None

    poll_timeout_seconds = (poll_timeout_ms / 1000) + CHECK_TIMEOUT_MARGIN_SECONDS
    read_timeout = _timeout_component(base_timeout.read)
    if read_timeout is None or read_timeout >= poll_timeout_seconds:
        return None

    return httpx.Timeout(
        connect=_timeout_component(base_timeout.connect),
        read=poll_timeout_seconds,
        write=_timeout_component(base_timeout.write),
        pool=_timeout_component(base_timeout.pool),
    )


def _ensure_model(
    value: SendModel | dict[str, Any], model_type: type[SendModel]
) -> SendModel:
    if isinstance(value, model_type):
        return value
    return model_type.model_validate(value)


def _parse_json(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError as exc:
        raise NoviApiTransportError('NoviAPI returned a non-JSON response') from exc


def _validate_json_response(response: httpx.Response, model_type: type[Any]) -> Any:
    payload = _parse_json(response)
    try:
        return model_type.model_validate(payload)
    except PydanticValidationError as exc:
        raise NoviApiTransportError(
            f'NoviAPI returned an unexpected payload for {model_type.__name__}'
        ) from exc


def _parse_error_envelope(response: httpx.Response) -> ErrorEnvelope | None:
    try:
        payload = response.json()
    except ValueError:
        return None
    if not isinstance(payload, dict) or 'exception' not in payload:
        return None
    try:
        return ErrorEnvelope.model_validate(payload)
    except PydanticValidationError:
        return None


def _build_response_exception(
    response: httpx.Response,
) -> NoviApiResponseError:
    detail = _parse_error_envelope(response)
    message = (
        detail.exception.description
        if detail is not None and detail.exception.description is not None
        else f'Unexpected NoviAPI response with status {response.status_code}'
    )

    if response.status_code == 400:
        exc_type = ValidationErrorResponse
    elif response.status_code == 401:
        exc_type = AuthenticationError
    elif response.status_code == 403:
        exc_type = MultipleAccessError
    elif response.status_code == 404:
        exc_type = NotFoundError
    elif response.status_code == 409:
        exc_type = ConflictError
    elif response.status_code == 429:
        exc_type = TooManyTokenRequestsError
    elif response.status_code == 500:
        exc_type = InternalServerError
    elif response.status_code == 507:
        exc_type = ProtectedMemoryFullError
    else:
        exc_type = NoviApiResponseError

    return exc_type(message, status_code=response.status_code, detail=detail)


def _response_payload_keys(payload: ResponsePayload | None) -> set[str]:
    if payload is None:
        return set()
    keys = set()
    if payload.status is not None:
        keys.add('status')
    if payload.eft is not None:
        keys.add('eft')
    if payload.graphic is not None:
        keys.add('graphic')
    if payload.configuration is not None:
        keys.add('configuration')
    if payload.packet is not None:
        keys.add('packet')
    return keys


def _validate_check_response(
    response: CheckResponse, *, allowed_response_keys: set[str]
) -> CheckResponse:
    actual_response_keys = _response_payload_keys(response.request.response)
    if not actual_response_keys.issubset(allowed_response_keys):
        raise NoviApiTransportError('Unexpected response payload for this endpoint')
    return response


class _SyncTokenProvider:
    def __init__(self, client: httpx.Client) -> None:
        self._client = client
        self._lock = threading.RLock()
        self._token: TokenResponse | None = None

    def _token_is_valid(self) -> bool:
        return self._token is not None and self._token.expiration_date > datetime.now(
            UTC
        )

    def _request_new_token_unlocked(self) -> TokenResponse:
        response = self._client.get('/token', auth=None)
        if response.status_code >= 400:
            raise _build_response_exception(response)
        token = _validate_json_response(response, TokenResponse)
        self._token = token
        return token

    def request_new_token(self) -> TokenResponse:
        with self._lock:
            return self._request_new_token_unlocked()

    def get_valid_token(self) -> str:
        with self._lock:
            if self._token_is_valid():
                token = self._token
                if token is None:
                    raise RuntimeError(TOKEN_CACHE_INVARIANT_MESSAGE)
                return token.token
            if self._token is None:
                return self._request_new_token_unlocked().token
            return self._refresh_token_unlocked(self._token.token).token

    def _refresh_token_unlocked(self, current_token: str | None) -> TokenResponse:
        if self._token is None:
            return self._request_new_token_unlocked()
        if (
            current_token is not None
            and self._token.token != current_token
            and self._token_is_valid()
        ):
            return self._token
        response = self._client.request(
            'PATCH',
            '/token',
            auth=None,
            headers={
                'Authorization': f'Bearer {self._token.token}',
                'Content-Type': 'text/plain',
            },
            content=b'',
        )
        if response.status_code >= 400:
            raise _build_response_exception(response)
        token = _validate_json_response(response, TokenResponse)
        self._token = token
        return token

    def refresh_token(self, current_token: str | None = None) -> TokenResponse:
        with self._lock:
            return self._refresh_token_unlocked(current_token)

    def clear(self) -> None:
        with self._lock:
            self._token = None


class _AsyncTokenProvider:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client
        self._lock = anyio.Lock()
        self._token: TokenResponse | None = None

    def _token_is_valid(self) -> bool:
        return self._token is not None and self._token.expiration_date > datetime.now(
            UTC
        )

    async def _request_new_token_unlocked(self) -> TokenResponse:
        response = await self._client.get('/token', auth=None)
        if response.status_code >= 400:
            raise _build_response_exception(response)
        token = _validate_json_response(response, TokenResponse)
        self._token = token
        return token

    async def request_new_token(self) -> TokenResponse:
        async with self._lock:
            return await self._request_new_token_unlocked()

    async def get_valid_token(self) -> str:
        async with self._lock:
            if self._token_is_valid():
                token = self._token
                if token is None:
                    raise RuntimeError(TOKEN_CACHE_INVARIANT_MESSAGE)
                return token.token
            if self._token is None:
                return (await self._request_new_token_unlocked()).token
            return (await self._refresh_token_unlocked(self._token.token)).token

    async def _refresh_token_unlocked(self, current_token: str | None) -> TokenResponse:
        if self._token is None:
            return await self._request_new_token_unlocked()
        if (
            current_token is not None
            and self._token.token != current_token
            and self._token_is_valid()
        ):
            return self._token
        response = await self._client.request(
            'PATCH',
            '/token',
            auth=None,
            headers={
                'Authorization': f'Bearer {self._token.token}',
                'Content-Type': 'text/plain',
            },
            content=b'',
        )
        if response.status_code >= 400:
            raise _build_response_exception(response)
        token = _validate_json_response(response, TokenResponse)
        self._token = token
        return token

    async def refresh_token(self, current_token: str | None = None) -> TokenResponse:
        async with self._lock:
            return await self._refresh_token_unlocked(current_token)

    async def clear(self) -> None:
        async with self._lock:
            self._token = None


class _SyncRequestMixin:
    _client: httpx.Client
    _token_provider: _SyncTokenProvider

    @property
    def _client_timeout(self) -> httpx.Timeout:
        return _timeout_to_poll_timeout(self._client.timeout)

    def _send_raw(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        try:
            return self._client.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            raise NoviApiTransportError(str(exc)) from exc

    def _request(
        self,
        method: str,
        path: str,
        *,
        require_auth: bool = True,
        **kwargs: Any,
    ) -> httpx.Response:
        request_kwargs = dict(kwargs)
        headers = httpx.Headers(request_kwargs.pop('headers', None))
        token: str | None = None
        if require_auth:
            token = self._token_provider.get_valid_token()
            headers['Authorization'] = f'Bearer {token}'
        response = self._send_raw(method, path, headers=headers, **request_kwargs)
        if response.status_code == 401 and require_auth and token is not None:
            refreshed_token = self._token_provider.refresh_token(token).token
            retry_headers = httpx.Headers(headers)
            retry_headers['Authorization'] = f'Bearer {refreshed_token}'
            response = self._send_raw(
                method, path, headers=retry_headers, **request_kwargs
            )
        if response.status_code >= 400:
            error = _build_response_exception(response)
            if isinstance(error, AuthenticationError | MultipleAccessError):
                self._token_provider.clear()
            raise error
        return response

    def _send(
        self,
        path: str,
        root_key: str,
        value: SendModel | dict[str, Any],
        model_type: type[SendModel],
    ) -> CreatedResponse:
        payload_model = _ensure_model(value, model_type)
        response = self._request(
            'POST',
            path,
            json={
                root_key: payload_model.model_dump(
                    mode='json', exclude_none=True, by_alias=True
                )
            },
        )
        return _validate_json_response(response, CreatedResponse)

    def _confirm(self, path: str, request_id: str) -> ConfirmedResponse:
        response = self._request('PUT', f'{path}/{request_id}')
        return _validate_json_response(response, ConfirmedResponse)

    def _check(
        self,
        path: str,
        request_id: str,
        *,
        timeout: int | None = None,
        allowed_response_keys: set[str],
    ) -> CheckResponse:
        params = {'timeout': timeout} if timeout is not None else None
        request_timeout = _request_timeout_for_check(self._client_timeout, timeout)
        response = self._request(
            'GET',
            f'{path}/{request_id}',
            params=params,
            timeout=request_timeout,
        )
        parsed = _validate_json_response(response, CheckResponse)
        return _validate_check_response(
            parsed, allowed_response_keys=allowed_response_keys
        )

    def _cancel(self, path: str, request_id: str) -> DeleteResponse:
        response = self._request('DELETE', f'{path}/{request_id}')
        return _validate_json_response(response, DeleteResponse)


class _AsyncRequestMixin:
    _client: httpx.AsyncClient
    _token_provider: _AsyncTokenProvider

    @property
    def _client_timeout(self) -> httpx.Timeout:
        return _timeout_to_poll_timeout(self._client.timeout)

    async def _send_raw(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        try:
            return await self._client.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            raise NoviApiTransportError(str(exc)) from exc

    async def _request(
        self,
        method: str,
        path: str,
        *,
        require_auth: bool = True,
        **kwargs: Any,
    ) -> httpx.Response:
        request_kwargs = dict(kwargs)
        headers = httpx.Headers(request_kwargs.pop('headers', None))
        token: str | None = None
        if require_auth:
            token = await self._token_provider.get_valid_token()
            headers['Authorization'] = f'Bearer {token}'
        response = await self._send_raw(method, path, headers=headers, **request_kwargs)
        if response.status_code == 401 and require_auth and token is not None:
            refreshed_token = (await self._token_provider.refresh_token(token)).token
            retry_headers = httpx.Headers(headers)
            retry_headers['Authorization'] = f'Bearer {refreshed_token}'
            response = await self._send_raw(
                method, path, headers=retry_headers, **request_kwargs
            )
        if response.status_code >= 400:
            error = _build_response_exception(response)
            if isinstance(error, AuthenticationError | MultipleAccessError):
                await self._token_provider.clear()
            raise error
        return response

    async def _send(
        self,
        path: str,
        root_key: str,
        value: SendModel | dict[str, Any],
        model_type: type[SendModel],
    ) -> CreatedResponse:
        payload_model = _ensure_model(value, model_type)
        response = await self._request(
            'POST',
            path,
            json={
                root_key: payload_model.model_dump(
                    mode='json', exclude_none=True, by_alias=True
                )
            },
        )
        return _validate_json_response(response, CreatedResponse)

    async def _confirm(self, path: str, request_id: str) -> ConfirmedResponse:
        response = await self._request('PUT', f'{path}/{request_id}')
        return _validate_json_response(response, ConfirmedResponse)

    async def _check(
        self,
        path: str,
        request_id: str,
        *,
        timeout: int | None = None,
        allowed_response_keys: set[str],
    ) -> CheckResponse:
        params = {'timeout': timeout} if timeout is not None else None
        request_timeout = _request_timeout_for_check(self._client_timeout, timeout)
        response = await self._request(
            'GET',
            f'{path}/{request_id}',
            params=params,
            timeout=request_timeout,
        )
        parsed = _validate_json_response(response, CheckResponse)
        return _validate_check_response(
            parsed, allowed_response_keys=allowed_response_keys
        )

    async def _cancel(self, path: str, request_id: str) -> DeleteResponse:
        response = await self._request('DELETE', f'{path}/{request_id}')
        return _validate_json_response(response, DeleteResponse)


class NoviApiClient(_SyncRequestMixin):
    def __init__(
        self,
        base_url: str,
        *,
        timeout: httpx.Timeout | float = 5.0,
        verify: bool | str = True,
        transport: httpx.BaseTransport | None = None,
        trust_env: bool = False,
    ) -> None:
        normalized_base_url = _normalize_base_url(base_url)
        self._root_url = normalized_base_url
        self._client = httpx.Client(
            base_url=normalized_base_url,
            timeout=timeout,
            verify=verify,
            transport=transport,
            trust_env=trust_env,
            headers={'User-Agent': 'novitus-noviapi'},
        )
        self._token_provider = _SyncTokenProvider(self._client)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> NoviApiClient:
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()

    def comm_test(self) -> bool:
        response = self._request('GET', self._root_url, require_auth=False)
        return response.status_code == 200

    def token_get(self) -> TokenResponse:
        return self._token_provider.request_new_token()

    def token_refresh(self, current_token: str | None = None) -> TokenResponse:
        return self._token_provider.refresh_token(current_token)

    def queue_check(self) -> QueueStatusResponse:
        response = self._request('GET', '/queue')
        return _validate_json_response(response, QueueStatusResponse)

    def queue_clear(self) -> QueueDeleteResponse:
        response = self._request('DELETE', '/queue')
        return _validate_json_response(response, QueueDeleteResponse)

    def receipt_send(self, receipt: Receipt | dict[str, Any]) -> CreatedResponse:
        return self._send('/receipt', 'receipt', receipt, Receipt)

    def receipt_confirm(self, request_id: str) -> ConfirmedResponse:
        return self._confirm('/receipt', request_id)

    def receipt_check(
        self, request_id: str, *, timeout: int | None = None
    ) -> CheckResponse:
        return self._check(
            '/receipt',
            request_id,
            timeout=timeout,
            allowed_response_keys=set(),
        )

    def receipt_cancel(self, request_id: str) -> DeleteResponse:
        return self._cancel('/receipt', request_id)

    def invoice_send(self, invoice: Invoice | dict[str, Any]) -> CreatedResponse:
        return self._send('/invoice', 'invoice', invoice, Invoice)

    def invoice_confirm(self, request_id: str) -> ConfirmedResponse:
        return self._confirm('/invoice', request_id)

    def invoice_check(
        self, request_id: str, *, timeout: int | None = None
    ) -> CheckResponse:
        return self._check(
            '/invoice',
            request_id,
            timeout=timeout,
            allowed_response_keys=set(),
        )

    def invoice_cancel(self, request_id: str) -> DeleteResponse:
        return self._cancel('/invoice', request_id)

    def nf_printout_send(self, printout: NonFiscal | dict[str, Any]) -> CreatedResponse:
        return self._send('/nf_printout', 'printout', printout, NonFiscal)

    def nf_printout_confirm(self, request_id: str) -> ConfirmedResponse:
        return self._confirm('/nf_printout', request_id)

    def nf_printout_check(
        self, request_id: str, *, timeout: int | None = None
    ) -> CheckResponse:
        return self._check(
            '/nf_printout',
            request_id,
            timeout=timeout,
            allowed_response_keys=set(),
        )

    def nf_printout_cancel(self, request_id: str) -> DeleteResponse:
        return self._cancel('/nf_printout', request_id)

    def daily_report_send(
        self, daily_report: DailyReport | dict[str, Any]
    ) -> CreatedResponse:
        return self._send('/daily_report', 'daily_report', daily_report, DailyReport)

    def daily_report_confirm(self, request_id: str) -> ConfirmedResponse:
        return self._confirm('/daily_report', request_id)

    def daily_report_check(
        self, request_id: str, *, timeout: int | None = None
    ) -> CheckResponse:
        return self._check(
            '/daily_report',
            request_id,
            timeout=timeout,
            allowed_response_keys=set(),
        )

    def daily_report_cancel(self, request_id: str) -> DeleteResponse:
        return self._cancel('/daily_report', request_id)

    def eft_send(self, eft: EFTCommand | dict[str, Any]) -> CreatedResponse:
        return self._send('/eft', 'eft', eft, EFTCommand)

    def eft_confirm(self, request_id: str) -> ConfirmedResponse:
        return self._confirm('/eft', request_id)

    def eft_check(
        self, request_id: str, *, timeout: int | None = None
    ) -> CheckResponse:
        return self._check(
            '/eft',
            request_id,
            timeout=timeout,
            allowed_response_keys={'eft'},
        )

    def eft_cancel(self, request_id: str) -> DeleteResponse:
        return self._cancel('/eft', request_id)

    def graphic_send(self, graphic: GraphicCommand | dict[str, Any]) -> CreatedResponse:
        return self._send('/graphic', 'graphic', graphic, GraphicCommand)

    def graphic_confirm(self, request_id: str) -> ConfirmedResponse:
        return self._confirm('/graphic', request_id)

    def graphic_check(
        self, request_id: str, *, timeout: int | None = None
    ) -> CheckResponse:
        return self._check(
            '/graphic',
            request_id,
            timeout=timeout,
            allowed_response_keys={'graphic'},
        )

    def graphic_cancel(self, request_id: str) -> DeleteResponse:
        return self._cancel('/graphic', request_id)

    def configuration_send(
        self, configuration: ConfigurationCommand | dict[str, Any]
    ) -> CreatedResponse:
        return self._send(
            '/configuration',
            'configuration',
            configuration,
            ConfigurationCommand,
        )

    def configuration_confirm(self, request_id: str) -> ConfirmedResponse:
        return self._confirm('/configuration', request_id)

    def configuration_check(
        self, request_id: str, *, timeout: int | None = None
    ) -> CheckResponse:
        return self._check(
            '/configuration',
            request_id,
            timeout=timeout,
            allowed_response_keys={'configuration'},
        )

    def configuration_cancel(self, request_id: str) -> DeleteResponse:
        return self._cancel('/configuration', request_id)

    def status_send(self, status: StatusCommand | dict[str, Any]) -> CreatedResponse:
        return self._send('/status', 'status', status, StatusCommand)

    def status_confirm(self, request_id: str) -> ConfirmedResponse:
        return self._confirm('/status', request_id)

    def status_check(
        self, request_id: str, *, timeout: int | None = None
    ) -> CheckResponse:
        return self._check(
            '/status',
            request_id,
            timeout=timeout,
            allowed_response_keys={'status'},
        )

    def status_cancel(self, request_id: str) -> DeleteResponse:
        return self._cancel('/status', request_id)

    def direct_io_send(
        self, direct_io: DirectIOCommand | dict[str, Any]
    ) -> CreatedResponse:
        return self._send('/direct_io', 'direct_io', direct_io, DirectIOCommand)

    def direct_io_confirm(self, request_id: str) -> ConfirmedResponse:
        return self._confirm('/direct_io', request_id)

    def direct_io_check(
        self, request_id: str, *, timeout: int | None = None
    ) -> CheckResponse:
        return self._check(
            '/direct_io',
            request_id,
            timeout=timeout,
            allowed_response_keys={'packet'},
        )

    def direct_io_cancel(self, request_id: str) -> DeleteResponse:
        return self._cancel('/direct_io', request_id)

    def lock_send(self, lock: LockCommand | dict[str, Any]) -> CreatedResponse:
        return self._send('/lock', 'lock', lock, LockCommand)

    def lock_confirm(self, request_id: str) -> ConfirmedResponse:
        return self._confirm('/lock', request_id)

    def lock_check(
        self, request_id: str, *, timeout: int | None = None
    ) -> CheckResponse:
        return self._check(
            '/lock',
            request_id,
            timeout=timeout,
            allowed_response_keys=set(),
        )

    def lock_cancel(self, request_id: str) -> DeleteResponse:
        return self._cancel('/lock', request_id)


class NoviApiAsyncClient(_AsyncRequestMixin):
    def __init__(
        self,
        base_url: str,
        *,
        timeout: httpx.Timeout | float = 5.0,
        verify: bool | str = True,
        transport: httpx.AsyncBaseTransport | None = None,
        trust_env: bool = False,
    ) -> None:
        normalized_base_url = _normalize_base_url(base_url)
        self._root_url = normalized_base_url
        self._client = httpx.AsyncClient(
            base_url=normalized_base_url,
            timeout=timeout,
            verify=verify,
            transport=transport,
            trust_env=trust_env,
            headers={'User-Agent': 'novitus-noviapi'},
        )
        self._token_provider = _AsyncTokenProvider(self._client)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> NoviApiAsyncClient:
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        await self.aclose()

    async def comm_test(self) -> bool:
        response = await self._request('GET', self._root_url, require_auth=False)
        return response.status_code == 200

    async def token_get(self) -> TokenResponse:
        return await self._token_provider.request_new_token()

    async def token_refresh(self, current_token: str | None = None) -> TokenResponse:
        return await self._token_provider.refresh_token(current_token)

    async def queue_check(self) -> QueueStatusResponse:
        response = await self._request('GET', '/queue')
        return _validate_json_response(response, QueueStatusResponse)

    async def queue_clear(self) -> QueueDeleteResponse:
        response = await self._request('DELETE', '/queue')
        return _validate_json_response(response, QueueDeleteResponse)

    async def receipt_send(self, receipt: Receipt | dict[str, Any]) -> CreatedResponse:
        return await self._send('/receipt', 'receipt', receipt, Receipt)

    async def receipt_confirm(self, request_id: str) -> ConfirmedResponse:
        return await self._confirm('/receipt', request_id)

    async def receipt_check(
        self, request_id: str, *, timeout: int | None = None
    ) -> CheckResponse:
        return await self._check(
            '/receipt',
            request_id,
            timeout=timeout,
            allowed_response_keys=set(),
        )

    async def receipt_cancel(self, request_id: str) -> DeleteResponse:
        return await self._cancel('/receipt', request_id)

    async def invoice_send(self, invoice: Invoice | dict[str, Any]) -> CreatedResponse:
        return await self._send('/invoice', 'invoice', invoice, Invoice)

    async def invoice_confirm(self, request_id: str) -> ConfirmedResponse:
        return await self._confirm('/invoice', request_id)

    async def invoice_check(
        self, request_id: str, *, timeout: int | None = None
    ) -> CheckResponse:
        return await self._check(
            '/invoice',
            request_id,
            timeout=timeout,
            allowed_response_keys=set(),
        )

    async def invoice_cancel(self, request_id: str) -> DeleteResponse:
        return await self._cancel('/invoice', request_id)

    async def nf_printout_send(
        self, printout: NonFiscal | dict[str, Any]
    ) -> CreatedResponse:
        return await self._send('/nf_printout', 'printout', printout, NonFiscal)

    async def nf_printout_confirm(self, request_id: str) -> ConfirmedResponse:
        return await self._confirm('/nf_printout', request_id)

    async def nf_printout_check(
        self, request_id: str, *, timeout: int | None = None
    ) -> CheckResponse:
        return await self._check(
            '/nf_printout',
            request_id,
            timeout=timeout,
            allowed_response_keys=set(),
        )

    async def nf_printout_cancel(self, request_id: str) -> DeleteResponse:
        return await self._cancel('/nf_printout', request_id)

    async def daily_report_send(
        self, daily_report: DailyReport | dict[str, Any]
    ) -> CreatedResponse:
        return await self._send(
            '/daily_report', 'daily_report', daily_report, DailyReport
        )

    async def daily_report_confirm(self, request_id: str) -> ConfirmedResponse:
        return await self._confirm('/daily_report', request_id)

    async def daily_report_check(
        self, request_id: str, *, timeout: int | None = None
    ) -> CheckResponse:
        return await self._check(
            '/daily_report',
            request_id,
            timeout=timeout,
            allowed_response_keys=set(),
        )

    async def daily_report_cancel(self, request_id: str) -> DeleteResponse:
        return await self._cancel('/daily_report', request_id)

    async def eft_send(self, eft: EFTCommand | dict[str, Any]) -> CreatedResponse:
        return await self._send('/eft', 'eft', eft, EFTCommand)

    async def eft_confirm(self, request_id: str) -> ConfirmedResponse:
        return await self._confirm('/eft', request_id)

    async def eft_check(
        self, request_id: str, *, timeout: int | None = None
    ) -> CheckResponse:
        return await self._check(
            '/eft',
            request_id,
            timeout=timeout,
            allowed_response_keys={'eft'},
        )

    async def eft_cancel(self, request_id: str) -> DeleteResponse:
        return await self._cancel('/eft', request_id)

    async def graphic_send(
        self, graphic: GraphicCommand | dict[str, Any]
    ) -> CreatedResponse:
        return await self._send('/graphic', 'graphic', graphic, GraphicCommand)

    async def graphic_confirm(self, request_id: str) -> ConfirmedResponse:
        return await self._confirm('/graphic', request_id)

    async def graphic_check(
        self, request_id: str, *, timeout: int | None = None
    ) -> CheckResponse:
        return await self._check(
            '/graphic',
            request_id,
            timeout=timeout,
            allowed_response_keys={'graphic'},
        )

    async def graphic_cancel(self, request_id: str) -> DeleteResponse:
        return await self._cancel('/graphic', request_id)

    async def configuration_send(
        self, configuration: ConfigurationCommand | dict[str, Any]
    ) -> CreatedResponse:
        return await self._send(
            '/configuration',
            'configuration',
            configuration,
            ConfigurationCommand,
        )

    async def configuration_confirm(self, request_id: str) -> ConfirmedResponse:
        return await self._confirm('/configuration', request_id)

    async def configuration_check(
        self, request_id: str, *, timeout: int | None = None
    ) -> CheckResponse:
        return await self._check(
            '/configuration',
            request_id,
            timeout=timeout,
            allowed_response_keys={'configuration'},
        )

    async def configuration_cancel(self, request_id: str) -> DeleteResponse:
        return await self._cancel('/configuration', request_id)

    async def status_send(
        self, status: StatusCommand | dict[str, Any]
    ) -> CreatedResponse:
        return await self._send('/status', 'status', status, StatusCommand)

    async def status_confirm(self, request_id: str) -> ConfirmedResponse:
        return await self._confirm('/status', request_id)

    async def status_check(
        self, request_id: str, *, timeout: int | None = None
    ) -> CheckResponse:
        return await self._check(
            '/status',
            request_id,
            timeout=timeout,
            allowed_response_keys={'status'},
        )

    async def status_cancel(self, request_id: str) -> DeleteResponse:
        return await self._cancel('/status', request_id)

    async def direct_io_send(
        self, direct_io: DirectIOCommand | dict[str, Any]
    ) -> CreatedResponse:
        return await self._send('/direct_io', 'direct_io', direct_io, DirectIOCommand)

    async def direct_io_confirm(self, request_id: str) -> ConfirmedResponse:
        return await self._confirm('/direct_io', request_id)

    async def direct_io_check(
        self, request_id: str, *, timeout: int | None = None
    ) -> CheckResponse:
        return await self._check(
            '/direct_io',
            request_id,
            timeout=timeout,
            allowed_response_keys={'packet'},
        )

    async def direct_io_cancel(self, request_id: str) -> DeleteResponse:
        return await self._cancel('/direct_io', request_id)

    async def lock_send(self, lock: LockCommand | dict[str, Any]) -> CreatedResponse:
        return await self._send('/lock', 'lock', lock, LockCommand)

    async def lock_confirm(self, request_id: str) -> ConfirmedResponse:
        return await self._confirm('/lock', request_id)

    async def lock_check(
        self, request_id: str, *, timeout: int | None = None
    ) -> CheckResponse:
        return await self._check(
            '/lock',
            request_id,
            timeout=timeout,
            allowed_response_keys=set(),
        )

    async def lock_cancel(self, request_id: str) -> DeleteResponse:
        return await self._cancel('/lock', request_id)
