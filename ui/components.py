"""
ui/components.py
Reusable HTML and CSS UI components, custom styles, and header elements.
"""

from __future__ import annotations

import streamlit as st

from utils.helpers import score_color


def render_styles() -> None:
    """Inject custom CSS stylesheet into the Streamlit app."""
    st.markdown(
        """
<style>
    /* Main header gradient */
    .main-header {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
        padding: 2rem;
        border-radius: 12px;
        margin-bottom: 1.5rem;
        text-align: center;
    }
    .main-header h1 { color: #e94560; margin: 0; font-size: 2.2rem; }
    .main-header p  { color: #a8b2d8; margin: 0.5rem 0 0; font-size: 1rem; }

    /* Score card */
    .score-card {
        background: #1e1e2e;
        border-radius: 10px;
        padding: 1.2rem;
        text-align: center;
        border: 1px solid #333;
    }
    .score-number { font-size: 3rem; font-weight: 800; color: #ffffff; }
    .score-label  { color: #a8b2d8; font-size: 0.85rem; letter-spacing: 1px; }

    /* Issue / warning cards */
    .issue-card {
        background: #2d1b1b;
        border-left: 4px solid #e74c3c;
        border-radius: 6px;
        padding: 0.75rem 1rem;
        margin-bottom: 0.5rem;
        color: #f5b5b5 !important;
    }
    .warning-card {
        background: #2d2a1b;
        border-left: 4px solid #f39c12;
        border-radius: 6px;
        padding: 0.75rem 1rem;
        margin-bottom: 0.5rem;
        color: #f5dfa0 !important;
    }
    .success-card {
        background: #1b2d1b;
        border-left: 4px solid #2ecc71;
        border-radius: 6px;
        padding: 0.75rem 1rem;
        margin-bottom: 0.5rem;
        color: #a8f0b5 !important;
    }

    /* Section header */
    .section-header {
        font-size: 1.1rem;
        font-weight: 700;
        color: #e94560;
        border-bottom: 2px solid #e94560;
        padding-bottom: 0.3rem;
        margin-bottom: 1rem;
    }
</style>
""",
        unsafe_allow_html=True,
    )


def render_header() -> None:
    """Render the application header with honest title and capabilities."""
    st.markdown(
        """
<div class="main-header">
    <h1>⚡ MySQL Query Optimizer & Index Recommender</h1>
    <p>Deterministic Rule Engine &nbsp;|&nbsp; AST Pattern Detection &nbsp;|&nbsp;
       Index Advice &nbsp;|&nbsp; Optional LLM Assistant</p>
</div>
""",
        unsafe_allow_html=True,
    )


def render_score_card(score: int, label: str = "PERFORMANCE SCORE") -> None:
    """Render a styled KPI score card."""
    color = score_color(score)
    st.markdown(
        f'<div class="score-card">'
        f'<div class="score-number" style="color:{color}">{score}</div>'
        f'<div class="score-label">{label}</div>'
        f"</div>",
        unsafe_allow_html=True,
    )
