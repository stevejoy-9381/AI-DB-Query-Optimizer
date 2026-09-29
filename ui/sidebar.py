"""
ui/sidebar.py
Sidebar configuration, live database connection manager, schema viewer,
sample query picker, session metrics, and AI assistant toggle.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

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
    is_connected: bool = False


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

        # Schema Section (Live DB or Pasted Schema)
        if st.session_state.get(KEY_DB_ENGINE) is not None and st.session_state.get(KEY_DB_CONFIG):
            curr_db = st.session_state[KEY_DB_CONFIG].get("database", "")
            if curr_db:
                try:
                    schema_info = _get_cached_schema(st.session_state[KEY_DB_ENGINE], curr_db)
                    schema_info.source = "live DB"
                    st.session_state[KEY_SCHEMA_INFO] = schema_info
                    with st.expander(f"📚 Schema: `{curr_db}` (live DB)", expanded=False):
                        st.caption("🟢 **Source:** `Schema: live DB`")
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
        else:
            # Offline / Pasted Schema mode
            current_schema: SchemaInfo | None = st.session_state.get(KEY_SCHEMA_INFO)
            schema_label = f"📋 Schema: `{current_schema.database}`" if current_schema else "📋 Schema (Paste or Load)"
            with st.expander(schema_label, expanded=False):
                if current_schema:
                    st.caption(f"🏷️ **Source:** `Schema: {current_schema.source}`")
                    st.caption(f"Tables: {len(current_schema.tables)}")
                    if st.button("🗑️ Clear Schema", use_container_width=True):
                        st.session_state[KEY_SCHEMA_INFO] = None
                        st.rerun()

                # Action 1: Load Sample shop_db
                from db.schema_parser import load_sample_ddl_schema, parse_ddl_schema
                if st.button("📦 Load Sample Schema (shop_db)", use_container_width=True):
                    try:
                        loaded = load_sample_ddl_schema()
                        st.session_state[KEY_SCHEMA_INFO] = loaded
                        st.success("Loaded shop_db schema (6 tables)!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed to load sample schema: {e}")

                # Action 2: Paste DDL Text
                pasted_ddl = st.text_area(
                    "Paste CREATE TABLE statements",
                    height=120,
                    placeholder="CREATE TABLE customers (\n  id INT PRIMARY KEY,\n  email VARCHAR(255) NOT NULL\n);",
                    key="pasted_ddl_input",
                )
                if st.button("📥 Parse Pasted DDL", use_container_width=True):
                    if pasted_ddl.strip():
                        try:
                            parsed = parse_ddl_schema(pasted_ddl, database_name="custom_pasted")
                            st.session_state[KEY_SCHEMA_INFO] = parsed
                            st.success(f"Parsed {len(parsed.tables)} tables successfully!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Schema syntax error: {e}")

                # Action 3: Upload .sql file
                uploaded_sql = st.file_uploader("Upload .sql schema", type=["sql"], key="upload_sql_schema")
                if uploaded_sql is not None:
                    try:
                        content = uploaded_sql.read().decode("utf-8")
                        parsed = parse_ddl_schema(content, database_name=uploaded_sql.name.split(".")[0])
                        st.session_state[KEY_SCHEMA_INFO] = parsed
                        st.success(f"Loaded schema from {uploaded_sql.name}!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed to parse uploaded SQL: {e}")

                # Optional: Edit row count estimates
                if current_schema and current_schema.tables:
                    st.markdown("##### Approximate Table Row Counts")
                    st.caption("Adjust row counts to drive scoring multipliers:")
                    for t_name, t_meta in current_schema.tables.items():
                        new_rows = st.number_input(
                            f"`{t_meta.name}` rows",
                            min_value=0,
                            value=int(t_meta.estimated_rows),
                            step=1000,
                            key=f"row_cnt_{t_name}",
                        )
                        t_meta.estimated_rows = int(new_rows)

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
        st.markdown("### 📊 Session & History")
        st.checkbox(
            "💾 Save History Locally",
            value=True,
            key="save_history_locally",
            help="Persists query history in local SQLite database (data/history.db). Queries are stored locally only.",
        )
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
        is_connected=st.session_state.get(KEY_DB_ENGINE) is not None,
    )
