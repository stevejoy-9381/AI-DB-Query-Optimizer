"""
ui package
Modularized presentation layer for the Streamlit dashboard.
"""

from ui.components import render_header, render_score_card, render_styles
from ui.sidebar import SidebarState, render_sidebar
from ui.state import (
    KEY_DB_CONFIG,
    KEY_DB_ENGINE,
    KEY_HISTORY,
    KEY_LAST_RESULT,
    KEY_SCHEMA_INFO,
    init_session_state,
)
from ui.tab_advanced import render_tab_advanced
from ui.tab_analyzer import render_tab_analyzer
from ui.tab_dataset import render_tab_dataset
from ui.tab_history import render_tab_history
from ui.tab_practices import render_tab_practices

__all__ = [
    "init_session_state",
    "render_styles",
    "render_header",
    "render_score_card",
    "render_sidebar",
    "SidebarState",
    "render_tab_analyzer",
    "render_tab_history",
    "render_tab_dataset",
    "render_tab_practices",
    "render_tab_advanced",
    "KEY_HISTORY",
    "KEY_LAST_RESULT",
    "KEY_DB_ENGINE",
    "KEY_DB_CONFIG",
    "KEY_SCHEMA_INFO",
]
