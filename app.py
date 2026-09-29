"""
app.py
AI-Powered SQL Query Optimization & Index Recommendation Engine
Main Streamlit Dashboard
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

from analyzer import analyze_query
from scoring import compute_score, simulate_optimized_score
from optimizer import generate_optimizations, generate_ai_insight
from recommendations import generate_index_recommendations, BEST_PRACTICES
from execution_plan import (
    generate_execution_plan, flatten_plan, get_all_nodes, plan_summary, PlanNode
)
from simulator import simulate_index_impact, impact_color
from rewrite_engine import rewrite_query
from utils.helpers import (
    format_sql,
    severity_badge,
    priority_badge,
    score_color,
    cost_color,
    complexity_color,
    build_json_report,
    build_csv_report,
    build_text_report,
    history_record,
)

from db.connection import (
    DBConfig,
    build_engine,
    test_connection as run_test_connection,
    close_engine,
)
from db.explain import run_explain
from db.schema import SchemaInfo, load_schema_from_db
from db.benchmark import compare_queries, benchmark_query


@st.cache_data(ttl=600)
def _get_cached_schema(_engine, db_name: str) -> SchemaInfo:
    """Load and cache database schema metadata for 10 minutes."""
    return load_schema_from_db(_engine, db_name)

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="MySQL Query Optimizer & Index Recommender",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Session state initialisation
# ---------------------------------------------------------------------------
if "history" not in st.session_state:
    st.session_state.history: list[dict] = []
if "last_result" not in st.session_state:
    st.session_state.last_result = None
if "db_engine" not in st.session_state:
    st.session_state["db_engine"] = None
if "db_config" not in st.session_state:
    st.session_state["db_config"] = None
if "schema_info" not in st.session_state:
    st.session_state["schema_info"] = None

# ---------------------------------------------------------------------------
# Custom CSS
# ---------------------------------------------------------------------------
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

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.markdown(
    """
<div class="main-header">
    <h1>⚡ AI-Powered SQL Query Optimizer</h1>
    <p>Index Recommendation Engine &nbsp;|&nbsp; Pattern Detection &nbsp;|&nbsp;
       Performance Scoring &nbsp;|&nbsp; Query Analysis</p>
