"""
ai/prompts.py
Secure, privacy-preserving prompt templates for database optimization insights.
Sends ONLY query, schema metadata, and rule findings. NEVER sends row data.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from db.schema import SchemaInfo


SYSTEM_INSTRUCTION = """\
You are an expert MySQL 8.x database administrator and query optimizer.
Analyze the provided SQL query, schema definitions, and rule-based diagnostic findings.
Provide actionable performance insights, identify bottlenecks, and optionally provide a safe rewritten query.

CRITICAL CONSTRAINTS:
1. Return ONLY valid, unadorned JSON conforming to the requested schema. Do not include markdown code fences (like ```json ... ```).
2. The suggested_query MUST be a pure read query (SELECT / CTE). NEVER suggest DDL, DROP, ALTER, DELETE, TRUNCATE, UPDATE, or administrative queries.
3. If no rewrite is appropriate, set suggested_query to null.
4. Base recommendations strictly on MySQL 8.x execution dynamics (InnoDB B-tree index seeks, filesort elimination, temporary tables).
"""


def build_analysis_prompt(
    query: str,
    analysis: dict[str, Any],
    score: int,
    schema: SchemaInfo | None = None,
    plan_summary: str | None = None,
) -> str:
    """
    Construct a privacy-preserving analysis prompt containing:
    - Target SQL query
    - Schema structure (table/column names, types, indexes) — ZERO row data
    - Static rule-engine findings
    - Plan summary (if available)
    """
    # 1. Format schema summary safely (zero user row data)
    schema_summary = "No live schema metadata provided (offline mode)."
    if schema and schema.tables:
        tbl_lines = []
        for tbl_name, tbl_info in schema.tables.items():
            cols = [f"{col.name} ({col.data_type})" for col in tbl_info.columns.values()]
            col_desc = ", ".join(cols) if cols else "unknown"
            idx_list = []
            for idx in tbl_info.indexes.values():
                idx_type = "PK" if idx.is_primary else ("UNIQUE" if idx.is_unique else "INDEX")
                idx_list.append(f"{idx.name} ({idx_type}: {', '.join(idx.columns)})")
            idx_desc = "; ".join(idx_list) if idx_list else "no indexes"
            tbl_lines.append(
                f"- Table `{tbl_info.name}` (~{tbl_info.estimated_rows:,} rows):\n"
                f"    Columns: {col_desc}\n"
                f"    Indexes: {idx_desc}"
            )
        schema_summary = "\n".join(tbl_lines)

    # 2. Format rule-engine findings
    issues = [
        f"[{i.get('severity', 'WARN')}] {i.get('message', '')}" for i in analysis.get("issues", [])
    ]
    warnings = [
        f"[{w.get('severity', 'INFO')}] {w.get('message', '')}"
        for w in analysis.get("warnings", [])
    ]
    findings = issues + warnings
    findings_str = (
        "\n".join(f"- {f}" for f in findings) if findings else "- None detected by static rules"
    )

    prompt_payload = {
        "query": query,
        "performance_score": f"{score}/100",
        "complexity": analysis.get("complexity", "Unknown"),
        "rule_engine_findings": findings_str,
        "schema_metadata": schema_summary,
        "execution_plan_summary": plan_summary or "Plan unavailable",
    }

    prompt = f"""
{SYSTEM_INSTRUCTION}

DATABASE QUERY AND CONTEXT:
Query:
```sql
{prompt_payload["query"]}
```

Performance Score: {prompt_payload["performance_score"]}
Complexity: {prompt_payload["complexity"]}

Rule Engine Findings:
{prompt_payload["rule_engine_findings"]}

Database Schema (Structure Only, No Row Data):
{prompt_payload["schema_metadata"]}

Execution Plan:
{prompt_payload["execution_plan_summary"]}

REQUIRED JSON OUTPUT FORMAT:
{{
  "explanation": "concise technical assessment of query performance and execution path",
  "issues": ["list of identified anti-patterns, missing indexes, or performance risks"],
  "suggested_query": "optimized SELECT query or null",
  "suggested_indexes": ["CREATE INDEX ... statements or empty list"],
  "confidence": 0.95
}}
"""
    return prompt.strip()
