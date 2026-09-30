"""
ui/tab_practices.py
Tab 4: Best Practices & Architecture Viewer — 12 curated MySQL performance guidelines
and full system component & sequence architecture diagrams.
"""

from __future__ import annotations

import streamlit as st
import streamlit.components.v1 as components

from recommendations import BEST_PRACTICES

MERMAID_COMPONENT_GRAPH = """
graph TD
    classDef real fill:#1b4d3e,stroke:#2ecc71,stroke-width:2px,color:#fff;
    classDef sim fill:#5c3a21,stroke:#e67e22,stroke-width:2px,color:#fff;
    classDef ui fill:#1f2937,stroke:#3b82f6,stroke-width:2px,color:#fff;
    classDef db fill:#2c3e50,stroke:#9b59b6,stroke-width:2px,color:#fff;

    subgraph UI_Layer ["Presentation Layer (Streamlit)"]
        APP["app.py (Entrypoint)"]:::ui
        SB["ui/sidebar.py (Connection & Schema Controls)"]:::ui
        TAB1["ui/tab_analyzer.py (Diagnostics & Scoring)"]:::ui
        TAB2["ui/tab_history.py (SQLite History Explorer)"]:::ui
        TAB5["ui/tab_advanced.py (Plan, Diff, Benchmark)"]:::ui
    end

    subgraph Core_Engine ["Analysis & Rewriting Engine"]
        VAL["utils/validation.py (Security & Bounds Check)"]:::real
        PARSER["query_model.py (sqlglot MySQL AST Extractor)"]:::real
        DETECTORS["detectors/ & analyzer.py (12+ Anti-Pattern Plugins)"]:::real
        SCORING["scoring.py & scoring_rules.py (0-100 Quality Math)"]:::real
        RECS["recommendations.py (MySQL 8.x Index DDL)"]:::real
        REWRITE["rewrite_engine.py (AST Transformations)"]:::real
        RW_VAL["rewrite_validation.py (Multiset & AST Equivalence)"]:::real
    end

    subgraph Simulation_Layer ["Heuristic Simulation Layer"]
        PLAN_SIM["execution_plan.py (Simulated EXPLAIN Tree)"]:::sim
        IMPACT_SIM["simulator.py (Latency & Scan Multipliers)"]:::sim
    end

    subgraph Live_DB_Layer ["Live Database Integration"]
        DBCONN["db/connection.py (SQLAlchemy + PyMySQL Pool)"]:::db
        DBSCHEMA["db/schema.py (information_schema Introspection)"]:::db
        DBEXPLAIN["db/explain.py (Live EXPLAIN / ANALYZE Guard)"]:::db
        DBBENCH["db/benchmark.py (Multi-run Statistical Timer)"]:::db
    end

    subgraph Persistence_AI ["Persistence & Optional AI"]
        STORE["history_store.py (Local SQLite Repository)"]:::real
        AI_PKG["ai/ (Gemini / OpenAI Assistant with Fallback)"]:::real
    end

    %% UI Connections
    APP --> SB
    APP --> TAB1
    APP --> TAB2
    APP --> TAB5

    %% Analyzer Tab Flow
    TAB1 --> VAL
    VAL --> PARSER
    PARSER --> DETECTORS
    DETECTORS --> SCORING
    DETECTORS --> RECS
    TAB1 --> AI_PKG
    TAB1 --> STORE

    %% Advanced Tab Flow
    TAB5 --> PLAN_SIM
    TAB5 --> IMPACT_SIM
    TAB5 --> REWRITE
    REWRITE --> RW_VAL
    TAB5 --> DBEXPLAIN
    TAB5 --> DBBENCH

    %% Database Introspection
    SB --> DBCONN
    DBCONN --> DBSCHEMA
    DBSCHEMA -.-> DETECTORS
    DBSCHEMA -.-> RECS
    DBSCHEMA -.-> SCORING
"""

