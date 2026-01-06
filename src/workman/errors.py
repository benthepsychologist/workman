"""Workman error types."""


class WorkmanError(Exception):
    """Base error for workman."""


class CompileError(WorkmanError):
    """Error during plan compilation."""

    def __init__(self, message: str, op: str | None = None):
        self.op = op
        super().__init__(message)


class ValidationError(WorkmanError):
    """Payload or schema validation error."""

    def __init__(self, message: str, errors: list[object] | None = None):
        self.errors = errors or []
        super().__init__(message)
