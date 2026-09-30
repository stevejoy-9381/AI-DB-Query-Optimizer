"""Tests for db/connection.py module."""

import os
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.exc import OperationalError

from db.connection import DBConfig, close_engine
from db.connection import test_connection as run_test_connection


def test_db_config_defaults():
    """Verify DBConfig initializes with expected defaults."""
    cfg = DBConfig()
    assert cfg.host == "localhost"
    assert cfg.port == 3306
    assert cfg.user == "root"
    assert cfg.password == ""
    assert cfg.database == ""
    assert cfg.connect_timeout == 5
    assert cfg.read_timeout == 30


def test_db_config_display_masks_password():
    """Verify to_display_dict does not contain the password key."""
    cfg = DBConfig(user="admin", password="super_secret_password", database="test_db")
    display = cfg.to_display_dict()
    assert "password" not in display
    assert display["user"] == "admin"
    assert display["database"] == "test_db"


def test_db_config_get_url_escaping():
    """Verify get_url properly handles special characters in credentials."""
    cfg = DBConfig(user="app_user", password="p@ss/word#123", database="my_db")
    url = cfg.get_url()
    assert "mysql+pymysql://app_user:p%40ss%2Fword%23123@localhost:3306/my_db" == url


def test_empty_user_validation():
    """Verify test_connection fails gracefully if user is empty."""
    cfg = DBConfig(user="")
    ok, msg = run_test_connection(cfg)
    assert not ok
    assert "Username cannot be empty" in msg


@patch("db.connection.build_engine")
def test_connection_success(mock_build_engine):
    """Verify test_connection returns True when ping succeeds."""
    mock_engine = MagicMock()
    mock_conn = MagicMock()
    mock_result = MagicMock()
    mock_result.fetchone.return_value = (1,)
    mock_conn.execute.return_value = mock_result
    mock_engine.connect.return_value.__enter__.return_value = mock_conn
    mock_build_engine.return_value = mock_engine

    cfg = DBConfig(user="test_user", database="test_db")
    ok, msg = run_test_connection(cfg)
    assert ok is True
    assert "Successfully connected" in msg


@patch("db.connection.build_engine")
def test_connection_wrong_password(mock_build_engine):
    """Verify MySQL 1045 access denied is categorized cleanly."""
    mock_engine = MagicMock()
    orig_exc = Exception(1045, "Access denied for user 'root'@'localhost'")
    orig_exc.args = (1045, "Access denied for user 'root'@'localhost'")
    mock_engine.connect.side_effect = OperationalError("Access denied", {}, orig_exc)
    mock_build_engine.return_value = mock_engine

    cfg = DBConfig(user="root", password="wrong", database="shop_db")
    ok, msg = run_test_connection(cfg)
    assert ok is False
    assert "Access denied" in msg


@patch("db.connection.build_engine")
def test_connection_unknown_database(mock_build_engine):
    """Verify MySQL 1049 unknown database error is categorized cleanly."""
    mock_engine = MagicMock()
    orig_exc = Exception(1049, "Unknown database 'nonexistent'")
    orig_exc.args = (1049, "Unknown database 'nonexistent'")
    mock_engine.connect.side_effect = OperationalError("Unknown database", {}, orig_exc)
    mock_build_engine.return_value = mock_engine

    cfg = DBConfig(user="root", database="nonexistent")
    ok, msg = run_test_connection(cfg)
    assert ok is False
    assert "Unknown database" in msg


@patch("db.connection.build_engine")
def test_connection_host_unreachable(mock_build_engine):
    """Verify MySQL 2003 host unreachable error is categorized cleanly."""
    mock_engine = MagicMock()
    orig_exc = Exception(2003, "Can't connect to MySQL server on '192.0.2.1'")
    orig_exc.args = (2003, "Can't connect to MySQL server on '192.0.2.1'")
    mock_engine.connect.side_effect = OperationalError("Can't connect", {}, orig_exc)
    mock_build_engine.return_value = mock_engine

    cfg = DBConfig(host="192.0.2.1", user="root")
    ok, msg = run_test_connection(cfg)
    assert ok is False
    assert "Host unreachable" in msg


@patch("db.connection.build_engine")
def test_connection_timeout(mock_build_engine):
    """Verify timeout errors are categorized cleanly."""
    mock_engine = MagicMock()
    mock_engine.connect.side_effect = OperationalError("Connection timed out", {}, None)
    mock_build_engine.return_value = mock_engine

    cfg = DBConfig(user="root", connect_timeout=3)
    ok, msg = run_test_connection(cfg)
    assert ok is False
    assert "Connection timed out" in msg


def test_close_engine_safe():
    """Verify close_engine gracefully handles None and errors."""
    close_engine(None)
    mock_engine = MagicMock()
    close_engine(mock_engine)
    mock_engine.dispose.assert_called_once()


@pytest.mark.db
def test_live_db_connection_optional():
    """Integration test against a live MySQL server if TEST_DB_URL is provided."""
    test_db_url = os.environ.get("TEST_DB_URL")
    if not test_db_url:
        pytest.skip("TEST_DB_URL not set; skipping live DB integration test.")

    import sqlalchemy

    engine = sqlalchemy.create_engine(test_db_url)
    with engine.connect() as conn:
        res = conn.execute(sqlalchemy.text("SELECT 1")).scalar()
        assert res == 1
