"""utils/validation.py
Input validation and user-friendly error diagnostic formatters.

Protects the application from malformed, oversized, multi-statement, or non-text queries,
and formats database connection and syntax errors with clear troubleshooting actions.
"""

from __future__ import annotations

import re
import uuid
from typing import Optional, Tuple

import sqlglot
from sqlglot.errors import ParseError


def validate_sql_input(
    raw_query: str,
    max_length: int = 20000,
    dialect: str = "mysql",
) -> Tuple[bool, Optional[str]]:
    """Validate user SQL query input against size, syntax, and safety limits.

    Args:
        raw_query: Raw user input SQL string.
        max_length: Character limit for queries.
        dialect: SQL dialect for parser.

    Returns:
        Tuple of (is_valid, error_message_or_None).
    """
    if not raw_query or not raw_query.strip():
        return False, "Query cannot be empty. Please enter a SQL statement to analyze."

    cleaned = raw_query.strip()

    # 1. Null bytes or non-printable binary characters
    if "\x00" in cleaned or any(ord(c) < 32 and c not in "\n\r\t" for c in cleaned):
        return False, "Query contains invalid non-printable or null byte characters."

    # 2. Max length check
    if len(cleaned) > max_length:
        return (
            False,
            f"Query exceeds maximum permitted length ({len(cleaned):,} / {max_length:,} characters).",
        )

    # 3. Comments-only check
    no_comments = re.sub(r"--[^\n]*", "", cleaned)
    no_comments = re.sub(r"/\*.*?\*/", "", no_comments, flags=re.DOTALL).strip()
    if not no_comments:
        return False, "Query contains only comments without an executable SQL statement."

    # 4. Parse statements via sqlglot
    try:
        parsed_statements = sqlglot.parse(cleaned, read=dialect)
    except ParseError as parse_err:
        errors = getattr(parse_err, "errors", [])
        line = errors[0].get("line") if errors else None
        col = errors[0].get("col") if errors else None
        loc_str = f" at line {line}, col {col}" if line else ""
        return False, f"SQL Syntax Error{loc_str}: {parse_err}. Please check your syntax."
    except Exception as exc:
        return False, f"Failed to parse SQL query: {exc}"

    valid_stmts = [s for s in parsed_statements if s is not None]
    if len(valid_stmts) > 1:
        return (
            False,
            "Multiple SQL statements detected. Please submit a single query at a time for analysis.",
        )
    elif len(valid_stmts) == 0:
        return False, "Query contains no executable statements."

    return True, None


def format_connection_error(exc: Exception) -> dict[str, str]:
    """Inspect DB connection exception and return user-friendly diagnostic guidance.

    Returns:
        dict: {"title": ..., "detail": ..., "action": ...}
    """
    err_str = str(exc).lower()

    if "access denied" in err_str or "1045" in err_str:
        return {
            "title": "Authentication Failed (Error 1045)",
            "detail": "Incorrect username or password for MySQL database.",
            "action": "Check user credentials in sidebar and verify the user has access to this database.",
        }
    elif "unknown database" in err_str or "1049" in err_str:
        return {
            "title": "Database Not Found (Error 1049)",
            "detail": "The specified MySQL database does not exist.",
            "action": "Verify database name spelling or run `CREATE DATABASE <name>;` before connecting.",
        }
    elif "can't connect" in err_str or "2003" in err_str or "connection refused" in err_str:
        return {
            "title": "Host Unreachable (Error 2003)",
            "detail": "Could not connect to MySQL server at the given host and port.",
            "action": "Ensure MySQL service is actively running and port 3306 is open and accepting connections.",
        }
    elif "timed out" in err_str or "timeout" in err_str:
        return {
            "title": "Connection Timed Out",
            "detail": "Database connection took longer than the configured timeout.",
            "action": "Verify network connectivity, VPN, or firewall rules between application and database.",
        }
    else:
        return {
            "title": "Database Connection Error",
            "detail": str(exc),
            "action": "Check MySQL server logs and configuration settings in .env or secrets.",
        }


def generate_error_reference() -> str:
    """Generate a short unique incident reference ID for error boundaries."""
    return str(uuid.uuid4())[:8].upper()
