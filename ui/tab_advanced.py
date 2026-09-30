"""
ui/tab_advanced.py
Tab 5: Advanced Analysis — Execution plan visualizer (real/simulated),
Index impact simulator, Query rewrite engine with side-by-side diff, and live benchmarking.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from db.benchmark import compare_queries
from db.explain import run_explain
from execution_plan import (
    PlanNode,
    flatten_plan,
    generate_execution_plan,
    get_all_nodes,
    plan_summary,
)
from rewrite_engine import rewrite_query
from rewrite_validation import validate_rewrite_data
from simulator import impact_color, simulate_index_impact
from ui.state import KEY_DB_ENGINE, KEY_LAST_RESULT
from utils.diff import generate_side_by_side_diff, render_diff_html
from utils.helpers import cost_color, score_color

_NODE_COLORS = {
    "ALL": "#e74c3c",
    "REF": "#2ecc71",
    "EQ_REF": "#2ecc71",
    "CONST": "#1abc9c",
    "RANGE": "#27ae60",
    "INDEX": "#f39c12",
    "ref": "#2ecc71",
    "range": "#27ae60",
    "eq_ref": "#2ecc71",
    "const": "#1abc9c",
    "index": "#f39c12",
    "Ordering": "#8e44ad",
    "Grouping": "#16a085",
    "Filter": "#3498db",
    "filesort": "#8e44ad",
    "temporary": "#d35400",
    "Hash Join": "#e67e22",
    "Nested Loop": "#d35400",
    "Aggregate": "#16a085",
    "Limit": "#7f8c8d",
    "Subquery": "#c0392b",
    "Result": "#2980b9",
    "Seq Scan": "#e74c3c",
    "Index Scan": "#2ecc71",
    "Sort": "#8e44ad",
}


def render_tab_advanced() -> None:
    """Render Tab 5: Advanced Analysis UI."""
    st.markdown(
        '<div class="section-header">🔬 Advanced Analysis Tools</div>', unsafe_allow_html=True
    )

    lr = st.session_state.get(KEY_LAST_RESULT)
    if lr is None:
        st.info(
            "**No query analyzed yet.**  "
            "Paste a SQL query in the **🔍 Query Analyzer** tab and click **⚡ Analyze Query** first."
        )
        return

    adv_query = lr["query"]
    adv_analysis = lr["analysis"]
    adv_score = lr["score_result"]

    st.markdown(
        f"Showing advanced analysis for: `{adv_query[:80]}{'…' if len(adv_query) > 80 else ''}`"
    )
    st.markdown("---")

    # ===================================================================
    # SECTION 1 — Execution Plan Visualizer
    # ===================================================================
    st.markdown(
        '<div class="section-header">📋 Query Execution Plan Visualizer</div>',
        unsafe_allow_html=True,
    )

    engine = st.session_state.get(KEY_DB_ENGINE)
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
                st.success(
                    f"🟢 **Live Database Plan:** Real MySQL 8.x EXPLAIN output (Server: `{explain_res.get('mysql_version')}`)",
                    icon="✅",
                )
            else:
                st.warning(
                    f"⚠️ **Real EXPLAIN Notice:** {explain_res.get('error')} — Falling back to simulated plan."
                )
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
        st.info(
            "⚪ **Plan Source:** Simulated MySQL 8.x Plan (Connect to MySQL in sidebar for real EXPLAIN)",
            icon="ℹ️",
        )

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

    edge_x: list = []
    edge_y: list = []
    for pid, cid in edges_chart:
        px_val, py_val = positions[pid]
        cx_val, cy_val = positions[cid]
        edge_x += [px_val, (px_val + cx_val) / 2, cx_val, None]
        edge_y += [py_val, (py_val + cy_val) / 2, cy_val, None]

    node_x = [positions[id(n)][0] for n in all_plan_nodes]
    node_y = [positions[id(n)][1] for n in all_plan_nodes]
    node_label = [n.node_type for n in all_plan_nodes]
    node_hover = [
        f"<b>{n.node_type}</b><br>{n.description}<br>Est. Rows: {n.estimated_rows:,}<br>Cost: {n.cost_label}"
        for n in all_plan_nodes
    ]
    node_colors = [_NODE_COLORS.get(n.node_type, "#7f8c8d") for n in all_plan_nodes]

    fig_plan = go.Figure()
    if edge_x:
        fig_plan.add_trace(
            go.Scatter(
                x=edge_x,
                y=edge_y,
                mode="lines",
                line=dict(color="#555", width=2),
                hoverinfo="none",
                showlegend=False,
            )
        )
    fig_plan.add_trace(
        go.Scatter(
            x=node_x,
            y=node_y,
            mode="markers+text",
            marker=dict(
                size=55, color=node_colors, line=dict(color="white", width=2), symbol="circle"
            ),
            text=node_label,
            textposition="middle center",
            textfont=dict(color="white", size=9.5),
            hovertext=node_hover,
            hoverinfo="text",
            showlegend=False,
        )
    )
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

    with st.expander("📄 Execution Plan Detail Table"):
        plan_df = pd.DataFrame(flatten_plan(plan_root))
        st.dataframe(plan_df, use_container_width=True, hide_index=True)

    if raw_analyze_output:
        with st.expander("⏱️ EXPLAIN ANALYZE Execution Output"):
            st.code(raw_analyze_output, language="text")

    if raw_explain_json:
        with st.expander("📋 Raw EXPLAIN FORMAT=JSON"):
            st.json(raw_explain_json)

    st.caption(
        "🔴 ALL (Full Table Scan)  🟢 ref / range (Index Seek)  🟡 index (Covering Scan)  "
        "🟠 Hash Join  🔶 Nested Loop  🔷 filesort  🟤 temporary  ⬛ Limit"
    )

    st.markdown("---")

    # ===================================================================
    # SECTION 2 — Index Impact Simulator
    # ===================================================================
    st.markdown(
        '<div class="section-header">⚡ Index Impact Simulator</div>', unsafe_allow_html=True
    )
    st.caption("Projects query performance before and after applying the recommended indexes.")

    impact = simulate_index_impact(adv_query, adv_analysis, adv_score)
    imp_col = impact_color(impact["impact_level"])

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

    fig_impact = go.Figure()
    metrics = ["Score", "Est. Time (ms)"]
    before_vals = [impact["before_score"], min(impact["before_time_ms"], 2000)]
    after_vals = [impact["after_score"], min(impact["after_time_ms"], 2000)]

    fig_impact.add_trace(
        go.Bar(
            name="Before Indexes",
            x=metrics,
            y=before_vals,
            marker_color="#e74c3c",
            text=[str(v) for v in before_vals],
            textposition="auto",
        )
    )
    fig_impact.add_trace(
        go.Bar(
            name="After Indexes",
            x=metrics,
            y=after_vals,
            marker_color="#2ecc71",
            text=[str(v) for v in after_vals],
            textposition="auto",
        )
    )
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
            f"📌 Columns to index: **{', '.join(impact['indexed_columns'])}**  →  estimated **{impact['speedup_label']}** after indexing."
        )

    st.markdown("---")

    # ===================================================================
    # SECTION 3 — Query Rewrite Engine
    # ===================================================================
    st.markdown('<div class="section-header">✏️ Query Rewrite Engine</div>', unsafe_allow_html=True)
    st.caption("Automatically rewrites inefficient SQL patterns into optimized equivalents.")

    col_rw_opts, _ = st.columns([2, 1])
    with col_rw_opts:
        allow_limit = st.checkbox(
            "Allow LIMIT injection (caps result set to 100 rows)",
            value=True,
            help="When enabled, injects LIMIT 100 on unbounded SELECT queries. Uncheck to maintain identical result cardinality.",
            key="adv_allow_limit",
        )

    rewrite = rewrite_query(adv_query, adv_analysis, allow_limit_injection=allow_limit)

    val = rewrite.get("validation", {})
    val_level = val.get("level", "Verified equivalent")
    val_color = val.get("badge_color", "#2ecc71")
    val_msg = val.get("message", "")

    st.markdown(
        f'**Semantic Trust Level:** <span style="background:{val_color};color:white;padding:3px 10px;border-radius:12px;font-weight:600;font-size:0.85rem;">{val_level}</span> &nbsp; <small style="color:#aaa;">{val_msg}</small>',
        unsafe_allow_html=True,
    )
    st.markdown("")

    if rewrite["is_changed"]:
        diff_obj = generate_side_by_side_diff(rewrite["original"], rewrite["rewritten"])
        st.markdown("##### 🔀 Side-by-Side Query Comparison")
        st.markdown(render_diff_html(diff_obj), unsafe_allow_html=True)

        st.markdown("##### ⚙️ Applied Rewrite Transformations")
        for change in rewrite["changes"]:
            st.markdown(f'<div class="success-card">✅ {change}</div>', unsafe_allow_html=True)

        if rewrite["rewrite_score_est"] > 0:
            st.success(
                f"⚡ Applying these rewrites could add approximately **+{rewrite['rewrite_score_est']} points** to the performance score."
            )

        st.markdown("##### 📋 Copy Final Optimized SQL")
        st.code(rewrite["rewritten"], language="sql")

        dl_col1, _ = st.columns([1, 3])
        with dl_col1:
            st.download_button(
                label="💾 Download .sql File",
                data=rewrite["rewritten"],
                file_name="optimized_query.sql",
                mime="text/plain",
                use_container_width=True,
            )

        if engine is not None and is_safe_for_live:
            st.markdown("---")
            if st.button("🧪 Validate Rewrite on Live Sample Data", key="btn_validate_data"):
                with st.spinner(
                    "Executing original and rewritten queries with row cap to verify multiset equivalence..."
                ):
                    data_val = validate_rewrite_data(
                        engine, adv_query, rewrite["rewritten"], row_cap=100
                    )
                st.markdown(
                    f'**Empirical Data Validation:** <span style="background:{data_val.badge_color};color:white;padding:3px 10px;border-radius:12px;font-weight:600;font-size:0.85rem;">{data_val.level}</span>',
                    unsafe_allow_html=True,
                )
                st.info(data_val.message)
                for detail in data_val.details:
                    st.caption(f"• {detail}")
    else:
        st.success("✅ **Nothing to rewrite:** Your query is already well-structured and optimal!")
        st.code(rewrite["original"], language="sql")

    # ===================================================================
    # SECTION 4 — Live Query Execution Benchmarking
    # ===================================================================
    st.markdown("---")
    st.markdown(
        '<div class="section-header">⏱️ Live Query Execution Benchmarking</div>',
        unsafe_allow_html=True,
    )
    st.caption(
        "Measure actual wall-clock execution times (min, median, p95, mean) on your live MySQL database."
    )

    if engine is None:
        st.info(
            "⚪ **Offline Mode:** Connect to a MySQL database in the sidebar to benchmark queries live.",
            icon="ℹ️",
        )
    elif not is_safe_for_live:
        st.warning(
            f"🛡️ **Safety Guard Active:** Live benchmarking is strictly disabled for `{adv_stmt_type}` statements to prevent accidental table locks or data mutations.",
            icon="🔒",
        )
    else:
        default_compare_sql = rewrite["rewritten"] if rewrite.get("is_changed") else adv_query
        bc_col1, bc_col2 = st.columns([1, 1])
        with bc_col1:
            bm_runs = st.slider(
                "Timed Runs", min_value=3, max_value=15, value=5, step=1, key="bm_runs"
            )
        with bc_col2:
            bm_warmup = st.slider(
                "Warmup Runs", min_value=0, max_value=3, value=1, step=1, key="bm_warmup"
            )

        compare_input = st.text_area(
            "Query to compare against original (e.g. rewritten query)",
            value=default_compare_sql,
            height=120,
            key="bm_compare_input",
        )

        if st.button("🚀 Run Live Benchmark", type="primary", use_container_width=True):
            with st.spinner(
                f"Running benchmark ({bm_warmup} warmup + {bm_runs} iterations on live MySQL)..."
            ):
                comp_res = compare_queries(
                    engine, adv_query, compare_input, runs=bm_runs, warmup=bm_warmup
                )

            if comp_res.original.success and comp_res.rewritten.success:
                bk1, bk2, bk3, bk4 = st.columns(4)
                with bk1:
                    st.markdown(
                        f'<div class="score-card"><div class="score-number" style="color:#e74c3c;font-size:1.6rem">{comp_res.original.median_ms:.2f} ms</div><div class="score-label">ORIGINAL (MEDIAN)</div></div>',
                        unsafe_allow_html=True,
                    )
                with bk2:
                    st.markdown(
                        f'<div class="score-card"><div class="score-number" style="color:#2ecc71;font-size:1.6rem">{comp_res.rewritten.median_ms:.2f} ms</div><div class="score-label">REWRITTEN (MEDIAN)</div></div>',
                        unsafe_allow_html=True,
                    )
                with bk3:
                    speed_color = "#2ecc71" if comp_res.speedup_factor >= 1.0 else "#e74c3c"
                    st.markdown(
                        f'<div class="score-card"><div class="score-number" style="color:{speed_color};font-size:1.6rem">{comp_res.speedup_factor:.2f}×</div><div class="score-label">MEASURED SPEEDUP</div></div>',
                        unsafe_allow_html=True,
                    )
                with bk4:
                    row_status = "✅ Match" if comp_res.row_counts_match else "⚠️ Mismatch"
                    st.markdown(
                        f'<div class="score-card"><div class="score-number" style="color:#a8b2d8;font-size:1.4rem">{row_status}</div><div class="score-label">{comp_res.original.rows_returned} vs {comp_res.rewritten.rows_returned} ROWS</div></div>',
                        unsafe_allow_html=True,
                    )

                if comp_res.warning:
                    st.warning(comp_res.warning)

                fig_bm = go.Figure()
                metrics_names = [
                    "Min Latency",
                    "Median Latency",
                    "95th Percentile (p95)",
                    "Mean Latency",
                ]
                orig_vals = [
                    comp_res.original.min_ms,
                    comp_res.original.median_ms,
                    comp_res.original.p95_ms,
                    comp_res.original.mean_ms,
                ]
                rew_vals = [
                    comp_res.rewritten.min_ms,
                    comp_res.rewritten.median_ms,
                    comp_res.rewritten.p95_ms,
                    comp_res.rewritten.mean_ms,
                ]

                fig_bm.add_trace(
                    go.Bar(
                        name="Original Query", x=metrics_names, y=orig_vals, marker_color="#e74c3c"
                    )
                )
                fig_bm.add_trace(
                    go.Bar(
                        name="Rewritten Query", x=metrics_names, y=rew_vals, marker_color="#2ecc71"
                    )
                )
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
