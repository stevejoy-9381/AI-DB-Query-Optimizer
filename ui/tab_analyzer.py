"""
ui/tab_analyzer.py
Tab 1: Query Analyzer — Input, Static & AST Analysis, Scoring, Charts,
Optimization Strategies, Ranked Index Advice, and Report Export.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from ai import get_ai_insight
from analyzer import analyze_query
from optimizer import generate_optimizations
from recommendations import (
    detect_redundant_indexes,
    generate_index_recommendations,
)
from scoring import compute_score, simulate_optimized_score
from ui.charts import (
    create_optimization_sim_bar,
    create_pattern_detection_bar,
    create_score_gauge,
    create_waterfall_chart,
)
from ui.components import render_score_card
from ui.sidebar import SidebarState
from ui.state import KEY_HISTORY, KEY_LAST_RESULT
from utils.helpers import (
    build_csv_report,
    build_json_report,
    build_text_report,
    complexity_color,
    cost_color,
    format_sql,
    history_record,
    priority_badge,
    severity_badge,
)


def render_tab_analyzer(sidebar_state: SidebarState) -> None:
    """Render Tab 1: Query Analyzer UI."""
    default_query = ""
    if sidebar_state.selected_sample != "— Select a sample —":
        default_query = sidebar_state.selected_sample

    if not sidebar_state.is_connected:
        st.info("ℹ️ **Demo Mode**: Offline estimates only (not connected to a live database). Schema and index advice use sample `shop_db`.")

    col_input, col_tips = st.columns([3, 1])

    with col_input:
        st.markdown('<div class="section-header">SQL Query Input</div>', unsafe_allow_html=True)
        query_input = st.text_area(
            "Paste your SQL query below",
            value=default_query,
            height=180,
            placeholder="SELECT * FROM orders WHERE customer_id = 10",
            label_visibility="collapsed",
            key="main_query_input",
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

    analyze_btn = st.button("⚡ Analyze Query", type="primary", use_container_width=True, key="btn_analyze_query")

    if analyze_btn and query_input.strip():
        query = query_input.strip()

        with st.spinner("Running analysis pipeline…"):
            active_schema = sidebar_state.active_schema
            analysis      = analyze_query(query, schema=active_schema)
            score_result  = compute_score(analysis, schema=active_schema)
            opt_score     = simulate_optimized_score(analysis)
            optimizations = generate_optimizations(query, analysis)
            index_recs    = generate_index_recommendations(query, analysis, schema=active_schema)
            ai_data       = get_ai_insight(
                query=query,
                analysis=analysis,
                score=score_result.total,
                schema=active_schema,
                enabled=sidebar_state.enable_ai,
            )
            ai_insight    = ai_data["insight"]
            ai_source     = ai_data["source"]
            ai_suggested  = ai_data.get("suggested_query")
            ai_rewrite_status = ai_data.get("rewrite_status")
            formatted_sql = format_sql(query)

        # Store for Advanced Analysis tab
        st.session_state[KEY_LAST_RESULT] = {
            "query":             query,
            "analysis":          analysis,
            "score_result":      score_result,
            "opt_score":         opt_score,
            "optimizations":     optimizations,
            "index_recs":        index_recs,
            "ai_insight":        ai_insight,
            "ai_source":         ai_source,
            "ai_suggested":      ai_suggested,
            "ai_rewrite_status": ai_rewrite_status,
        }

        # Save to session history
        rec = history_record(query, analysis, score_result.total)
        rec["cost"] = score_result.cost_estimate
        st.session_state[KEY_HISTORY].append(rec)

        # Save to persistent SQLite history if enabled
        if st.session_state.get("save_history_locally", True):
            try:
                from history_store import HistoryStore
                store = HistoryStore()
                store.add(
                    query=query,
                    score=score_result.total,
                    report_dict={
                        "score": score_result.total,
                        "complexity": analysis.get("complexity", "O(n)"),
                        "cost": score_result.cost_estimate,
                        "statement_type": analysis.get("statement_type", "SELECT"),
                        "findings_count": len(analysis.get("issues", [])),
                        "optimizations_count": len(optimizations),
                        "index_recs_count": len(index_recs),
                        "ai_source": ai_source,
                    },
                    statement_type=analysis.get("statement_type", "SELECT"),
                    complexity=analysis.get("complexity", "O(n)"),
                    cost=score_result.cost_estimate,
                    dialect="mysql",
                    mode="live" if sidebar_state.is_connected else "offline",
                    source_badges=ai_source,
                )
            except Exception as hist_err:
                import logging
                logging.getLogger(__name__).warning("Failed to persist history record: %s", hist_err)

        st.markdown("---")

        # ---- Row 1: KPI metrics ----
        k1, k2, k3, k4, k5 = st.columns(5)
        with k1:
            render_score_card(score_result.total, "PERFORMANCE SCORE")
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
                f'<div class="score-label">EST. COST</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
        with k4:
            st.markdown(
                f'<div class="score-card">'
                f'<div class="score-number" style="color:#3498db;font-size:1.8rem">'
                f'{score_result.rows_scanned_estimate}</div>'
                f'<div class="score-label">EST. ROWS SCANNED</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
        with k5:
            issue_count = len(analysis["issues"]) + len(analysis["warnings"])
            color = "#2ecc71" if issue_count == 0 else ("#f39c12" if issue_count <= 2 else "#e74c3c")
            st.markdown(
                f'<div class="score-card">'
                f'<div class="score-number" style="color:{color}">{issue_count}</div>'
                f'<div class="score-label">ISSUES DETECTED</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

        st.markdown("---")

        # ---- Row 2: Charts ----
        ch1, ch2, ch3 = st.columns(3)
        with ch1:
            st.markdown('<div class="section-header">📊 Score Gauge</div>', unsafe_allow_html=True)
            st.plotly_chart(create_score_gauge(score_result.total), use_container_width=True)

        with ch2:
            st.markdown('<div class="section-header">📈 Optimization Simulation</div>', unsafe_allow_html=True)
            st.plotly_chart(create_optimization_sim_bar(score_result.total, opt_score), use_container_width=True)

        with ch3:
            st.markdown('<div class="section-header">🔍 Pattern Detection</div>', unsafe_allow_html=True)
            st.plotly_chart(create_pattern_detection_bar(analysis), use_container_width=True)

        # ---- Row 2b: Score Breakdown Waterfall Chart ----
        st.markdown('<div class="section-header">🧮 Explainable Score Breakdown</div>', unsafe_allow_html=True)
        if score_result.breakdown:
            st.plotly_chart(create_waterfall_chart(score_result), use_container_width=True)
        else:
            st.info("No rule adjustments were applied to the base score of 100.")

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

            st.markdown(
                f'<div class="section-header" style="margin-top:1rem">'
                f'💡 Performance Insight <span style="font-size:0.75rem; background:#222; border:1px solid #444; padding:2px 8px; border-radius:4px; margin-left:8px; vertical-align:middle;">🏷️ {ai_source}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
            st.info(ai_insight)
            if ai_suggested:
                badge = ai_rewrite_status or "AI suggestion (unverified)"
                badge_color = "#2ecc71" if "Verified" in badge else "#f39c12"
                st.markdown(
                    f"**Suggested Rewrite** <span style='font-size:0.75rem; background:{badge_color}; color:#000; padding:2px 6px; border-radius:3px; font-weight:bold;'>{badge}</span>",
                    unsafe_allow_html=True,
                )
                st.code(ai_suggested, language="sql")

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
            top_n = index_recs[:2]
            rest = index_recs[2:]

            def _render_rec_card(rec):
                with st.expander(
                    f"📌 Rank #{rec.get('rank', 1)}: {rec['index_name']} ({rec['index_type']})",
                    expanded=(rec.get("rank", 1) == 1),
                ):
                    st.code(rec["ddl"], language="sql")
                    st.markdown(f"**Reason:** {rec['reason']}")
                    if rec.get("column_order_explanation"):
                        st.info(f"💡 **Column Ordering Rule:** {rec['column_order_explanation']}")
                    if rec.get("estimated_size"):
                        st.markdown(f"💾 **Estimated Index Size:** `{rec['estimated_size']}`")
                    if rec.get("trade_offs"):
                        st.markdown(f"⚖️ **Trade-offs:** {rec['trade_offs']}")
                    st.success(f"⚡ Estimated Improvement: {rec['estimated_improvement']}")

            for rec in top_n:
                _render_rec_card(rec)

            if rest:
                with st.expander(f"🔍 Advanced / Additional Index Options ({len(rest)} more)"):
                    for rec in rest:
                        _render_rec_card(rec)

        # Redundant Index Audit (if live schema available)
        if active_schema:
            redundant_indexes = detect_redundant_indexes(active_schema)
            if redundant_indexes:
                with st.expander(f"⚠️ Redundant & Duplicate Index Audit ({len(redundant_indexes)} found in schema)"):
                    st.caption(
                        "The MySQL leftmost prefix rule makes sub-indexes redundant when a wider composite index already exists. "
                        "Review suggestions below to eliminate write overhead and save disk space."
                    )
                    for red in redundant_indexes:
                        st.code(red["ddl"], language="sql")
                        st.markdown(f"**Reason:** {red['reason']}")
                        st.warning(f"⚠️ {red['warning']}")

        st.markdown("---")

        # ---- Row 6: Export Report ----
        st.markdown('<div class="section-header">📤 Export Analysis Report</div>', unsafe_allow_html=True)
        ex1, ex2, ex3 = st.columns(3)

        json_report = build_json_report(query, analysis, score_result, optimizations, index_recs, opt_score, insight_text=ai_insight, insight_source=ai_source)
        csv_report  = build_csv_report(query, analysis, score_result, opt_score, insight_source=ai_source)
        text_report = build_text_report(query, analysis, score_result, optimizations, index_recs, opt_score, ai_insight, insight_source=ai_source)

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
