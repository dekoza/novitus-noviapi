from __future__ import annotations

from noviapi.models import ErrorEnvelope


class NoviApiError(Exception):
    pass


class NoviApiTransportError(NoviApiError):
    pass


class NoviApiResponseError(NoviApiError):
    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        detail: ErrorEnvelope | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.detail = detail


class ValidationErrorResponse(NoviApiResponseError):
    pass


class AuthenticationError(NoviApiResponseError):
    pass


class MultipleAccessError(AuthenticationError):
    pass


class NotFoundError(NoviApiResponseError):
    pass


class ConflictError(NoviApiResponseError):
    pass


class TooManyTokenRequestsError(NoviApiResponseError):
    pass


class InternalServerError(NoviApiResponseError):
    pass


class ProtectedMemoryFullError(NoviApiResponseError):
    pass
