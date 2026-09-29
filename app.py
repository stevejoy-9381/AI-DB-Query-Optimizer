"""
app.py
Entry point for MySQL Query Optimizer & Index Recommender.
Modular Streamlit dashboard for query analysis, index recommendations, AST heuristics, and live benchmarking.
"""

from __future__ import annotations

import streamlit as st

from ui import (
    init_session_state,
    render_header,
    render_sidebar,
    render_styles,
    render_tab_advanced,
    render_tab_analyzer,
    render_tab_dataset,
    render_tab_history,
    render_tab_practices,
)

# ---------------------------------------------------------------------------
# Streamlit Application Configuration
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="MySQL Query Optimizer & Index Recommender",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Initialization & Layout
# ---------------------------------------------------------------------------
init_session_state()
render_styles()
render_header()

# Render interactive sidebar
sidebar_state = render_sidebar()

# ---------------------------------------------------------------------------
# Main Application Tabs
# ---------------------------------------------------------------------------
tab_analyze, tab_history, tab_dataset, tab_practices, tab_advanced = st.tabs(
    ["🔍 Query Analyzer", "📜 Query History", "📂 Sample Dataset", "📖 Best Practices", "🔬 Advanced Analysis"]
)

with tab_analyze:
    render_tab_analyzer(sidebar_state)

with tab_history:
    render_tab_history()

with tab_dataset:
    render_tab_dataset()

with tab_practices:
    render_tab_practices()

with tab_advanced:
    render_tab_advanced()

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------
st.markdown("---")
st.markdown(
    "<div style='text-align:center;color:#666;font-size:0.8rem'>"
    "Rule-Based SQL Query Optimizer & Index Recommender &nbsp;|&nbsp; "
    "Target: MySQL 8.x &nbsp;|&nbsp; Streamlit + Plotly + SQLAlchemy + PyMySQL"
    "</div>",
    unsafe_allow_html=True,
)
