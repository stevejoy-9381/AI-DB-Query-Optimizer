"""Logging configuration with console and rotating file handlers, plus secret masking."""

import logging
import os
import re
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

# Regex patterns for sensitive data
SENSITIVE_PATTERNS = [
    re.compile(r"(password[\s:=]+)([^\s,;\"']+)", re.IGNORECASE),
    re.compile(r"(api[-_]?key[\s:=]+)([^\s,;\"']+)", re.IGNORECASE),
    re.compile(r"(bearer\s+)([A-Za-z0-9_\-\.]+)", re.IGNORECASE),
    re.compile(r"(mysql\+pymysql://[^:]+:)([^@]+)(@)", re.IGNORECASE),
]


class SecretMaskingFilter(logging.Filter):
    """Filter that masks passwords, API keys, and connection credentials."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = self.mask_secrets(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: self._mask_val(v) for k, v in record.args.items()}
            elif isinstance(record.args, tuple):
                record.args = tuple(self._mask_val(v) for v in record.args)
        return True

    @staticmethod
    def _mask_val(val: object) -> object:
        if isinstance(val, str):
            return SecretMaskingFilter.mask_secrets(val)
        return val

    @staticmethod
    def mask_secrets(text: str) -> str:
        """Replace detected secrets with redacted placeholder."""
        masked = text
        for pattern in SENSITIVE_PATTERNS:
            if pattern.pattern.startswith("(mysql\\+pymysql"):
                masked = pattern.sub(r"\1***\3", masked)
            else:
                masked = pattern.sub(r"\1***", masked)
        return masked


_configured = False


def setup_logging(
    level: str = "INFO",
    log_dir: str = "logs",
    log_file: str = "app.log",
    max_bytes: int = 5 * 1024 * 1024,
    backup_count: int = 3,
) -> logging.Logger:
    """Initialize root and app logging with console and rotating file handlers.

    Args:
        level: Minimum log level string (e.g. 'DEBUG', 'INFO', 'WARNING').
        log_dir: Directory where logs should be stored.
        log_file: Log file name.
        max_bytes: Maximum size of a log file before rotation.
        backup_count: Number of rotated log backups to retain.

    Returns:
        logging.Logger: The configured application logger.
    """
    global _configured
    root_logger = logging.getLogger()
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    if _configured:
        root_logger.setLevel(numeric_level)
        return logging.getLogger("optimizer")

    root_logger.setLevel(numeric_level)

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    masking_filter = SecretMaskingFilter()

    # 1. Console Handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.addFilter(masking_filter)
    console_handler.setLevel(numeric_level)
    root_logger.addHandler(console_handler)

    # 2. Rotating File Handler
    try:
        Path(log_dir).mkdir(parents=True, exist_ok=True)
        file_path = os.path.join(log_dir, log_file)
        file_handler = RotatingFileHandler(
            file_path,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        file_handler.addFilter(masking_filter)
        file_handler.setLevel(numeric_level)
        root_logger.addHandler(file_handler)
    except OSError:
        # Fall back gracefully if filesystem is read-only
        pass

    _configured = True
    return logging.getLogger("optimizer")


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Return a logger child of the optimizer namespace.

    Args:
        name: Subsystem name or module name.

    Returns:
        logging.Logger: Child logger instance.
    """
    if not _configured:
        setup_logging()
    if name:
        return logging.getLogger(f"optimizer.{name}")
    return logging.getLogger("optimizer")
