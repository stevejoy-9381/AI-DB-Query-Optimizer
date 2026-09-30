"""
ui/charts.py
Extracted Plotly chart generators for performance score gauges,
waterfall breakdowns, pattern detection, and history trends.
"""

from __future__ import annotations

import plotly.express as px
import plotly.graph_objects as go

from utils.helpers import score_color


def create_score_gauge(score: int) -> go.Figure:
    """Create a Plotly gauge indicator for performance score (0-100)."""
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=score,
            domain={"x": [0, 1], "y": [0, 1]},
            title={"text": "Query Health", "font": {"size": 16, "color": "#a8b2d8"}},
            number={"font": {"size": 36, "color": score_color(score)}},
            gauge={
                "axis": {"range": [0, 100], "tickwidth": 1, "tickcolor": "#555"},
                "bar": {"color": score_color(score), "thickness": 0.25},
                "bgcolor": "rgba(255,255,255,0.05)",
                "steps": [
                    {"range": [0, 50], "color": "rgba(231,76,60,0.2)"},
                    {"range": [50, 80], "color": "rgba(243,156,18,0.2)"},
                    {"range": [80, 100], "color": "rgba(46,204,113,0.2)"},
                ],
                "threshold": {
                    "line": {"color": score_color(score), "width": 4},
                    "thickness": 0.75,
                    "value": score,
                },
            },
        )
    )
    fig.update_layout(
        height=250,
        paper_bgcolor="rgba(0,0,0,0)",
        font_color="white",
        margin=dict(t=20, b=20, l=20, r=20),
    )
    return fig


def create_optimization_sim_bar(original_score: int, opt_score: int) -> go.Figure:
    """Create a before/after bar comparison of query scores."""
    fig = go.Figure(
        go.Bar(
            x=["Original", "Optimized"],
            y=[original_score, opt_score],
            marker_color=[score_color(original_score), "#2ecc71"],
            text=[f"{original_score}", f"{opt_score}"],
            textposition="auto",
        )
    )
    fig.update_layout(
        height=250,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="white",
        yaxis=dict(range=[0, 110], gridcolor="#333"),
        xaxis=dict(gridcolor="#333"),
        margin=dict(t=20, b=20, l=20, r=20),
    )
    return fig


def create_pattern_detection_bar(analysis: dict) -> go.Figure:
    """Create a detected patterns indicator bar chart."""
    patterns = {
        "SELECT *": 1 if analysis.get("select_star") else 0,
        "Missing WHERE": 1 if not analysis.get("has_where") else 0,
        "JOINs": min(analysis.get("join_count", 0), 1),
        "Subqueries": min(analysis.get("subquery_count", 0), 1),
        "No LIMIT": 0 if analysis.get("has_limit") else 1,
    }
    fig = px.bar(
        x=list(patterns.keys()),
        y=list(patterns.values()),
        color=list(patterns.values()),
        color_continuous_scale=["#2ecc71", "#e74c3c"],
        labels={"x": "Pattern", "y": "Detected"},
    )
    fig.update_layout(
        height=250,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="white",
        yaxis=dict(range=[0, 1.5], gridcolor="#333", tickvals=[0, 1], ticktext=["No", "Yes"]),
        xaxis=dict(gridcolor="#333"),
        showlegend=False,
        coloraxis_showscale=False,
        margin=dict(t=20, b=20, l=20, r=20),
    )
    return fig


def create_waterfall_chart(score_result) -> go.Figure:
    """Create a waterfall chart visualizing additive bonuses and subtractive penalties."""
    measures = ["absolute"]
    x_labels = ["Base Score"]
    y_values = [100]

    for item in score_result.breakdown:
        measures.append("relative")
        x_labels.append(item["label"][:24])  # truncate for readability
        y_values.append(item["delta"])

    measures.append("total")
    x_labels.append("Final Score")
    y_values.append(score_result.total)

    fig = go.Figure(
        go.Waterfall(
            name="Score Waterfall",
            orientation="v",
            measure=measures,
            x=x_labels,
            textposition="outside",
            text=[
                f"{v:+d}" if i > 0 and i < len(y_values) - 1 else f"{v}"
                for i, v in enumerate(y_values)
            ],
            y=y_values,
            connector={"line": {"color": "#666"}},
            decreasing={"marker": {"color": "#e74c3c"}},
            increasing={"marker": {"color": "#2ecc71"}},
            totals={"marker": {"color": score_color(score_result.total)}},
        )
    )
    fig.update_layout(
        height=320,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="white",
        yaxis=dict(range=[0, 115], gridcolor="#333", title="Score"),
        xaxis=dict(gridcolor="#333", tickangle=-30),
        margin=dict(t=20, b=20, l=20, r=20),
    )
    return fig


def create_trendline_chart(history: list[dict]) -> go.Figure:
    """Create score trend chart over time across analyzed queries."""
    indices = list(range(1, len(history) + 1))
    scores = [h["score"] for h in history]
    queries = [(h.get("query") or h.get("query_snippet") or "Query")[:35] + "…" for h in history]

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=indices,
            y=scores,
            mode="lines+markers",
            name="Score",
            line=dict(color="#3498db", width=2),
            marker=dict(size=8, color=[score_color(s) for s in scores]),
            text=queries,
            hovertemplate="Query #%{x}<br>Score: %{y}/100<br>%{text}<extra></extra>",
        )
    )
    fig.add_hline(y=80, line_dash="dash", line_color="#2ecc71", annotation_text="Good (80)")
    fig.add_hline(y=50, line_dash="dash", line_color="#f39c12", annotation_text="Moderate (50)")

    fig.update_layout(
        height=300,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="white",
        yaxis=dict(range=[0, 105], gridcolor="#333", title="Score"),
        xaxis=dict(gridcolor="#333", title="Query Number", dtick=1),
        margin=dict(t=20, b=20, l=20, r=20),
    )
    return fig
