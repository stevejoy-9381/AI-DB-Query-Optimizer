"""Custom exception classes for AI DB Query Optimizer."""

from typing import Optional


class OptimizerError(Exception):
    """Base exception for all optimizer errors."""

    def __init__(self, message: str, details: Optional[str] = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details

    def __str__(self) -> str:
        if self.details:
            return f"{self.message} (Details: {self.details})"
        return self.message


class QueryParseError(OptimizerError):
    """Raised when SQL parsing fails or dialect syntax is unsupported."""

    def __init__(
        self,
        message: str = "Failed to parse SQL query",
        line: Optional[int] = None,
        col: Optional[int] = None,
        details: Optional[str] = None,
    ) -> None:
        super().__init__(message, details)
        self.line = line
        self.col = col


class UnsafeQueryError(OptimizerError):
    """Raised when a query violates safety constraints (e.g. destructive DDL/DML)."""

    def __init__(
        self,
        message: str = "Unsafe query detected",
        hazard_type: str = "CRITICAL",
        details: Optional[str] = None,
    ) -> None:
        super().__init__(message, details)
        self.hazard_type = hazard_type


class DBConnectionError(OptimizerError):
    """Raised when connecting to or authenticating with database fails."""

    def __init__(
        self,
        message: str = "Database connection failed",
        host: Optional[str] = None,
        database: Optional[str] = None,
        details: Optional[str] = None,
    ) -> None:
        super().__init__(message, details)
        self.host = host
        self.database = database


class DBExecutionError(OptimizerError):
    """Raised when an EXPLAIN or read query fails during database execution."""

    def __init__(
        self,
        message: str = "Database execution failed",
        sql: Optional[str] = None,
        details: Optional[str] = None,
    ) -> None:
        super().__init__(message, details)
        self.sql = sql


class LLMError(OptimizerError):
    """Raised when an LLM provider fails, times out, or returns invalid response."""

    def __init__(
        self,
        message: str = "LLM request failed",
        provider: Optional[str] = None,
        details: Optional[str] = None,
    ) -> None:
        super().__init__(message, details)
        self.provider = provider


class SchemaParseError(OptimizerError):
    """Raised when parsing pasted DDL statements fails."""

    def __init__(
        self,
        message: str = "Failed to parse schema DDL",
        statement: Optional[str] = None,
        details: Optional[str] = None,
    ) -> None:
        super().__init__(message, details)
        self.statement = statement
