from typing import Any


class GlunovaException(Exception):
    """Base application exception."""

    def __init__(self, message: str, code: str = "error", status_code: int = 400) -> None:
        self.message = message
        self.code = code
        self.status_code = status_code
        super().__init__(message)


class NotFoundError(GlunovaException):
    def __init__(self, message: str = "Resource not found") -> None:
        super().__init__(message, code="not_found", status_code=404)


class ConflictError(GlunovaException):
    def __init__(self, message: str = "Resource conflict") -> None:
        super().__init__(message, code="conflict", status_code=409)


class ForbiddenError(GlunovaException):
    def __init__(self, message: str = "Forbidden") -> None:
        super().__init__(message, code="forbidden", status_code=403)


class UnauthorizedError(GlunovaException):
    def __init__(self, message: str = "Unauthorized") -> None:
        super().__init__(message, code="unauthorized", status_code=401)


class ValidationAppError(GlunovaException):
    def __init__(self, message: str = "Validation error") -> None:
        super().__init__(message, code="validation_error", status_code=422)


def error_payload(message: str, code: str, details: Any = None) -> dict[str, Any]:
    body: dict[str, Any] = {"detail": message, "code": code}
    if details is not None:
        body["details"] = details
    return body
