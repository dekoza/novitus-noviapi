from __future__ import annotations

import pytest

from noviapi._hardware_polling import poll_hardware_request
from noviapi.models import CheckResponse


def _check_response(status: str) -> CheckResponse:
    return CheckResponse.model_validate(
        {
            'device': {'status': 'OK'},
            'request': {'status': status, 'id': 'a' * 32},
        }
    )


def test_poll_hardware_request_retries_pending_statuses() -> None:
    timeouts: list[int] = []
    responses = iter([_check_response('PENDING'), _check_response('DONE')])

    def check_request(request_id: str, *, timeout: int | None = None) -> CheckResponse:
        assert request_id == 'a' * 32
        assert timeout is not None
        timeouts.append(timeout)
        return next(responses)

    response = poll_hardware_request(check_request, 'a' * 32, timeout_ms=30_000)

    assert response.request.status == 'DONE'
    assert timeouts == [30_000, 30_000]


def test_poll_hardware_request_returns_last_response_after_max_attempts() -> None:
    attempts = 0

    def check_request(request_id: str, *, timeout: int | None = None) -> CheckResponse:
        nonlocal attempts
        attempts += 1
        return _check_response('PENDING')

    response = poll_hardware_request(
        check_request,
        'a' * 32,
        timeout_ms=30_000,
        max_attempts=2,
    )

    assert response.request.status == 'PENDING'
    assert attempts == 2


def test_poll_hardware_request_stops_on_error_status() -> None:
    attempts = 0

    def check_request(request_id: str, *, timeout: int | None = None) -> CheckResponse:
        nonlocal attempts
        attempts += 1
        return _check_response('ERROR')

    response = poll_hardware_request(check_request, 'a' * 32, timeout_ms=30_000)

    assert response.request.status == 'ERROR'
    assert attempts == 1


def test_poll_hardware_request_retries_queued_status() -> None:
    attempts = 0
    responses = iter([_check_response('QUEUED'), _check_response('DONE')])

    def check_request(request_id: str, *, timeout: int | None = None) -> CheckResponse:
        nonlocal attempts
        attempts += 1
        return next(responses)

    response = poll_hardware_request(check_request, 'a' * 32, timeout_ms=30_000)

    assert response.request.status == 'DONE'
    assert attempts == 2


def test_poll_hardware_request_stops_on_unknown_status() -> None:
    attempts = 0

    def check_request(request_id: str, *, timeout: int | None = None) -> CheckResponse:
        nonlocal attempts
        attempts += 1
        return _check_response('UNKNOWN')

    response = poll_hardware_request(check_request, 'a' * 32, timeout_ms=30_000)

    assert response.request.status == 'UNKNOWN'
    assert attempts == 1


def test_poll_hardware_request_rejects_non_positive_attempt_count() -> None:
    with pytest.raises(ValueError, match='max_attempts'):
        poll_hardware_request(
            lambda request_id, *, timeout=None: _check_response('DONE'),
            'a' * 32,
            timeout_ms=30_000,
            max_attempts=0,
        )
