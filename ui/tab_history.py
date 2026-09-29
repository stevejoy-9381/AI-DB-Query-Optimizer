"""ui/tab_history.py
Tab 2: Query History — Searchable persistent SQLite logs, score trends,
two-query side-by-side comparison, and CSV/JSON export.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from history_store import HistoryStore
from ui.charts import create_trendline_chart
from utils.diff import generate_side_by_side_diff


def render_tab_history() -> None:
    """Render Tab 2: Query History UI with search, comparison, and persistent SQLite backend."""
    st.markdown('<div class="section-header">📜 Persistent Query History</div>', unsafe_allow_html=True)
    st.caption("All queries are persisted locally in `data/history.db` and survive browser refreshes and server restarts.")

    store = HistoryStore()
    total_records = store.count()

    if total_records == 0:
        st.info("No queries recorded yet. Analyze a query in **🔍 Query Analyzer** to start tracking history.")
        return

    # 1. Search & Filter Bar
    f_col1, f_col2, f_col3 = st.columns([3, 2, 2])
    with f_col1:
        search_query = st.text_input("🔍 Search queries", placeholder="e.g. customers, JOIN, order_id", key="hist_search")
    with f_col2:
        score_range = st.slider("Score Range", min_value=0, max_value=100, value=(0, 100), key="hist_score_range")
    with f_col3:
        page_size = st.selectbox("Page Size", options=[10, 25, 50], index=0, key="hist_page_size")

    # Fetch filtered records
    filtered_count = store.count(search=search_query, min_score=score_range[0], max_score=score_range[1])
    records = store.list(
        search=search_query,
        min_score=score_range[0],
        max_score=score_range[1],
        limit=int(page_size),
        offset=0,
    )

    st.markdown(f"**Showing {len(records)} of {filtered_count} matching runs** (Total in DB: {total_records})")

    if not records:
        st.warning("No historical queries match your search and filter criteria.")
        return

    # 2. Main History Dataframe
    df = pd.DataFrame(records)
    display_cols = ["id", "created_at", "statement_type", "score", "complexity", "cost", "mode", "query"]
    renamed_df = df[display_cols].rename(columns={
        "id": "ID",
        "created_at": "Timestamp",
        "statement_type": "Type",
        "score": "Score",
        "complexity": "Complexity",
        "cost": "Cost",
        "mode": "Mode",
        "query": "SQL Query",
    })
    st.dataframe(renamed_df, use_container_width=True, hide_index=True)

    # 3. Score Trendline Chart
    chart_data = [{"timestamp": r["created_at"], "score": r["score"], "query_snippet": r["query"][:40]} for r in reversed(records)]
    if len(chart_data) > 1:
        st.markdown("### 📈 Score Trend Across History")
        st.plotly_chart(create_trendline_chart(chart_data), use_container_width=True)

    st.markdown("---")

    # 4. Compare Two Historical Queries
    st.markdown("### ⚖️ Compare Two Queries")
    st.caption("Select any two query IDs from history to inspect side-by-side metric deltas and SQL diff.")
    id_options = [r["id"] for r in records]
    c_col1, c_col2 = st.columns(2)
    with c_col1:
        id_a = st.selectbox("Query A (Baseline)", options=id_options, index=0 if len(id_options) > 0 else 0, key="cmp_a")
    with c_col2:
        default_b_idx = 1 if len(id_options) > 1 else 0
        id_b = st.selectbox("Query B (Comparison)", options=id_options, index=default_b_idx, key="cmp_b")

    if id_a and id_b:
        rec_a = store.get(int(id_a))
        rec_b = store.get(int(id_b))

        if rec_a and rec_b:
            m1, m2, m3, m4 = st.columns(4)
            with m1:
                score_delta = rec_b["score"] - rec_a["score"]
                st.metric("Score Delta", f"{rec_b['score']} / 100", delta=f"{score_delta:+d} pts")
            with m2:
                st.metric("Statement Type", f"{rec_a['statement_type']} ➔ {rec_b['statement_type']}")
            with m3:
                st.metric("Complexity", f"{rec_a['complexity']} ➔ {rec_b['complexity']}")
            with m4:
                cost_delta = round(rec_b["cost"] - rec_a["cost"], 2)
                st.metric("Cost Estimate", f"{rec_b['cost']}", delta=f"{cost_delta:+.2f}")

            # SQL Diff
            st.markdown("##### Side-by-Side SQL Comparison")
            diff = generate_side_by_side_diff(rec_a["query"], rec_b["query"])
            diff_col1, diff_col2 = st.columns(2)
            with diff_col1:
                st.caption(f"**Query A (ID: {id_a})**")
                st.code(rec_a["query"], language="sql")
            with diff_col2:
                st.caption(f"**Query B (ID: {id_b})**")
                st.code(rec_b["query"], language="sql")
            if diff.has_changes:
                st.info(f"Modifications detected: +{diff.lines_added} lines, -{diff.lines_removed} lines, ~{diff.lines_modified} modified.")
            else:
                st.success("Queries are syntactically identical.")

    st.markdown("---")

    # 5. Export and Clear History
    exp_col1, exp_col2, exp_col3 = st.columns([2, 2, 3])
    with exp_col1:
        st.download_button(
            "📥 Export History (CSV)",
            data=store.export_csv(),
            file_name="query_history.csv",
            mime="text/csv",
            use_container_width=True,
        )
    with exp_col2:
        st.download_button(
            "📥 Export History (JSON)",
            data=store.export_json(),
            file_name="query_history.json",
            mime="application/json",
            use_container_width=True,
        )
    with exp_col3:
        confirm_clear = st.checkbox("Confirm database wipe", key="confirm_clear_history_chk")
        if st.button("🗑️ Clear All Persistent History", disabled=not confirm_clear, use_container_width=True):
            store.clear_all()
            st.success("History database cleared.")
            st.rerun()
