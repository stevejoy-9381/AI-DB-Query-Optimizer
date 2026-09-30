"""tests/test_diff.py
Unit tests for side-by-side SQL diff visualizer and comparison engine.
Verifies format normalization, line-by-line diff alignment, change statistics,
and HTML rendering.
"""

from utils.diff import (
    format_sqlglot_pretty,
    generate_side_by_side_diff,
    render_diff_html,
)


def test_format_sqlglot_pretty():
    raw = "select id,name from users where id=10"
    formatted = format_sqlglot_pretty(raw)
    assert "SELECT" in formatted
    assert "FROM" in formatted
    assert "WHERE" in formatted


def test_diff_identical_queries():
    q = "SELECT id, name FROM customers WHERE id = 10;"
    diff = generate_side_by_side_diff(q, q)

    assert diff.has_changes is False
    assert diff.lines_added == 0
    assert diff.lines_removed == 0
    assert diff.lines_modified == 0
    assert len(diff.left_lines) == len(diff.right_lines)
    assert all(line.tag == "equal" for line in diff.left_lines)
    assert all(r.tag == "equal" for r in diff.right_lines)


def test_diff_with_modifications():
    orig = "SELECT * FROM customers WHERE UPPER(name) = 'ALICE';"
    rew = "SELECT id, name FROM customers WHERE name = 'alice';"
    diff = generate_side_by_side_diff(orig, rew)

    assert diff.has_changes is True
    assert len(diff.left_lines) == len(diff.right_lines)
    # At least one line modified or replaced
    tags = {line.tag for line in diff.left_lines} | {r.tag for r in diff.right_lines}
    assert "replace" in tags or "delete" in tags or "insert" in tags


def test_diff_with_limit_addition():
    orig = "SELECT id, name FROM customers;"
    rew = "SELECT id, name FROM customers LIMIT 100;"
    diff = generate_side_by_side_diff(orig, rew)

    assert diff.has_changes is True
    assert len(diff.left_lines) == len(diff.right_lines)
    assert diff.lines_added > 0 or diff.lines_modified > 0


def test_render_diff_html():
    orig = "SELECT * FROM orders;"
    rew = "SELECT id, total FROM orders LIMIT 100;"
    diff = generate_side_by_side_diff(orig, rew)

    html = render_diff_html(diff)
    assert isinstance(html, str)
    assert "Original SQL" in html
    assert "Rewritten SQL" in html
    assert "monospace" in html
