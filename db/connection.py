"""Database connection manager using SQLAlchemy and PyMySQL for MySQL 8.x."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote_plus

import sqlalchemy
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError, ProgrammingError, SQLAlchemyError

logger = logging.getLogger(__name__)


@dataclass
class DBConfig:
    """Connection parameters for MySQL database."""

    host: str = "localhost"
    port: int = 3306
    user: str = "root"
    password: str = ""
    database: str = ""
    connect_timeout: int = 5
    read_timeout: int = 30

    def to_display_dict(self) -> dict[str, Any]:
        """Return safe dictionary with password masked for UI display and logs."""
        return {
            "host": self.host,
            "port": self.port,
            "user": self.user,
            "database": self.database,
            "connect_timeout": self.connect_timeout,
            "read_timeout": self.read_timeout,
        }

    def get_url(self) -> str:
        """Build SQLAlchemy connection URL with safely escaped credentials."""
        safe_user = quote_plus(self.user)
        safe_password = quote_plus(self.password)
        safe_db = quote_plus(self.database) if self.database else ""
        
        # When database is empty, connect without selecting database (e.g. for server ping)
        db_path = f"/{safe_db}" if safe_db else ""
        return f"mysql+pymysql://{safe_user}:{safe_password}@{self.host}:{self.port}{db_path}"


def build_engine(config: DBConfig) -> Engine:
    """Create a SQLAlchemy engine configured for MySQL 8.x.

    Args:
        config: Connection configuration.

    Returns:
        SQLAlchemy Engine instance.
    """
    url = config.get_url()
    connect_args = {
        "connect_timeout": config.connect_timeout,
        "read_timeout": config.read_timeout,
        "charset": "utf8mb4",
    }
    logger.info("Building SQLAlchemy engine for %s@%s:%s/%s", config.user, config.host, config.port, config.database)
    return create_engine(
        url,
        pool_pre_ping=True,
        pool_recycle=3600,
        connect_args=connect_args,
    )


def test_connection(config: DBConfig) -> tuple[bool, str]:
    """Test connection to the database and return categorized status.

    Args:
        config: Connection configuration.

    Returns:
        Tuple of (success_boolean, human_readable_message).
    """
    if not config.user:
        return False, "Username cannot be empty."

    engine = None
    try:
        engine = build_engine(config)
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1 AS ping"))
            row = result.fetchone()
            if row and row[0] == 1:
                return True, f"Successfully connected to MySQL database '{config.database or 'server'}'."
            return False, "Connected but ping query returned unexpected result."

    except OperationalError as err:
        err_msg = str(err).lower()
        orig_code = getattr(err.orig, "args", [None])[0] if hasattr(err, "orig") else None

        if orig_code == 1045 or "access denied" in err_msg:
            return False, f"Access denied for user '{config.user}'. Check your username and password."
        if orig_code == 1049 or "unknown database" in err_msg:
            return False, f"Unknown database '{config.database}'. Please verify the database exists."
        if orig_code == 2003 or "can't connect to mysql server" in err_msg or "connection refused" in err_msg:
            return False, f"Host unreachable: cannot connect to {config.host}:{config.port}. Verify MySQL is running and network/firewall allows access."
        if "timed out" in err_msg or "timeout" in err_msg:
            return False, f"Connection timed out after {config.connect_timeout} seconds."

        return False, f"Database connection error: {_clean_error_message(str(err))}"

    except ProgrammingError as err:
        return False, f"SQL configuration error: {_clean_error_message(str(err))}"

    except SQLAlchemyError as err:
        return False, f"SQLAlchemy error: {_clean_error_message(str(err))}"

    except Exception as err:
        return False, f"Unexpected error while connecting: {_clean_error_message(str(err))}"

    finally:
        if engine:
            try:
                engine.dispose()
            except Exception:
                pass


def close_engine(engine: Engine | None) -> None:
    """Safely dispose of an existing database engine."""
    if engine is not None:
        try:
            engine.dispose()
            logger.info("Database engine connection pool disposed.")
        except Exception as err:
            logger.warning("Error disposing database engine: %s", err)


def _clean_error_message(raw_msg: str) -> str:
    """Sanitize error message to ensure passwords or sensitive strings aren't leaked."""
    lines = raw_msg.splitlines()
    first_line = lines[0] if lines else raw_msg
    # Truncate overly long error traces
    return first_line[:200]