MERMAID_SEQUENCE_OFFLINE = """
sequenceDiagram
    autonumber
    actor User
    participant UI as ui/tab_analyzer.py
    participant Val as utils/validation.py
    participant Model as query_model.py
    participant Analyzer as analyzer.py + detectors/
    participant Scoring as scoring.py
    participant Recs as recommendations.py
    participant Store as history_store.py

    User->>UI: Enter SQL & click "Analyze Query"
    UI->>Val: validate_sql_input(query)
    alt Unsafe or Invalid Input
        Val-->>UI: ValidationError (empty, comment-only, >20k chars)
        UI-->>User: Display friendly error card
    else Valid Query
        Val-->>UI: Sanitized SQL string
        UI->>Model: extract_query_features(query) [sqlglot AST]
        Model-->>UI: QueryFeatures (tables, joins, predicates, projections)
        UI->>Analyzer: analyze_query(query, schema)
        Analyzer->>Analyzer: Run 12+ Anti-Pattern Detectors
        Analyzer-->>UI: Issues list, complexity tier, AST findings
        UI->>Scoring: compute_score(analysis, schema)
        Scoring->>Scoring: Base 100 - Penalties + Bonuses * Schema Multipliers
        Scoring-->>UI: ScoreResult (total, waterfall breakdown, cost band)
        UI->>Recs: generate_index_recommendations(query, analysis, schema)
        Recs-->>UI: Ranked MySQL 8.x CREATE INDEX DDLs
        UI->>Store: HistoryStore.add(...)
        Store-->>UI: Persisted to data/history.db
        UI-->>User: Render KPI cards, score gauge, findings & recommendations
    end
"""

MERMAID_SEQUENCE_CONNECTED = """
sequenceDiagram
    autonumber
    actor User
    participant Sidebar as ui/sidebar.py
    participant DBConn as db/connection.py
    participant DBSchema as db/schema.py
    participant DBExplain as db/explain.py
    participant DBBench as db/benchmark.py
    participant AdvTab as ui/tab_advanced.py

    User->>Sidebar: Configure host, user, port & database
    Sidebar->>DBConn: init_connection_pool(config)
    DBConn-->>Sidebar: Pool established (SQLAlchemy Engine)
    Sidebar->>DBSchema: get_cached_schema(engine, database)
    DBSchema->>DBConn: Query information_schema (tables, columns, indexes, cardinalities)
    DBConn-->>DBSchema: Raw metadata rows
    DBSchema-->>Sidebar: SchemaContext loaded into session_state

    User->>AdvTab: Request Real EXPLAIN FORMAT=JSON
    AdvTab->>DBExplain: get_live_explain(engine, query)
    DBExplain->>DBExplain: validate_select_only(query) [Strict Guard]
    DBExplain->>DBConn: EXPLAIN FORMAT=JSON {query}
    DBConn-->>DBExplain: Execution plan JSON
    DBExplain-->>AdvTab: Parsed access types (ALL, ref, range, cost info)

    User->>AdvTab: Request Real Database Benchmark
    AdvTab->>DBBench: benchmark_query(engine, query, runs=5, warmup=1)
    DBBench->>DBBench: validate_select_only(query)
    loop 1 Warm-up + 5 Measurement Runs
        DBBench->>DBConn: Execute and measure high-resolution perf_counter()
        DBConn-->>DBBench: Result consumed
    end
    DBBench-->>AdvTab: BenchmarkResult (min, median, max, stddev ms)
    AdvTab-->>User: Render latency charts & plan tree
"""


