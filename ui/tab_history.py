"""
ui/tab_history.py
Tab 2: Query History — Session query logs, score trends, and performance audits.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ui.charts import create_trendline_chart
from ui.state import KEY_HISTORY


def render_tab_history() -> None:
    """Render Tab 2: Query History UI."""
    st.markdown('<div class="section-header">📜 Query History</div>', unsafe_allow_html=True)

    history = st.session_state.get(KEY_HISTORY, [])
    if not history:
        st.info("No queries analyzed yet in this session. Go to **🔍 Query Analyzer** to get started.")
        return

    hist_df = pd.DataFrame(history)
    hist_df = hist_df.rename(columns={
        "timestamp":     "Time",
        "query_snippet": "Query",
        "score":         "Score",
        "complexity":    "Complexity",
        "cost":          "Cost",
        "issues":        "Issues",
    })

    st.dataframe(hist_df, use_container_width=True, hide_index=True)

    # Score trend line chart
    if len(history) > 1:
        st.markdown("### Score Trend Across Session")
        st.plotly_chart(create_trendline_chart(history), use_container_width=True)
