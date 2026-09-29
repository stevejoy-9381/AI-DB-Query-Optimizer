"""
ui/tab_dataset.py
Tab 3: Sample Dataset — Interactive query library, category distribution, and complexity breakdown.
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st


def render_tab_dataset() -> None:
    """Render Tab 3: Sample Dataset UI."""
    st.markdown('<div class="section-header">📂 Sample Query Dataset</div>', unsafe_allow_html=True)
    try:
        df = pd.read_csv("data/sample_queries.csv")
        st.dataframe(df, use_container_width=True, hide_index=True)

        # Category distribution chart
        if "category" in df.columns:
            cat_counts = df["category"].value_counts().reset_index()
            cat_counts.columns = ["Category", "Count"]
            fig_cat = px.pie(
                cat_counts,
                names="Category",
                values="Count",
                color_discrete_map={
                    "Good":         "#2ecc71",
                    "Moderate":     "#f39c12",
                    "Anti-pattern": "#e74c3c",
                },
            )
            fig_cat.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                font_color="white",
                height=320,
                margin=dict(t=20, b=20, l=20, r=20),
            )
            st.plotly_chart(fig_cat, use_container_width=True)

    except FileNotFoundError:
        st.error("Sample dataset not found at `data/sample_queries.csv`.")
