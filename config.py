"""config.py
Configuration module, database dialect abstraction, and settings management.

Provides centralized configuration for application settings (precedence: st.secrets > env > .env > defaults)
and database dialects (default: MySQL 8.x) with modular traits for future multi-dialect support.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


# ===========================================================================
# 1. Dialect Abstraction
# ===========================================================================

class Dialect(str, Enum):
    """Supported database dialects."""
    MYSQL = "mysql"
    POSTGRESQL = "postgresql"


@dataclass(frozen=True)
class DialectConfig:
    """Encapsulates dialect-specific syntax, features, and defaults."""
    name: Dialect
    display_name: str
    target_version: str
    default_port: int
    explain_command: str
    supports_include_indexes: bool
    connection_poolers: list[str]
    access_types: list[str] = field(default_factory=list)
    cost_units_description: str = ""

    def format_covering_index(
        self,
        table: str,
        index_name: str,
        filter_col: str,
        projected_cols: list[str],
    ) -> str:
        """Generate DDL for a covering index according to dialect rules."""
        if self.supports_include_indexes:
            proj_str = ", ".join(projected_cols) if projected_cols else "col1, col2"
            return (
                f"-- PostgreSQL covering index with non-key payload columns:\n"
                f"CREATE INDEX {index_name}\n"
                f"    ON {table}({filter_col}) INCLUDE ({proj_str});"
            )

        all_cols = [filter_col] + [c for c in projected_cols if c != filter_col]
        cols_str = ", ".join(all_cols)
        return (
            f"-- MySQL 8.x covering index (InnoDB composite B-tree):\n"
            f"CREATE INDEX {index_name}\n"
            f"    ON {table}({cols_str});"
        )

    def format_fulltext_index(
        self,
        table: str,
        index_name: str,
        column: str,
    ) -> str:
        """Generate DDL for full-text index according to dialect rules."""
        if self.name == Dialect.POSTGRESQL:
            return (
                f"-- PostgreSQL full-text index using GIN:\n"
                f"CREATE INDEX {index_name} ON {table} USING gin(to_tsvector('english', {column}));"
            )

        return (
            f"-- MySQL 8.x InnoDB full-text index:\n"
            f"ALTER TABLE {table} ADD FULLTEXT INDEX {index_name} ({column});"
        )


DIALECT_REGISTRY: dict[Dialect, DialectConfig] = {
    Dialect.MYSQL: DialectConfig(
        name=Dialect.MYSQL,
        display_name="MySQL",
        target_version="8.0+",
        default_port=3306,
        explain_command="EXPLAIN FORMAT=JSON",
        supports_include_indexes=False,
        connection_poolers=["ProxySQL", "MySQL Router", "application-level pooling"],
        access_types=["const", "eq_ref", "ref", "range", "index", "ALL"],
        cost_units_description="MySQL cost model (memory_block_read_cost=0.25, io_block_read_cost=1.0, row_eval=0.10)",
    ),
    Dialect.POSTGRESQL: DialectConfig(
        name=Dialect.POSTGRESQL,
        display_name="PostgreSQL",
        target_version="15+",
        default_port=5432,
        explain_command="EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)",
        supports_include_indexes=True,
        connection_poolers=["PgBouncer", "pgpool-II"],
        access_types=["Seq Scan", "Index Scan", "Bitmap Index Scan", "Index Only Scan"],
        cost_units_description="PostgreSQL cost model (seq_page_cost=1.0, random_page_cost=4.0, cpu_tuple_cost=0.01)",
    ),
}

_ACTIVE_DIALECT: Dialect = Dialect.MYSQL


def get_current_dialect() -> Dialect:
    """Return the active dialect enum."""
    return _ACTIVE_DIALECT


def get_dialect_config(dialect: Dialect | str | None = None) -> DialectConfig:
    """Return configuration for the requested or currently active dialect."""
    if dialect is None:
        target = _ACTIVE_DIALECT
    elif isinstance(dialect, Dialect):
        target = dialect
    else:
        try:
            target = Dialect(dialect.lower().strip())
        except ValueError:
            logger.warning("Unknown dialect '%s', falling back to MySQL", dialect)
            target = Dialect.MYSQL

    return DIALECT_REGISTRY[target]


def set_dialect(dialect: Dialect | str) -> None:
    """Set the active dialect for query analysis and recommendations."""
    global _ACTIVE_DIALECT
    if isinstance(dialect, Dialect):
        _ACTIVE_DIALECT = dialect
    else:
        try:
            _ACTIVE_DIALECT = Dialect(dialect.lower().strip())
        except ValueError as err:
            valid = ", ".join(d.value for d in Dialect)
            raise ValueError(f"Invalid dialect '{dialect}'. Supported dialects: {valid}") from err
    logger.info("Active dialect set to: %s", _ACTIVE_DIALECT.value)


def is_mysql() -> bool:
    """Convenience helper to check if active dialect is MySQL."""
    return _ACTIVE_DIALECT == Dialect.MYSQL


# ===========================================================================
# 2. Application Settings and Secrets Management
# ===========================================================================

def mask_secret(secret: Optional[str], visible_chars: int = 4) -> str:
    """Mask a secret string for safe logging and presentation.

    Args:
        secret: String secret to mask.
        visible_chars: Number of trailing characters to leave unmasked.

    Returns:
        str: Masked string (e.g. '****abcd') or empty string if None.
    """
    if not secret:
        return ""
    if visible_chars <= 0:
        return "*" * len(secret)
    if len(secret) <= visible_chars:
        return "****"
    return "*" * (len(secret) - visible_chars) + secret[-visible_chars:]


class AppSettings(BaseSettings):
    """Centralized application settings with strict validation and precedence."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        populate_by_name=True,
    )

    # Database connection
    db_host: str = Field(default="localhost", alias="DB_HOST")
    db_port: int = Field(default=3306, alias="DB_PORT")
    db_user: str = Field(default="root", alias="DB_USER")
    db_password: str = Field(default="", alias="DB_PASSWORD")
    db_database: str = Field(default="shop_db", alias="DB_DATABASE")
    db_connect_timeout: int = Field(default=5, alias="DB_CONNECT_TIMEOUT")
    db_read_timeout: int = Field(default=30, alias="DB_READ_TIMEOUT")

    # Dialect
    default_dialect: str = Field(default="mysql", alias="DEFAULT_DIALECT")

    # Application limits & logs
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    max_query_length: int = Field(default=20000, alias="MAX_QUERY_LENGTH")

    # Benchmarking
    benchmark_runs: int = Field(default=5, alias="BENCHMARK_RUNS")
    benchmark_warmup: int = 1
    benchmark_timeout_seconds: int = 30

    # AI / LLM configuration
    llm_provider: str = Field(default="gemini", alias="LLM_PROVIDER")
    llm_model: str = Field(default="gemini-1.5-flash", alias="LLM_MODEL")
    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")

    # Integration test URL
    test_db_url: str = Field(default="", alias="TEST_DB_URL")

    @field_validator("db_port")
    @classmethod
    def validate_port(cls, v: int) -> int:
        if not (1 <= v <= 65535):
            raise ValueError(f"Port must be between 1 and 65535, got {v}")
        return v

    @field_validator("benchmark_runs")
    @classmethod
    def validate_benchmark_runs(cls, v: int) -> int:
        if v < 1:
            raise ValueError("benchmark_runs must be at least 1")
        return v

    @field_validator("max_query_length")
    @classmethod
    def validate_max_query_length(cls, v: int) -> int:
        if v < 100:
            raise ValueError("max_query_length must be at least 100 characters")
        return v

    def masked_password(self) -> str:
        """Return masked database password."""
        return mask_secret(self.db_password, visible_chars=0)

    def masked_api_key(self, provider: str = "gemini") -> str:
        """Return masked API key for the requested provider."""
        key = self.gemini_api_key if provider.lower() == "gemini" else self.openai_api_key
        return mask_secret(key, visible_chars=4)

    def safe_dict(self) -> dict[str, Any]:
        """Return a dictionary representation with sensitive secrets masked."""
        d = self.model_dump()
        d["db_password"] = self.masked_password()
        d["gemini_api_key"] = mask_secret(self.gemini_api_key)
        d["openai_api_key"] = mask_secret(self.openai_api_key)
        if self.test_db_url:
            d["test_db_url"] = re.sub(r"(://[^:]+:)([^@]+)(@)", r"\1***\3", self.test_db_url)
        return d


def load_settings() -> AppSettings:
    """Load settings following the precedence: st.secrets > os.environ > .env > defaults.

    Returns:
        AppSettings: Validated settings instance.
    """
    secrets_data: dict[str, Any] = {}

    # Attempt to load from streamlit secrets if available
    try:
        import streamlit as st
        if hasattr(st, "secrets") and st.secrets:
            for k, v in st.secrets.items():
                if isinstance(v, (str, int, float, bool)):
                    secrets_data[k.upper()] = v
    except Exception:
        pass

    # Merge: Streamlit secrets take precedence over environment variables
    merged_env = dict(os.environ)
    for k, v in secrets_data.items():
        merged_env[k] = str(v)

    try:
        return AppSettings(_env_file=".env", **merged_env)  # type: ignore[call-arg]
    except Exception as exc:
        logger.warning("Error loading settings with strict validation: %s. Using default settings.", exc)
        return AppSettings()