def _render_mermaid_component(diagram_code: str, height: int = 560) -> None:
    """Render a Mermaid diagram inside Streamlit using a responsive HTML container."""
    html_code = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
        <style>
            body {{
                margin: 0;
                padding: 10px;
                background: transparent;
                display: flex;
                justify-content: center;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            }}
            .mermaid {{
                width: 100%;
                display: flex;
                justify-content: center;
            }}
        </style>
    </head>
    <body>
        <div class="mermaid">
{diagram_code}
        </div>
        <script>
            mermaid.initialize({{
                startOnLoad: true,
                theme: 'dark',
                securityLevel: 'loose',
                fontFamily: 'Inter, system-ui, sans-serif'
            }});
        </script>
    </body>
    </html>
    """
    components.html(html_code, height=height, scrolling=True)


def render_tab_practices() -> None:
    """Render Tab 4: SQL Performance Best Practices & System Architecture Viewer UI."""
    st.markdown(
        '<div class="section-header">📖 SQL Performance Best Practices</div>',
        unsafe_allow_html=True,
    )
    st.caption(
        "12 verified MySQL 8.x optimization rules for index design, sargable predicates, and join efficiency."
    )

    with st.expander("🏛️ System Architecture & Execution Flow Visualizer", expanded=False):
        st.info(
            "💡 **Dual Execution Design:** The application executes in **Heuristic Offline Mode** "
            "(ast parsing, rule checks, index DDLs, simulated plans) or **Live Database Mode** "
            "(introspecting `information_schema`, authentic `EXPLAIN FORMAT=JSON`, and live benchmark timers)."
        )

        arch_view = st.radio(
            "Select Architecture View:",
            [
                "🗺️ Component Architecture",
                "🔄 Offline Analysis Sequence",
                "⚡ Live Database Sequence",
                "📦 Design Rationale & Modules",
            ],
            horizontal=True,
            key="arch_view_selector",
        )

        if arch_view == "🗺️ Component Architecture":
            st.markdown("#### Layered Component Graph")
            st.caption(
                "Legend: 🟩 **Real Execution** &nbsp;|&nbsp; 🟧 **Simulated / Heuristic** &nbsp;|&nbsp; 🟦 **Streamlit UI** &nbsp;|&nbsp; 🟪 **Live MySQL Connection**"
            )
            _render_mermaid_component(MERMAID_COMPONENT_GRAPH, height=620)

            with st.expander("🔍 View Raw Mermaid Definition"):
                st.code(MERMAID_COMPONENT_GRAPH.strip(), language="mermaid")

        elif arch_view == "🔄 Offline Analysis Sequence":
            st.markdown("#### Offline Query Analysis Flow (Pure AST & Rule Engine)")
            st.caption(
                "Traces execution when no database is connected: user input is sanitized, parsed via sqlglot, inspected by 12+ anti-pattern plugins, scored, and rewritten."
            )
            _render_mermaid_component(MERMAID_SEQUENCE_OFFLINE, height=520)

            with st.expander("🔍 View Raw Mermaid Definition"):
                st.code(MERMAID_SEQUENCE_OFFLINE.strip(), language="mermaid")

        elif arch_view == "⚡ Live Database Sequence":
            st.markdown("#### Live MySQL Introspection & Execution Plan Flow")
            st.caption(
                "Traces execution when connected to MySQL 8.x: pool initialization, information_schema caching, guarded EXPLAIN JSON extraction, and statistical latency benchmarking."
            )
            _render_mermaid_component(MERMAID_SEQUENCE_CONNECTED, height=560)

            with st.expander("🔍 View Raw Mermaid Definition"):
                st.code(MERMAID_SEQUENCE_CONNECTED.strip(), language="mermaid")

        elif arch_view == "📦 Design Rationale & Modules":
            st.markdown("#### Engineering Decisions & Module Mapping")

            col1, col2 = st.columns(2)
            with col1:
                st.markdown(
                    """
                    **1. Why `sqlglot` over Regex?**
                    - SQL is context-free and recursive; regex fails on nested subqueries, CTEs, string literals containing keywords, and dialect variations.
                    - `sqlglot` builds a true Abstract Syntax Tree (AST), enabling exact AST node visitation (`exp.Select`, `exp.Join`, `exp.Where`).

                    **2. Why SQLite for History?**
                    - Zero-configuration local persistence (`data/history.db`).
                    - Requires no Docker container or external database to store session queries, scores, and timestamps.
                    """
                )
            with col2:
                st.markdown(
                    """
                    **3. Why Simulated Heuristics alongside Real DB?**
                    - Developers and students often lack access to production schemas with millions of rows.
                    - Heuristics permit offline exploration, teaching cost estimation and sargability without DB credentials.

                    **4. Strict Safety Guarding**
                    - `db.explain` and `db.benchmark` enforce strict AST validation rejecting any mutating or DDL statements (`UPDATE`, `DELETE`, `DROP`).
                    """
                )

            st.markdown("---")
            st.caption(
                "For detailed module-by-module breakdown and testing strategy, refer to `docs/ARCHITECTURE.md`."
            )

    st.markdown("---")
    for i, tip in enumerate(BEST_PRACTICES, 1):
        st.markdown(
            f'<div class="success-card">✅ <strong>{i}.</strong> {tip}</div>',
            unsafe_allow_html=True,
        )

