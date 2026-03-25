from __future__ import annotations

from typing import Protocol

from noviapi.models import CheckResponse

TERMINAL_REQUEST_STATUSES = {'DONE', 'ERROR'}
RETRYABLE_REQUEST_STATUSES = {'QUEUED', 'PENDING'}


class CheckRequest(Protocol):
    def __call__(
        self, request_id: str, *, timeout: int | None = None
    ) -> CheckResponse: ...


def poll_hardware_request(
    check_request: CheckRequest,
    request_id: str,
    *,
    timeout_ms: int,
    max_attempts: int = 3,
) -> CheckResponse:
    if max_attempts < 1:
        raise ValueError('max_attempts must be at least 1')

    response: CheckResponse | None = None
    for _ in range(max_attempts):
        response = check_request(request_id, timeout=timeout_ms)
        if response.request.status in TERMINAL_REQUEST_STATUSES:
            return response
        if response.request.status not in RETRYABLE_REQUEST_STATUSES:
            return response

    assert response is not None
    return response
