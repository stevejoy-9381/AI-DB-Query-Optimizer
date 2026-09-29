"""
ui/state.py
Centralized Streamlit session state keys, constants, and initialization helpers.
Prevents typo-related session state bugs across UI modules.
"""

from __future__ import annotations

import streamlit as st

# Centralized session state keys
KEY_HISTORY = "history"
KEY_LAST_RESULT = "last_result"
KEY_DB_ENGINE = "db_engine"
KEY_DB_CONFIG = "db_config"
KEY_SCHEMA_INFO = "schema_info"
KEY_REWRITE_OPT_IN_LIMIT = "rewrite_opt_in_limit"
KEY_SIDEBAR_QUERY = "sidebar_query"


def init_session_state() -> None:
    """Initialize all required session state variables with default values."""
    if KEY_HISTORY not in st.session_state:
        st.session_state[KEY_HISTORY] = []
    if KEY_LAST_RESULT not in st.session_state:
        st.session_state[KEY_LAST_RESULT] = None
    if KEY_DB_ENGINE not in st.session_state:
        st.session_state[KEY_DB_ENGINE] = None
    if KEY_DB_CONFIG not in st.session_state:
        st.session_state[KEY_DB_CONFIG] = None
    if KEY_SCHEMA_INFO not in st.session_state:
        st.session_state[KEY_SCHEMA_INFO] = None
    if KEY_REWRITE_OPT_IN_LIMIT not in st.session_state:
        st.session_state[KEY_REWRITE_OPT_IN_LIMIT] = False