</div>
""",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("## 🛠️ Tools")

    # Database connection status badge
    if st.session_state.get("db_engine") is not None and st.session_state.get("db_config"):
        connected_db = st.session_state["db_config"].get("database") or "MySQL"
        st.success(f"🟢 **Connected:** `{connected_db}`", icon="✅")
    else:
        st.info("⚪ **Mode:** Offline (simulated)", icon="ℹ️")

    with st.expander("🔌 MySQL 8.x Connection", expanded=st.session_state.get("db_engine") is None):
        cfg_current = st.session_state.get("db_config") or {}
        db_host = st.text_input("Host", value=cfg_current.get("host", "localhost"), key="sidebar_db_host")
        db_port = st.number_input("Port", value=int(cfg_current.get("port", 3306)), min_value=1, max_value=65535, step=1, key="sidebar_db_port")
        db_user = st.text_input("User", value=cfg_current.get("user", "root"), key="sidebar_db_user")
        db_pass = st.text_input("Password", type="password", key="sidebar_db_pass", help="Never stored in session state after connection")
        db_name = st.text_input("Database", value=cfg_current.get("database", "shop_db"), key="sidebar_db_name")

        btn_col1, btn_col2 = st.columns(2)
        with btn_col1:
            if st.button("🧪 Test", use_container_width=True):
                test_cfg = DBConfig(
                    host=db_host.strip(),
                    port=int(db_port),
                    user=db_user.strip(),
                    password=db_pass,
                    database=db_name.strip(),
                )
                ok, msg = run_test_connection(test_cfg)
                if ok:
                    st.success(msg)
                else:
                    st.error(msg)

        with btn_col2:
            if st.session_state.get("db_engine") is None:
                if st.button("🔗 Connect", type="primary", use_container_width=True):
                    connect_cfg = DBConfig(
                        host=db_host.strip(),
                        port=int(db_port),
                        user=db_user.strip(),
                        password=db_pass,
                        database=db_name.strip(),
                    )
                    ok, msg = run_test_connection(connect_cfg)
                    if ok:
                        try:
                            engine = build_engine(connect_cfg)
                            st.session_state["db_engine"] = engine
                            st.session_state["db_config"] = connect_cfg.to_display_dict()
                            st.success(f"Connected to {connect_cfg.database or 'MySQL'}!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Failed to initialize engine: {e}")
                    else:
                        st.error(msg)
            else:
                if st.button("🔌 Disconnect", use_container_width=True):
                    close_engine(st.session_state.get("db_engine"))
                    st.session_state["db_engine"] = None
                    st.session_state["db_config"] = None
                    st.session_state["schema_info"] = None
                    st.info("Disconnected from database.")
                    st.rerun()

    # Load and display schema if connected
    if st.session_state.get("db_engine") is not None and st.session_state.get("db_config"):
        curr_db = st.session_state["db_config"].get("database", "")
        if curr_db:
            try:
                schema_info = _get_cached_schema(st.session_state["db_engine"], curr_db)
                st.session_state["schema_info"] = schema_info
                with st.expander(f"📚 Schema: `{curr_db}` ({len(schema_info.tables)} tables)", expanded=False):
                    if st.button("🔄 Refresh Schema", use_container_width=True):
                        _get_cached_schema.clear()
                        st.rerun()
                    for t_name, t_meta in sorted(schema_info.tables.items()):
                        st.markdown(f"**`{t_meta.name}`** — `{t_meta.estimated_rows:,}` rows")
                        if t_meta.indexes:
                            idx_str = ", ".join(f"`{idx.name}` ({', '.join(idx.columns)})" for idx in t_meta.indexes.values())
                            st.caption(f"Indexes: {idx_str}")
            except Exception as schema_err:
                st.caption(f"⚠️ Schema load notice: {schema_err}")

    st.markdown("---")

    # Sample query picker
    st.markdown("### 📂 Load Sample Query")
    try:
        sample_df = pd.read_csv("data/sample_queries.csv")
        sample_options = ["— Select a sample —"] + sample_df["query"].tolist()
        selected_sample = st.selectbox("Choose a sample query", sample_options, label_visibility="collapsed")
    except Exception:
        selected_sample = "— Select a sample —"

    st.markdown("---")
    st.markdown("### 📊 Session Stats")
    queries_metric_placeholder = st.empty()
    avg_metric_placeholder = st.empty()

    queries_metric_placeholder.metric("Queries Analyzed", len(st.session_state.history))
    if st.session_state.history:
        avg_score = sum(h["score"] for h in st.session_state.history) / len(st.session_state.history)
        avg_metric_placeholder.metric("Avg Score", f"{avg_score:.1f} / 100")
    else:
        avg_metric_placeholder.empty()

    if st.button("🗑️ Clear History"):
        st.session_state.history = []
        st.rerun()

# ---------------------------------------------------------------------------
# Main tabs
# ---------------------------------------------------------------------------
tab_analyze, tab_history, tab_dataset, tab_practices, tab_advanced = st.tabs(
    ["🔍 Query Analyzer", "📜 Query History", "📂 Sample Dataset", "📖 Best Practices", "🔬 Advanced Analysis"]
)

# ===========================================================================
# TAB 1 — Query Analyzer
# ===========================================================================
with tab_analyze:
    # Pre-fill from sidebar sample picker
    default_query = ""
    if selected_sample != "— Select a sample —":
        default_query = selected_sample

    col_input, col_tips = st.columns([3, 1])

    with col_input:
        st.markdown('<div class="section-header">SQL Query Input</div>', unsafe_allow_html=True)
        query_input = st.text_area(
            "Paste your SQL query below",
            value=default_query,
            height=180,
            placeholder="SELECT * FROM orders WHERE customer_id = 10",
            label_visibility="collapsed",
        )

    with col_tips:
        st.markdown('<div class="section-header">Quick Tips</div>', unsafe_allow_html=True)
        st.info(
            "**Supported patterns**\n\n"
            "- `SELECT` queries\n"
            "- `JOIN` queries\n"
            "- Aggregation (`COUNT`, `SUM` …)\n"
            "- Subqueries / CTEs\n"
            "- Filtering / ordering"
        )

    analyze_btn = st.button("⚡ Analyze Query", type="primary", use_container_width=True)

    if analyze_btn and query_input.strip():
        query = query_input.strip()

        # ---- Run analysis pipeline ----
        with st.spinner("Running analysis pipeline…"):
            active_schema = st.session_state.get("schema_info")
            analysis      = analyze_query(query, schema=active_schema)
            score_result  = compute_score(analysis, schema=active_schema)
            opt_score     = simulate_optimized_score(analysis)
            optimizations = generate_optimizations(query, analysis)
            index_recs    = generate_index_recommendations(query, analysis, schema=active_schema)
            ai_insight    = generate_ai_insight(query, analysis, score_result.total)
            formatted_sql = format_sql(query)

        # Store for Advanced Analysis tab
        st.session_state.last_result = {
            "query":         query,
            "analysis":      analysis,
            "score_result":  score_result,
            "opt_score":     opt_score,
            "optimizations": optimizations,
            "index_recs":    index_recs,
            "ai_insight":    ai_insight,
        }

        # Save to history
        rec = history_record(query, analysis, score_result.total)
        rec["cost"] = score_result.cost_estimate
        st.session_state.history.append(rec)

        # Refresh sidebar stats in the same run so values don't appear static.
        queries_metric_placeholder.metric("Queries Analyzed", len(st.session_state.history))
        avg_score = sum(h["score"] for h in st.session_state.history) / len(st.session_state.history)
        avg_metric_placeholder.metric("Avg Score", f"{avg_score:.1f} / 100")

        st.markdown("---")

        # ---- Row 1: KPI metrics ----
        k1, k2, k3, k4, k5 = st.columns(5)
        with k1:
            st.markdown(
                f'<div class="score-card">'
                f'<div class="score-number" style="color:{score_color(score_result.total)}">'
                f'{score_result.total}</div>'
                f'<div class="score-label">PERFORMANCE SCORE</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
        with k2:
            color = complexity_color(analysis["complexity"])
            st.markdown(
                f'<div class="score-card">'
                f'<div class="score-number" style="color:{color};font-size:1.8rem">'
                f'{analysis["complexity"]}</div>'
                f'<div class="score-label">COMPLEXITY</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
        with k3:
            color = cost_color(score_result.cost_estimate)
            st.markdown(
                f'<div class="score-card">'
                f'<div class="score-number" style="color:{color};font-size:1.8rem">'
                f'{score_result.cost_estimate}</div>'
                f'<div class="score-label">COST ESTIMATE</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
        with k4:
            st.markdown(
                f'<div class="score-card">'
                f'<div class="score-number" style="color:#a8b2d8;font-size:1.4rem">'
                f'{score_result.rows_scanned_estimate}</div>'
                f'<div class="score-label">ROWS SCANNED</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
        with k5:
            improvement = opt_score - score_result.total
            st.markdown(
                f'<div class="score-card">'
                f'<div class="score-number" style="color:#2ecc71">+{improvement}</div>'
                f'<div class="score-label">POTENTIAL GAIN</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

        # Non-SELECT statement safety badge
        detected_stmt = analysis.get("statement_type") or analysis.get("query_type", "SELECT")
        if detected_stmt in ("INSERT", "UPDATE", "DELETE", "INSERT...SELECT"):
            st.info(
                f"🛡️ **Safety Guard: Analysis Only Mode** — Detected `{detected_stmt}` statement. "
                "Non-SELECT queries are analyzed statically and will never be executed or explained against live databases.",
                icon="🛡️",
            )

        st.markdown("---")

        # ---- Row 2: Charts ----
        ch1, ch2, ch3 = st.columns(3)

        with ch1:
            st.markdown('<div class="section-header">📊 Score Gauge</div>', unsafe_allow_html=True)
            fig_gauge = go.Figure(
                go.Indicator(
                    mode="gauge+number",
                    value=score_result.total,
                    domain={"x": [0, 1], "y": [0, 1]},
                    gauge={
                        "axis": {"range": [0, 100]},
                        "bar": {"color": score_color(score_result.total)},
                        "steps": [
                            {"range": [0, 49],  "color": "#2d1b1b"},
                            {"range": [50, 79], "color": "#2d2a1b"},
                            {"range": [80, 100],"color": "#1b2d1b"},
                        ],
                        "threshold": {
                            "line": {"color": "white", "width": 2},
                            "thickness": 0.75,
                            "value": score_result.total,
                        },
                    },
                    number={"font": {"color": score_color(score_result.total), "size": 40}},
                )
            )
            fig_gauge.update_layout(
                height=250,
                paper_bgcolor="rgba(0,0,0,0)",
                font_color="white",
                margin=dict(t=20, b=20, l=20, r=20),
            )
            st.plotly_chart(fig_gauge, use_container_width=True)

        with ch2:
            st.markdown('<div class="section-header">📈 Optimization Simulation</div>', unsafe_allow_html=True)
            fig_sim = go.Figure(
                go.Bar(
                    x=["Original", "Optimized"],
                    y=[score_result.total, opt_score],
                    marker_color=[score_color(score_result.total), "#2ecc71"],
                    text=[f"{score_result.total}", f"{opt_score}"],
                    textposition="auto",
                )
            )
            fig_sim.update_layout(
                height=250,
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font_color="white",
                yaxis=dict(range=[0, 110], gridcolor="#333"),
                xaxis=dict(gridcolor="#333"),
                margin=dict(t=20, b=20, l=20, r=20),
            )
            st.plotly_chart(fig_sim, use_container_width=True)

        with ch3:
            st.markdown('<div class="section-header">🔍 Pattern Detection</div>', unsafe_allow_html=True)
            patterns = {
                "SELECT *":      1 if analysis["select_star"] else 0,
                "Missing WHERE": 1 if not analysis["has_where"] else 0,
                "JOINs":         min(analysis["join_count"], 1),
                "Subqueries":    min(analysis["subquery_count"], 1),
                "No LIMIT":      0 if analysis["has_limit"] else 1,
            }
            fig_pat = px.bar(
                x=list(patterns.keys()),
                y=list(patterns.values()),
                color=list(patterns.values()),
                color_continuous_scale=["#2ecc71", "#e74c3c"],
                labels={"x": "Pattern", "y": "Detected"},
            )
            fig_pat.update_layout(
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
            st.plotly_chart(fig_pat, use_container_width=True)

        # ---- Row 2b: Score Breakdown Waterfall Chart ----
        st.markdown('<div class="section-header">🧮 Explainable Score Breakdown</div>', unsafe_allow_html=True)
        if score_result.breakdown:
            labels = ["Base Score"] + [b["label"] for b in score_result.breakdown]
            deltas = [100] + [b["delta"] for b in score_result.breakdown]
            measures = ["absolute"] + ["relative"] * len(score_result.breakdown)

            fig_waterfall = go.Figure(go.Waterfall(
                name="Score Walk",
                orientation="v",
                measure=measures,
                x=labels,
                textposition="outside",
                text=[f"{d:+d}" if i > 0 else f"{d}" for i, d in enumerate(deltas)],
                y=deltas,
                connector={"line": {"color": "#555"}},
                decreasing={"marker": {"color": "#e74c3c"}},
                increasing={"marker": {"color": "#2ecc71"}},
                totals={"marker": {"color": "#3498db"}},
            ))
            fig_waterfall.update_layout(
                height=320,
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font_color="white",
                yaxis=dict(gridcolor="#333", title="Performance Points"),
                xaxis=dict(gridcolor="#333", tickangle=-20),
                margin=dict(t=30, b=50, l=30, r=30),
            )
            st.plotly_chart(fig_waterfall, use_container_width=True)

            with st.expander("📋 Detailed Scoring Audit Trail"):
                breakdown_df = pd.DataFrame([
                    {
                        "Rule": b["label"],
                        "Impact": f"{b['delta']:+d} pts",
                        "Severity": b.get("severity", "MEDIUM"),
                        "Reason": b.get("reason", ""),
                    }
                    for b in score_result.breakdown
                ])
                st.dataframe(breakdown_df, use_container_width=True, hide_index=True)

        st.markdown("---")

        # ---- Row 3: Issues + Formatted SQL ----
        col_issues, col_sql = st.columns([1, 1])

        with col_issues:
            st.markdown('<div class="section-header">⚠️ Issues Detected</div>', unsafe_allow_html=True)
            if not analysis["issues"] and not analysis["warnings"]:
                st.markdown(
                    '<div class="success-card">✅ No issues detected — this query looks well-structured!</div>',
                    unsafe_allow_html=True,
                )
            else:
                for iss in analysis["issues"]:
                    st.markdown(
                        f'<div class="issue-card">'
                        f'<strong>{severity_badge(iss["severity"])}</strong>&nbsp; {iss["message"]}'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                for warn in analysis["warnings"]:
                    st.markdown(
                        f'<div class="warning-card">'
                        f'<strong>{severity_badge(warn["severity"])}</strong>&nbsp; {warn["message"]}'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

            # Score breakdown expander
            with st.expander("📋 Score Breakdown"):
                bd_df = pd.DataFrame(score_result.breakdown)
                if not bd_df.empty:
                    bd_df["delta"] = bd_df["delta"].apply(lambda d: f"+{d}" if d > 0 else str(d))
                    st.dataframe(bd_df[["label", "delta"]], use_container_width=True, hide_index=True)
                else:
                    st.write("No scoring rules applied.")

        with col_sql:
            st.markdown('<div class="section-header">🖊️ Formatted SQL</div>', unsafe_allow_html=True)
            st.code(formatted_sql, language="sql")

            st.markdown('<div class="section-header" style="margin-top:1rem">🤖 AI Insight</div>', unsafe_allow_html=True)
            st.info(ai_insight)

        st.markdown("---")

        # ---- Row 4: Optimization Recommendations ----
        st.markdown('<div class="section-header">🚀 Optimization Recommendations</div>', unsafe_allow_html=True)
        if not optimizations:
            st.success("✅ No optimization suggestions — query already follows best practices.")
        else:
            for i, opt in enumerate(optimizations, 1):
                with st.expander(f"{i}. {priority_badge(opt['priority'])}  {opt['title']}"):
                    st.markdown(f"**Description:** {opt['description']}")
                    st.code(opt["example"], language="sql")

        st.markdown("---")

        # ---- Row 5: Index Recommendations ----
        st.markdown('<div class="section-header">🗂️ Index Recommendations</div>', unsafe_allow_html=True)
        if not index_recs:
            st.info("No specific index recommendations for this query.")
        else:
            for rec in index_recs:
                with st.expander(f"📌 {rec['index_name']}  ({rec['index_type']})"):
                    st.code(rec["ddl"], language="sql")
                    st.markdown(f"**Reason:** {rec['reason']}")
                    st.success(f"⚡ Estimated Improvement: {rec['estimated_improvement']}")

        st.markdown("---")

        # ---- Row 6: Export Report ----
        st.markdown('<div class="section-header">📤 Export Analysis Report</div>', unsafe_allow_html=True)
        ex1, ex2, ex3 = st.columns(3)

        json_report = build_json_report(query, analysis, score_result, optimizations, index_recs, opt_score)
        csv_report  = build_csv_report(query, analysis, score_result, opt_score)
        text_report = build_text_report(query, analysis, score_result, optimizations, index_recs, opt_score, ai_insight)

        with ex1:
            st.download_button(
                "⬇️ Download JSON Report",
                data=json_report,
                file_name="query_report.json",
                mime="application/json",
                use_container_width=True,
            )
        with ex2:
            st.download_button(
                "⬇️ Download CSV Report",
                data=csv_report,
                file_name="query_report.csv",
                mime="text/csv",
                use_container_width=True,
            )
        with ex3:
            st.download_button(
                "⬇️ Download Text Report",
                data=text_report,
                file_name="query_report.txt",
                mime="text/plain",
                use_container_width=True,
            )

    elif analyze_btn:
        st.warning("⚠️ Please enter a SQL query before analyzing.")

# ===========================================================================
# TAB 2 — Query History
# ===========================================================================
with tab_history:
    st.markdown('<div class="section-header">📜 Query History</div>', unsafe_allow_html=True)

    if not st.session_state.history:
        st.info("No queries analyzed yet in this session. Go to **🔍 Query Analyzer** to get started.")
    else:
        hist_df = pd.DataFrame(st.session_state.history)
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
        if len(st.session_state.history) > 1:
            st.markdown("### Score Trend")
            scores = [h["score"] for h in st.session_state.history]
            fig_trend = go.Figure(
                go.Scatter(
                    y=scores,
                    mode="lines+markers+text",
                    text=[str(s) for s in scores],
                    textposition="top center",
                    line=dict(color="#e94560", width=2),
                    marker=dict(color="#e94560", size=8),
                )
            )
            fig_trend.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font_color="white",
                xaxis_title="Query #",
                yaxis_title="Score",
                yaxis=dict(range=[0, 105], gridcolor="#333"),
                xaxis=dict(gridcolor="#333"),
                height=300,
                margin=dict(t=20, b=20, l=20, r=20),
            )
            st.plotly_chart(fig_trend, use_container_width=True)

# ===========================================================================
# TAB 3 — Sample Dataset
# ===========================================================================
with tab_dataset:
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

# ===========================================================================
# TAB 4 — Best Practices
# ===========================================================================
with tab_practices:
    st.markdown('<div class="section-header">📖 SQL Performance Best Practices</div>', unsafe_allow_html=True)
    for i, tip in enumerate(BEST_PRACTICES, 1):
        st.markdown(
            f'<div class="success-card">✅ <strong>{i}.</strong> {tip}</div>',
            unsafe_allow_html=True,
        )

# ===========================================================================
# TAB 5 — Advanced Analysis
# ===========================================================================
with tab_advanced:
    st.markdown('<div class="section-header">🔬 Advanced Analysis Tools</div>', unsafe_allow_html=True)

    lr = st.session_state.last_result
    if lr is None:
        st.info(
            "**No query analyzed yet.**  "
            "Paste a SQL query in the **🔍 Query Analyzer** tab and click **⚡ Analyze Query** first."
        )
    else:
        adv_query    = lr["query"]
        adv_analysis = lr["analysis"]
        adv_score    = lr["score_result"]

        st.markdown(
            f"Showing advanced analysis for: `{adv_query[:80]}{'…' if len(adv_query)>80 else ''}`"
        )
        st.markdown("---")

        # ===================================================================
        # SECTION 1 — Execution Plan Visualizer
        # ===================================================================
        st.markdown('<div class="section-header">📋 Query Execution Plan Visualizer</div>', unsafe_allow_html=True)

        engine = st.session_state.get("db_engine")
        is_connected = engine is not None
        explain_warnings: list[str] = []
        raw_analyze_output: str | None = None
        raw_explain_json: dict | None = None
        is_real_plan = False

        adv_stmt_type = adv_analysis.get("statement_type") or adv_analysis.get("query_type", "SELECT")
        is_safe_for_live = adv_stmt_type in ("SELECT", "CTE", "UNION")

        if is_connected and is_safe_for_live:
            col_plan_mode, col_plan_opt = st.columns([3, 2])
            with col_plan_mode:
                plan_choice = st.radio(
                    "Execution Plan Source",
                    ["⚡ Real MySQL EXPLAIN (Live DB)", "🎲 Simulated Plan (Heuristic)"],
                    horizontal=True,
                    key="adv_plan_choice",
                )
            with col_plan_opt:
                run_analyze = st.checkbox(
                    "Run EXPLAIN ANALYZE (Executes query; MySQL 8.0.18+)",
                    value=False,
                    help="Executes query in a read-only transaction with a 5000ms safety timeout.",
                    key="adv_run_analyze",
                )

            if "Real" in plan_choice:
                with st.spinner("Executing EXPLAIN FORMAT=JSON on MySQL..."):
                    explain_res = run_explain(engine, adv_query, analyze=run_analyze)

                if explain_res.get("success"):
                    is_real_plan = True
                    plan_root = explain_res["plan_tree"]
                    explain_warnings = explain_res.get("warnings", [])
                    raw_analyze_output = explain_res.get("raw_analyze_text")
                    raw_explain_json = explain_res.get("raw_json")
                    st.success(f"🟢 **Live Database Plan:** Real MySQL 8.x EXPLAIN output (Server: `{explain_res.get('mysql_version')}`)", icon="✅")
                else:
                    st.warning(f"⚠️ **Real EXPLAIN Notice:** {explain_res.get('error')} — Falling back to simulated plan.")
                    plan_root = generate_execution_plan(adv_query, adv_analysis)
                    st.info("⚪ **Plan Source:** Simulated MySQL 8.x Plan (Fallback)", icon="ℹ️")
            else:
                plan_root = generate_execution_plan(adv_query, adv_analysis)
                st.info("⚪ **Plan Source:** Simulated MySQL 8.x Plan (User Selected)", icon="ℹ️")
        elif not is_safe_for_live:
            plan_root = generate_execution_plan(adv_query, adv_analysis)
            st.warning(
                f"🛡️ **Safety Guard Active:** Real MySQL EXPLAIN is disabled for `{adv_stmt_type}` statements to prevent accidental table locks or execution. Displaying simulated execution plan.",
                icon="🔒",
            )
        else:
            plan_root = generate_execution_plan(adv_query, adv_analysis)
            st.info("⚪ **Plan Source:** Simulated MySQL 8.x Plan (Connect to MySQL in sidebar for real EXPLAIN)", icon="ℹ️")

        if explain_warnings:
            st.markdown("##### ⚠️ Live Execution Plan Optimizer Findings")
            for w in explain_warnings:
                st.warning(f"• {w}")

        summary = plan_summary(plan_root)

        # KPI row for plan
        pc1, pc2, pc3, pc4 = st.columns(4)
        with pc1:
            color = cost_color(summary["cost_category"])
            st.markdown(
                f'<div class="score-card"><div class="score-number" style="color:{color};font-size:1.6rem">'
                f'{summary["cost_category"]}</div><div class="score-label">PLAN COST {"(REAL)" if is_real_plan else "(EST.)"}</div></div>',
                unsafe_allow_html=True,
            )
        with pc2:
            st.markdown(
                f'<div class="score-card"><div class="score-number" style="color:#a8b2d8;font-size:1.4rem">'
                f'{summary["estimated_rows"]:,}</div><div class="score-label">ROWS EXAMINED</div></div>',
                unsafe_allow_html=True,
            )
        with pc3:
            icon = "🟢" if summary["has_index_scan"] else "🔴"
            label = "ref / range / eq_ref" if summary["has_index_scan"] else "ALL (Table Scan)"
            st.markdown(
                f'<div class="score-card"><div class="score-number" style="font-size:1.4rem">'
                f'{icon} {label}</div><div class="score-label">PRIMARY ACCESS TYPE</div></div>',
                unsafe_allow_html=True,
            )
        with pc4:
            st.markdown(
                f'<div class="score-card"><div class="score-number" style="color:#a8b2d8;font-size:1.4rem">'
                f'{summary["total_nodes"]}</div><div class="score-label">PLAN NODES</div></div>',
                unsafe_allow_html=True,
            )

        st.markdown("")

        # ---- Plotly tree visualization ----
        all_plan_nodes = get_all_nodes(plan_root)

        # Assign positions: leaves get sequential x, parents center over children
        positions: dict[int, tuple[float, float]] = {}
        edges_chart: list[tuple[int, int]] = []
        _leaf_counter = [0]

        def _assign_pos(node: PlanNode, depth: int) -> None:
            if not node.children:
                positions[id(node)] = (_leaf_counter[0], -depth)
                _leaf_counter[0] += 1
            else:
                child_xs = []
                for child in node.children:
                    _assign_pos(child, depth + 1)
                    child_xs.append(positions[id(child)][0])
                    edges_chart.append((id(node), id(child)))
                positions[id(node)] = (sum(child_xs) / len(child_xs), -depth)

        _assign_pos(plan_root, 0)

        _NODE_COLORS = {
            "ALL":             "#e74c3c",
            "REF":             "#2ecc71",
            "EQ_REF":          "#2ecc71",
            "CONST":           "#1abc9c",
            "RANGE":           "#27ae60",
            "INDEX":           "#f39c12",
            "ref":             "#2ecc71",
            "range":           "#27ae60",
            "eq_ref":          "#2ecc71",
            "const":           "#1abc9c",
            "index":           "#f39c12",
            "Ordering":        "#8e44ad",
            "Grouping":        "#16a085",
            "Filter":          "#3498db",
            "filesort":        "#8e44ad",
            "temporary":       "#d35400",
            "Hash Join":       "#e67e22",
            "Nested Loop":     "#d35400",
            "Aggregate":       "#16a085",
            "Limit":           "#7f8c8d",
            "Subquery":        "#c0392b",
            "Result":          "#2980b9",
            # Compatibility fallbacks
            "Seq Scan":        "#e74c3c",
            "Index Scan":      "#2ecc71",
            "Sort":            "#8e44ad",
        }

        # Build edge traces
        edge_x: list = []
        edge_y: list = []
        for pid, cid in edges_chart:
            px_val, py_val = positions[pid]
            cx_val, cy_val = positions[cid]
            # Curved edge via midpoint
            edge_x += [px_val, (px_val + cx_val) / 2, cx_val, None]
            edge_y += [py_val, (py_val + cy_val) / 2, cy_val, None]

        node_x     = [positions[id(n)][0] for n in all_plan_nodes]
        node_y     = [positions[id(n)][1] for n in all_plan_nodes]
        node_label = [n.node_type for n in all_plan_nodes]
        node_hover = [
            f"<b>{n.node_type}</b><br>"
            f"{n.description}<br>"
            f"Est. Rows: {n.estimated_rows:,}<br>"
            f"Cost: {n.cost_label}"
            for n in all_plan_nodes
        ]
        node_colors = [_NODE_COLORS.get(n.node_type, "#7f8c8d") for n in all_plan_nodes]

        fig_plan = go.Figure()
        if edge_x:
            fig_plan.add_trace(go.Scatter(
                x=edge_x, y=edge_y,
                mode="lines",
                line=dict(color="#555", width=2),
                hoverinfo="none",
                showlegend=False,
            ))
        fig_plan.add_trace(go.Scatter(
            x=node_x, y=node_y,
            mode="markers+text",
            marker=dict(
                size=55,
                color=node_colors,
                line=dict(color="white", width=2),
                symbol="circle",
            ),
            text=node_label,
            textposition="middle center",
            textfont=dict(color="white", size=9.5),
            hovertext=node_hover,
            hoverinfo="text",
            showlegend=False,
        ))
        fig_plan.update_layout(
            height=max(350, len(set(positions[id(n)][1] for n in all_plan_nodes)) * 100),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font_color="white",
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            margin=dict(t=30, b=30, l=30, r=30),
        )
        st.plotly_chart(fig_plan, use_container_width=True)

        # ---- Plan node table ----
        with st.expander("📄 Execution Plan Detail Table"):
            plan_df = pd.DataFrame(flatten_plan(plan_root))
            st.dataframe(plan_df, use_container_width=True, hide_index=True)

        if raw_analyze_output:
            with st.expander("⏱️ EXPLAIN ANALYZE Execution Output"):
                st.code(raw_analyze_output, language="text")

        if raw_explain_json:
            with st.expander("📋 Raw EXPLAIN FORMAT=JSON"):
                st.json(raw_explain_json)

        # Legend
        st.caption(
            "🔴 ALL (Full Table Scan - expensive)  "
            "🟢 ref / range (Index Lookup - efficient)  "
            "🟡 index (Covering Index Scan)  "
            "🟠 Hash Join (MySQL 8.0.18+)  "
            "🔶 Nested Loop  "
            "🔷 filesort (Using filesort)  "
            "🟤 temporary (Using temporary)  "
            "⬛ Limit"
        )

        st.markdown("---")

        # ===================================================================
        # SECTION 2 — Index Impact Simulator
        # ===================================================================
        st.markdown('<div class="section-header">⚡ Index Impact Simulator</div>', unsafe_allow_html=True)
        st.caption("Projects query performance before and after applying the recommended indexes.")

        impact = simulate_index_impact(adv_query, adv_analysis, adv_score)

        imp_col = impact_color(impact["impact_level"])

        # Before / After metric cards
        ia1, ia2, ia3 = st.columns(3)
        with ia1:
            st.markdown("#### Before Indexes")
            st.markdown(
                f'<div class="score-card" style="border-color:#e74c3c">'
                f'<div class="score-number" style="color:{score_color(impact["before_score"])}">{impact["before_score"]}</div>'
                f'<div class="score-label">SCORE</div></div>',
                unsafe_allow_html=True,
            )
            st.markdown(f"**Cost:** `{impact['before_cost']}`")
            st.markdown(f"**Rows Scanned:** `{impact['before_rows']:,}`")
            st.markdown(f"**Est. Time:** `{impact['before_time_ms']:,} ms`")

        with ia2:
            st.markdown("#### After Indexes")
            st.markdown(
                f'<div class="score-card" style="border-color:#2ecc71">'
                f'<div class="score-number" style="color:{score_color(impact["after_score"])}">{impact["after_score"]}</div>'
                f'<div class="score-label">SCORE</div></div>',
                unsafe_allow_html=True,
            )
            st.markdown(f"**Cost:** `{impact['after_cost']}`")
            st.markdown(f"**Rows Scanned:** `{impact['after_rows']:,}`")
            st.markdown(f"**Est. Time:** `{impact['after_time_ms']:,} ms`")

        with ia3:
            st.markdown("#### Performance Gain")
            st.markdown(
                f'<div class="score-card" style="border-color:{imp_col}">'
                f'<div class="score-number" style="color:{imp_col}">+{impact["score_improvement"]}</div>'
                f'<div class="score-label">SCORE GAIN</div></div>',
                unsafe_allow_html=True,
            )
            st.markdown(f"**Impact Level:** `{impact['impact_level']}`")
            st.markdown(f"**Speedup:** `{impact['speedup_label']}`")
            st.markdown(f"**Rows Reduced:** `{impact['rows_reduction_pct']}%`")

        st.markdown("")

        # Before vs After bar chart
        fig_impact = go.Figure()
        metrics      = ["Score", "Est. Time (ms)"]
        before_vals  = [impact["before_score"], min(impact["before_time_ms"], 2000)]
        after_vals   = [impact["after_score"],  min(impact["after_time_ms"],  2000)]

        fig_impact.add_trace(go.Bar(
            name="Before Indexes",
            x=metrics,
            y=before_vals,
            marker_color="#e74c3c",
            text=[str(v) for v in before_vals],
            textposition="auto",
        ))
        fig_impact.add_trace(go.Bar(
            name="After Indexes",
            x=metrics,
            y=after_vals,
            marker_color="#2ecc71",
            text=[str(v) for v in after_vals],
            textposition="auto",
        ))
        fig_impact.update_layout(
            barmode="group",
            height=300,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font_color="white",
            yaxis=dict(gridcolor="#333"),
            xaxis=dict(gridcolor="#333"),
            legend=dict(bgcolor="rgba(0,0,0,0)"),
            margin=dict(t=20, b=20, l=20, r=20),
        )
        st.plotly_chart(fig_impact, use_container_width=True)

        if impact["indexed_columns"]:
            st.info(
                f"📌 Columns to index: **{', '.join(impact['indexed_columns'])}**  →  "
                f"estimated **{impact['speedup_label']}** after indexing."
            )

        st.markdown("---")

        # ===================================================================
        # SECTION 3 — Query Rewrite Engine
        # ===================================================================
        st.markdown('<div class="section-header">✏️ Query Rewrite Engine</div>', unsafe_allow_html=True)
        st.caption("Automatically rewrites inefficient SQL patterns into optimized equivalents.")

        rewrite = rewrite_query(adv_query, adv_analysis)

        rw1, rw2 = st.columns(2)
        with rw1:
            st.markdown("**Original Query**")
            st.code(rewrite["original"], language="sql")
        with rw2:
            st.markdown("**Rewritten Query**")
            st.code(rewrite["rewritten"], language="sql")

        st.markdown("")

        if rewrite["is_changed"]:
            st.markdown("**Transformations Applied:**")
            for change in rewrite["changes"]:
                st.markdown(
                    f'<div class="success-card">✅ {change}</div>',
                    unsafe_allow_html=True,
                )
            if rewrite["rewrite_score_est"] > 0:
                st.success(
                    f"⚡ Applying these rewrites could add approximately "
                    f"**+{rewrite['rewrite_score_est']} points** to the performance score."
                )
        else:
            st.success("✅ No automatic rewrites needed — query is already well-structured.")

        # ===================================================================
        # SECTION 4 — Live Query Execution Benchmarking
        # ===================================================================
        st.markdown("---")
        st.markdown('<div class="section-header">⏱️ Live Query Execution Benchmarking</div>', unsafe_allow_html=True)
        st.caption("Measure actual wall-clock execution times (min, median, p95, mean) on your live MySQL database.")

        if engine is None:
            st.info("⚪ **Offline Mode:** Connect to a MySQL database in the sidebar to benchmark queries live.", icon="ℹ️")
        elif not is_safe_for_live:
            st.warning(
                f"🛡️ **Safety Guard Active:** Live benchmarking is strictly disabled for `{adv_stmt_type}` statements to prevent accidental table locks or data mutations.",
                icon="🔒",
            )
        else:
            default_compare_sql = rewrite["rewritten"] if rewrite.get("is_changed") else adv_query
            bc_col1, bc_col2 = st.columns([1, 1])
            with bc_col1:
                bm_runs = st.slider("Timed Runs", min_value=3, max_value=15, value=5, step=1, key="bm_runs")
            with bc_col2:
                bm_warmup = st.slider("Warmup Runs", min_value=0, max_value=3, value=1, step=1, key="bm_warmup", help="Populates InnoDB buffer pool pages before measuring steady-state performance.")

            compare_input = st.text_area(
                "Query to compare against original (e.g. rewritten query)",
                value=default_compare_sql,
                height=120,
                key="bm_compare_input",
            )

            if st.button("🚀 Run Live Benchmark", type="primary", use_container_width=True):
                with st.spinner(f"Running benchmark ({bm_warmup} warmup + {bm_runs} iterations on live MySQL)..."):
                    comp_res = compare_queries(engine, adv_query, compare_input, runs=bm_runs, warmup=bm_warmup)

                if comp_res.original.success and comp_res.rewritten.success:
                    bk1, bk2, bk3, bk4 = st.columns(4)
                    with bk1:
                        st.markdown(
                            f'<div class="score-card"><div class="score-number" style="color:#e74c3c;font-size:1.6rem">'
                            f'{comp_res.original.median_ms:.2f} ms</div><div class="score-label">ORIGINAL (MEDIAN)</div></div>',
                            unsafe_allow_html=True,
                        )
                    with bk2:
                        st.markdown(
                            f'<div class="score-card"><div class="score-number" style="color:#2ecc71;font-size:1.6rem">'
                            f'{comp_res.rewritten.median_ms:.2f} ms</div><div class="score-label">REWRITTEN (MEDIAN)</div></div>',
                            unsafe_allow_html=True,
                        )
                    with bk3:
                        speed_color = "#2ecc71" if comp_res.speedup_factor >= 1.0 else "#e74c3c"
                        st.markdown(
                            f'<div class="score-card"><div class="score-number" style="color:{speed_color};font-size:1.6rem">'
                            f'{comp_res.speedup_factor:.2f}×</div><div class="score-label">MEASURED SPEEDUP</div></div>',
                            unsafe_allow_html=True,
                        )
                    with bk4:
                        row_status = "✅ Match" if comp_res.row_counts_match else "⚠️ Mismatch"
                        st.markdown(
                            f'<div class="score-card"><div class="score-number" style="color:#a8b2d8;font-size:1.4rem">'
                            f'{row_status}</div><div class="score-label">{comp_res.original.rows_returned} vs {comp_res.rewritten.rows_returned} ROWS</div></div>',
                            unsafe_allow_html=True,
                        )

                    if comp_res.warning:
                        st.warning(comp_res.warning)

                    # Comparison Bar Chart
                    fig_bm = go.Figure()
                    metrics_names = ["Min Latency", "Median Latency", "95th Percentile (p95)", "Mean Latency"]
                    orig_vals = [comp_res.original.min_ms, comp_res.original.median_ms, comp_res.original.p95_ms, comp_res.original.mean_ms]
                    rew_vals = [comp_res.rewritten.min_ms, comp_res.rewritten.median_ms, comp_res.rewritten.p95_ms, comp_res.rewritten.mean_ms]

                    fig_bm.add_trace(go.Bar(name="Original Query", x=metrics_names, y=orig_vals, marker_color="#e74c3c"))
                    fig_bm.add_trace(go.Bar(name="Rewritten Query", x=metrics_names, y=rew_vals, marker_color="#2ecc71"))
                    fig_bm.update_layout(
                        title="Query Latency Comparison (Milliseconds - Lower is Better)",
                        barmode="group",
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                        font_color="white",
                        yaxis=dict(title="Latency (ms)", gridcolor="#333"),
                        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                    )
                    st.plotly_chart(fig_bm, use_container_width=True)

                    st.info(f"ℹ️ **Buffer Pool Caveat:** {comp_res.buffer_cache_notice}")
                else:
                    err_msg = comp_res.original.error or comp_res.rewritten.error or "Benchmark failed."
                    st.error(f"Benchmark error: {err_msg}")

            st.caption(
                "📌 **Index Testing Note:** In MySQL, DDL statements (`CREATE INDEX`) cause implicit commits and cannot be run inside a temporary rollback transaction. "
                "To benchmark index recommendations, apply the recommended DDL on a staging database."
            )

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------
st.markdown("---")
st.markdown(
    "<div style='text-align:center;color:#666;font-size:0.8rem'>"
    "Rule-Based SQL Query Analyzer & Index Recommender &nbsp;|&nbsp; "
    "Target: MySQL 8.x &nbsp;|&nbsp; Streamlit + Plotly + SQLAlchemy + PyMySQL"
    "</div>",
    unsafe_allow_html=True,
)
