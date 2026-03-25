from __future__ import annotations

from noviapi.exceptions import (
    AuthenticationError,
    NoviApiResponseError,
    TooManyTokenRequestsError,
)
from noviapi.models import ApiExceptionDetails, ErrorEnvelope


def test_response_error_preserves_status_and_detail() -> None:
    detail = ErrorEnvelope(
        exception=ApiExceptionDetails(
            code=429,
            description='Too many token requests',
        )
    )

    error = TooManyTokenRequestsError(
        'Too many token requests',
        status_code=429,
        detail=detail,
    )

    assert error.status_code == 429
    assert error.detail is detail
    assert 'Too many token requests' in str(error)


def test_specific_response_errors_inherit_shared_base() -> None:
    assert issubclass(AuthenticationError, NoviApiResponseError)
    assert issubclass(TooManyTokenRequestsError, NoviApiResponseError)
