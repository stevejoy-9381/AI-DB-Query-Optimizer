"""tests/test_validation.py
Unit tests for query validation and error message formatting.
"""

from utils.validation import format_connection_error, generate_error_reference, validate_sql_input


def test_validate_empty_query():
    valid, msg = validate_sql_input("")
    assert valid is False
    assert "empty" in msg.lower()

    valid, msg = validate_sql_input("   \n\t  ")
    assert valid is False
    assert "empty" in msg.lower()


def test_validate_comments_only():
    valid, msg = validate_sql_input("-- Just a comment\n-- another comment")
    assert valid is False
    assert "comments" in msg.lower()

    valid, msg = validate_sql_input("/* Multi-line\n   comment */")
    assert valid is False
    assert "comments" in msg.lower()


def test_validate_max_length_exceeded():
    long_query = "SELECT " + "a" * 20500
    valid, msg = validate_sql_input(long_query, max_length=20000)
    assert valid is False
    assert "maximum permitted length" in msg.lower()


def test_validate_null_bytes():
    bad_query = "SELECT * FROM users WHERE name = 'abc\x00def';"
    valid, msg = validate_sql_input(bad_query)
    assert valid is False
    assert "null byte" in msg.lower() or "non-printable" in msg.lower()


def test_validate_multiple_statements():
    multi_sql = "SELECT * FROM customers; DROP TABLE orders;"
    valid, msg = validate_sql_input(multi_sql)
    assert valid is False
    assert "multiple sql statements" in msg.lower()


def test_validate_syntax_error():
    syntax_err_sql = "SELECT FROM WHERE;"
    valid, msg = validate_sql_input(syntax_err_sql)
    assert valid is False
    assert "syntax error" in msg.lower()


def test_validate_clean_query():
    valid_sql = "SELECT id, name FROM customers WHERE active = 1 ORDER BY id DESC LIMIT 10;"
    valid, msg = validate_sql_input(valid_sql)
    assert valid is True
    assert msg is None


def test_format_connection_error():
    # Access Denied
    err = format_connection_error(Exception("Access denied for user 'root'@'localhost' (using password: YES)"))
    assert "Authentication Failed" in err["title"]
    assert "password" in err["detail"].lower()

    # Unknown Database
    err = format_connection_error(Exception("(1049, \"Unknown database 'nonexistent_db'\")"))
    assert "Database Not Found" in err["title"]

    # Host unreachable
    err = format_connection_error(Exception("(2003, \"Can't connect to MySQL server on '127.0.0.1:3306'\")"))
    assert "Host Unreachable" in err["title"]

    # Timeout
    err = format_connection_error(Exception("Connection timed out after 5 seconds"))
    assert "Timed Out" in err["title"]


def test_generate_error_reference():
    ref1 = generate_error_reference()
    ref2 = generate_error_reference()
    assert len(ref1) == 8
    assert ref1 != ref2
