"""
ui/sidebar.py
Sidebar configuration, live database connection manager, schema viewer,
sample query picker, session metrics, and AI assistant toggle.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import pandas as pd
import streamlit as st

from db.connection import DBConfig, build_engine, close_engine, test_connection
from db.schema import SchemaInfo, load_schema_from_db
from ui.state import (
    KEY_DB_CONFIG,
    KEY_DB_ENGINE,
    KEY_HISTORY,
    KEY_SCHEMA_INFO,
)

logger = logging.getLogger(__name__)


@st.cache_resource(ttl=300)
def _get_cached_schema(_engine, db_name: str) -> SchemaInfo:
    """Introspect and cache schema metadata."""
    return load_schema_from_db(_engine, db_name)


@dataclass
class SidebarState:
    """State values returned from the sidebar for use in tabs."""
    selected_sample: str
    enable_ai: bool
    active_schema: SchemaInfo | None


def render_sidebar() -> SidebarState:
    """Render the sidebar UI controls and return current sidebar state."""
    with st.sidebar:
        st.markdown("## 🛠️ Tools")

        # Database Connection Section
        with st.expander("🔌 Database Connection", expanded=False):
            st.caption("Connect to MySQL 8.x for live EXPLAIN, schema metadata, and benchmarking.")
            db_host = st.text_input("Host", value="localhost", key="sb_db_host")
            db_port = st.number_input("Port", value=3306, min_value=1, max_value=65535, step=1, key="sb_db_port")
            db_user = st.text_input("User", value="root", key="sb_db_user")
            db_pass = st.text_input("Password", type="password", key="sb_db_pass")
            db_name = st.text_input("Database", value="shop", key="sb_db_name")

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
                    ok, msg = test_connection(test_cfg)
                    if ok:
                        st.success(msg)
                    else:
                        st.error(msg)

            with btn_col2:
                if st.session_state.get(KEY_DB_ENGINE) is None:
                    if st.button("🔗 Connect", type="primary", use_container_width=True):
                        connect_cfg = DBConfig(
                            host=db_host.strip(),
                            port=int(db_port),
                            user=db_user.strip(),
                            password=db_pass,
                            database=db_name.strip(),
                        )
                        ok, msg = test_connection(connect_cfg)
                        if ok:
                            try:
                                engine = build_engine(connect_cfg)
                                st.session_state[KEY_DB_ENGINE] = engine
                                st.session_state[KEY_DB_CONFIG] = connect_cfg.to_display_dict()
                                st.success(f"Connected to {connect_cfg.database or 'MySQL'}!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Failed to initialize engine: {e}")
                        else:
                            st.error(msg)
                else:
                    if st.button("🔌 Disconnect", use_container_width=True):
                        close_engine(st.session_state.get(KEY_DB_ENGINE))
                        st.session_state[KEY_DB_ENGINE] = None
                        st.session_state[KEY_DB_CONFIG] = None
                        st.session_state[KEY_SCHEMA_INFO] = None
                        st.info("Disconnected from database.")
                        st.rerun()

        # Load and display schema if connected
        if st.session_state.get(KEY_DB_ENGINE) is not None and st.session_state.get(KEY_DB_CONFIG):
            curr_db = st.session_state[KEY_DB_CONFIG].get("database", "")
            if curr_db:
                try:
                    schema_info = _get_cached_schema(st.session_state[KEY_DB_ENGINE], curr_db)
                    st.session_state[KEY_SCHEMA_INFO] = schema_info
                    with st.expander(f"📚 Schema: `{curr_db}` ({len(schema_info.tables)} tables)", expanded=False):
                        if st.button("🔄 Refresh Schema", use_container_width=True):
                            _get_cached_schema.clear()
                            st.rerun()
                        for t_name, t_meta in sorted(schema_info.tables.items()):
                            st.markdown(f"**`{t_meta.name}`** — `{t_meta.estimated_rows:,}` rows")
                            if t_meta.indexes:
                                idx_str = ", ".join(
                                    f"`{idx.name}` ({', '.join(idx.columns)})" for idx in t_meta.indexes.values()
                                )
                                st.caption(f"Indexes: {idx_str}")
                except Exception as schema_err:
                    st.caption(f"⚠️ Schema load notice: {schema_err}")

        st.markdown("---")

        # Sample query picker
        st.markdown("### 📂 Load Sample Query")
        selected_sample = "— Select a sample —"
        try:
            sample_df = pd.read_csv("data/sample_queries.csv")
            options = ["— Select a sample —"] + sample_df["title"].tolist()
            choice = st.selectbox("Choose a pre-built query", options, label_visibility="collapsed")
            if choice != "— Select a sample —":
                row = sample_df[sample_df["title"] == choice].iloc[0]
                selected_sample = row["query"]
                st.caption(f"**Category:** {row['category']}  |  **Complexity:** {row['complexity']}")
                st.caption(row["description"])
        except Exception as e:
            st.caption(f"Could not load samples: {e}")

        st.markdown("---")

        # Session analytics
        st.markdown("### 📊 Session Stats")
        history = st.session_state.get(KEY_HISTORY, [])
        st.metric("Queries Analyzed", len(history))
        if history:
            avg_score = sum(h["score"] for h in history) / len(history)
            st.metric("Avg Score", f"{avg_score:.1f} / 100")

        if st.button("🗑️ Clear History", use_container_width=True):
            st.session_state[KEY_HISTORY] = []
            st.rerun()

        st.markdown("---")

        # AI Assistant Toggle
        st.markdown("### 🤖 AI Assistant (Optional)")
        enable_ai = st.checkbox(
            "Enable LLM Insights",
            value=False,
            help="Use Google Gemini or OpenAI for natural language analysis and rewrites. Off by default.",
        )
        if enable_ai:
            st.caption(
                "🔒 **Privacy Notice:** When enabled, only the query syntax and schema column definitions are sent to the AI provider. "
                "No database row data or user credentials are ever transmitted."
            )

    return SidebarState(
        selected_sample=selected_sample,
        enable_ai=enable_ai,
        active_schema=st.session_state.get(KEY_SCHEMA_INFO),
    )
