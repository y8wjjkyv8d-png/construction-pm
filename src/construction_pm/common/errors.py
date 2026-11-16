"""Типізовані доменні помилки. Адаптер WebAPI перетворює їх на HTTP-коди."""


class DomainError(Exception):
    """Базова помилка бізнес-логіки."""

    code = "domain_error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ValidationError(DomainError):
    """Порушено інваріант або передано некоректні дані (HTTP 422)."""

    code = "validation_error"


class NotFoundError(DomainError):
    """Сутність не знайдена (HTTP 404)."""

    code = "not_found"


class ConflictError(DomainError):
    """Дія конфліктує з поточним станом (HTTP 409)."""

    code = "conflict"
