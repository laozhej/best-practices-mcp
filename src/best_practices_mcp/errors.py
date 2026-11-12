"""Expected application failures, independent of MCP transport envelopes."""

from typing import Any


class DomainError(Exception):
    """A stable error code and safe recovery details for a tool boundary."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: dict[str, Any] | None = None,
        recovery: str = "Correct the input and try again.",
        retry_after_seconds: int | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}
        self.recovery = recovery
        self.retry_after_seconds = retry_after_seconds

    def to_payload(self) -> dict[str, Any]:
        """Return domain data; the SDK adapter adds isError and content blocks."""
        return {
            "schema_version": 1,
            "error": {
                "code": self.code,
                "message": self.message,
                "details": self.details,
                "recovery": self.recovery,
                "retry_after_seconds": self.retry_after_seconds,
            },
        }
