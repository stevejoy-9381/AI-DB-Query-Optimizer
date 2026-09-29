"""
tests/test_app_smoke.py
Streamlit AppTest smoke test suite verifying that the refactored modular app.py
loads cleanly, executes query analysis end-to-end, and displays performance scores.
"""

from __future__ import annotations

import pytest
from streamlit.testing.v1 import AppTest


def test_app_loads_without_exceptions():
    """Verify that app.py loads cleanly with all tabs, sidebar, and styles."""
    at = AppTest.from_file("app.py", default_timeout=20)
    at.run()
    assert not at.exception, f"App crashed on load: {at.exception}"
    assert len(at.tabs) == 5


def test_app_runs_query_and_displays_score():
    """Verify that entering a query and clicking Analyze Query produces results without error."""
    at = AppTest.from_file("app.py", default_timeout=20)
    at.run()
    assert not at.exception

    # Find the main query input text area
    query_inputs = [t for t in at.text_area if t.key == "main_query_input"]
    assert len(query_inputs) >= 1
    query_inputs[0].input("SELECT id, name FROM users WHERE id = 10;").run()

    # Find and click the analyze button
    buttons = [b for b in at.button if b.key == "btn_analyze_query"]
    assert len(buttons) >= 1
    buttons[0].click().run()

    assert not at.exception, f"App crashed during query analysis: {at.exception}"

    # Verify that score and metric cards are rendered
    markdown_texts = " ".join(m.value for m in at.markdown)
    assert "PERFORMANCE SCORE" in markdown_texts
    assert "COMPLEXITY" in markdown_texts
    assert "Issues Detected" in markdown_texts or "No issues detected" in markdown_texts
