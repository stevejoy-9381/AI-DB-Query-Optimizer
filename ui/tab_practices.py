"""
ui/tab_practices.py
Tab 4: Best Practices — 12 curated MySQL performance and indexing guidelines.
"""

from __future__ import annotations

import streamlit as st
from recommendations import BEST_PRACTICES


def render_tab_practices() -> None:
    """Render Tab 4: SQL Performance Best Practices UI."""
    st.markdown('<div class="section-header">📖 SQL Performance Best Practices</div>', unsafe_allow_html=True)
    for i, tip in enumerate(BEST_PRACTICES, 1):
        st.markdown(
            f'<div class="success-card">✅ <strong>{i}.</strong> {tip}</div>',
            unsafe_allow_html=True,
        )
