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
# Main Application Tabs with Global Error Boundary
# ---------------------------------------------------------------------------
try:
    tab_analyze, tab_history, tab_dataset, tab_practices, tab_advanced = st.tabs(
        [
            "🔍 Query Analyzer",
            "📜 Query History",
            "📂 Sample Dataset",
            "📖 Best Practices",
            "🔬 Advanced Analysis",
        ]
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

except Exception as unhandled_err:
    from utils.validation import generate_error_reference

    err_ref = generate_error_reference()
    import logging

    logging.getLogger("optimizer").error(
        "Unhandled exception [ref: %s]: %s", err_ref, unhandled_err, exc_info=True
    )
    st.error(
        f"⚠️ Something went wrong (Incident Reference: `{err_ref}`). The error details have been safely logged."
    )
    with st.expander("🛠️ Troubleshooting Tips"):
        st.write("1. Check if the database host and credentials in the sidebar are reachable.")
        st.write("2. Make sure your query follows standard MySQL 8.x syntax.")
        st.write(
            "3. Inspect `logs/app.log` for diagnostic traceback using your incident reference code."
        )

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
