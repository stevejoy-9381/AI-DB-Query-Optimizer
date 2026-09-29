"""tests/test_config.py
Tests for configuration management, settings precedence, secret masking, and validation.
"""

import os
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from config import (
    AppSettings,
    Dialect,
    get_current_dialect,
    get_dialect_config,
    load_settings,
    mask_secret,
    set_dialect,
)


def test_default_settings():
    settings = AppSettings()
    assert settings.db_host == "localhost"
    assert settings.db_port == 3306
    assert settings.default_dialect == "mysql"
    assert settings.max_query_length == 20000


def test_settings_validation_invalid_port():
    with pytest.raises(ValidationError):
        AppSettings(db_port=70000)

    with pytest.raises(ValidationError):
        AppSettings(db_port=0)


def test_settings_validation_benchmark_runs():
    with pytest.raises(ValidationError):
        AppSettings(benchmark_runs=0)


def test_mask_secret():
    assert mask_secret(None) == ""
    assert mask_secret("") == ""
    assert mask_secret("short") == "*" * 1 + "hort"
    assert mask_secret("12", visible_chars=4) == "****"
    assert mask_secret("my_super_secret_key_1234", visible_chars=4).endswith("1234")
    assert mask_secret("my_super_secret_key_1234", visible_chars=4).startswith("****")


def test_safe_dict_masks_credentials():
    settings = AppSettings(
        db_password="super_secret_password",
        gemini_api_key="AIzaSyA1234567890",
        openai_api_key="sk-proj-1234567890",
        test_db_url="mysql+pymysql://root:mypassword@localhost:3306/shop_db",
    )
    safe = settings.safe_dict()
    assert "super_secret_password" not in safe["db_password"]
    assert "1234567890" not in safe["gemini_api_key"][:8]
    assert "mypassword" not in safe["test_db_url"]
    assert "***" in safe["test_db_url"]


def test_env_var_override():
    with patch.dict(os.environ, {"DB_PORT": "3307", "DB_DATABASE": "custom_shop"}):
        settings = load_settings()
        assert settings.db_port == 3307
        assert settings.db_database == "custom_shop"


def test_dialect_configuration():
    mysql_cfg = get_dialect_config(Dialect.MYSQL)
    assert mysql_cfg.default_port == 3306
    assert mysql_cfg.explain_command == "EXPLAIN FORMAT=JSON"
    assert mysql_cfg.supports_include_indexes is False

    pg_cfg = get_dialect_config(Dialect.POSTGRESQL)
    assert pg_cfg.default_port == 5432
    assert pg_cfg.supports_include_indexes is True

    # Switching active dialect
    set_dialect("postgresql")
    assert get_current_dialect() == Dialect.POSTGRESQL
    set_dialect("mysql")
    assert get_current_dialect() == Dialect.MYSQL
