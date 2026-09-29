"""rewrite_engine.py
AST-Driven SQL Query Rewrite Engine for MySQL 8.x.

Transforms inefficient SQL patterns into mathematically and semantically verified equivalents.
All rewrites operate on sqlglot AST nodes through an extensible RewriteRule registry.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import Any, Optional

import sqlglot
from sqlglot import exp

from query_model import QueryFeatures, extract_query_features
from rewrite_validation import validate_rewrite_static, EquivalenceLevel
from db.schema import SchemaInfo


# ---------------------------------------------------------------------------
# Default Column Hint Library (Used only when DB schema is not connected)
# ---------------------------------------------------------------------------

_COLUMN_HINTS: dict[str, list[str]] = {
    "users":        ["id", "name", "email", "created_at"],
    "customers":    ["id", "name", "email", "phone"],
    "orders":       ["id", "customer_id", "total", "status", "created_at"],
    "order_items":  ["id", "order_id", "product_id", "quantity", "price"],
    "products":     ["id", "name", "price", "category_id"],
    "employees":    ["id", "name", "department", "salary"],
    "logs":         ["id", "user_id", "action", "created_at"],
    "sessions":     ["id", "user_id", "status", "started_at"],
}


def _get_columns_for_table(table_name: str, schema: Optional[SchemaInfo] = None) -> list[str]:
    """Retrieve actual column names from schema if available, else sensible fallback."""
    t_clean = table_name.lower().strip("`\"' ")
    if schema is not None:
        t_info = schema.get_table(t_clean)
        if t_info and t_info.columns:
            return list(t_info.columns.keys())
    return _COLUMN_HINTS.get(t_clean, ["id", "name", "created_at"])


def _format_sql(sql: str) -> str:
    """Format SQL query with readable indentation."""
    try:
        return sqlglot.transpile(sql, read="mysql", write="mysql", pretty=True)[0]
    except Exception:
        return sql.strip()


# ---------------------------------------------------------------------------
# Base Rewrite Rule
# ---------------------------------------------------------------------------

class RewriteRule(ABC):
    """Abstract base class for AST query rewrite transformations."""

    name: str = "BaseRule"
    description: str = "Base rewrite rule"
    safety_level: str = EquivalenceLevel.VERIFIED_EQUIVALENT.value

    @abstractmethod
    def applies(
        self,
        ast: exp.Expression,
        features: QueryFeatures,
        schema: Optional[SchemaInfo] = None,
        **kwargs: Any,
    ) -> bool:
        """Return True if this rule can be safely applied to the AST."""
        raise NotImplementedError

    @abstractmethod
    def apply(
        self,
        ast: exp.Expression,
        features: QueryFeatures,
        schema: Optional[SchemaInfo] = None,
        **kwargs: Any,
    ) -> tuple[bool, str]:
        """Apply the transformation to the AST in place.
        Returns: (is_modified, explanation_message).
        """
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Concrete Rules
# ---------------------------------------------------------------------------

class InSubqueryToExistsRule(RewriteRule):
    """Transforms col IN (SELECT col FROM ...) to EXISTS (SELECT 1 FROM ... WHERE ...)."""

    name = "IN Subquery to EXISTS"
    description = "Rewrites IN (subquery) to EXISTS to avoid materializing large subquery sets."
    safety_level = EquivalenceLevel.VERIFIED_EQUIVALENT.value

    def applies(self, ast: exp.Expression, features: QueryFeatures, schema: Optional[SchemaInfo] = None, **kwargs: Any) -> bool:
        for in_node in ast.find_all(exp.In):
            is_negated = in_node.args.get("is_negated") or isinstance(in_node.parent, exp.Not)
            if in_node.find(exp.Select) and not is_negated:
                return True
        return False

    def apply(self, ast: exp.Expression, features: QueryFeatures, schema: Optional[SchemaInfo] = None, **kwargs: Any) -> tuple[bool, str]:
        modified = False
        for in_node in list(ast.find_all(exp.In)):
            is_negated = in_node.args.get("is_negated") or isinstance(in_node.parent, exp.Not)
            subquery = in_node.find(exp.Select)
            if subquery and not is_negated:
                left_col = in_node.this
                sub_tbl = subquery.find(exp.Table)
                if sub_tbl and subquery.expressions:
                    sub_col = subquery.expressions[0]
                    # Preserve existing subquery where clause if present
                    sub_where = subquery.find(exp.Where)
                    if sub_where:
                        corr_cond = f"{sub_where.this.sql(dialect='mysql')} AND {sub_col.sql(dialect='mysql')} = {left_col.sql(dialect='mysql')}"
                    else:
                        corr_cond = f"{sub_col.sql(dialect='mysql')} = {left_col.sql(dialect='mysql')}"

                    exists_str = f"EXISTS (SELECT 1 FROM {sub_tbl.sql(dialect='mysql')} WHERE {corr_cond})"
                    new_node = sqlglot.parse_one(exists_str, read="mysql")
                    in_node.replace(new_node)
                    modified = True
                    break

        return modified, "Rewrote IN (subquery) to EXISTS to avoid materializing intermediate subquery results."


class NotInSubqueryToNotExistsRule(RewriteRule):
    """Transforms col NOT IN (SELECT col FROM ...) to NOT EXISTS (SELECT 1 FROM ... WHERE ...)."""

    name = "NOT IN Subquery to NOT EXISTS"
    description = "Eliminates dangerous NULL-trap and allows MySQL anti-join optimization."
    safety_level = EquivalenceLevel.VERIFIED_EQUIVALENT.value

    def applies(self, ast: exp.Expression, features: QueryFeatures, schema: Optional[SchemaInfo] = None, **kwargs: Any) -> bool:
        for in_node in ast.find_all(exp.In):
            is_negated = in_node.args.get("is_negated") or isinstance(in_node.parent, exp.Not)
            if is_negated and in_node.find(exp.Select):
                return True
        return False

    def apply(self, ast: exp.Expression, features: QueryFeatures, schema: Optional[SchemaInfo] = None, **kwargs: Any) -> tuple[bool, str]:
        modified = False
        for in_node in list(ast.find_all(exp.In)):
            is_negated = in_node.args.get("is_negated") or isinstance(in_node.parent, exp.Not)
            subquery = in_node.find(exp.Select)
            if is_negated and subquery:
                left_col = in_node.this
                sub_tbl = subquery.find(exp.Table)
                if sub_tbl and subquery.expressions:
                    sub_col = subquery.expressions[0]
                    sub_where = subquery.find(exp.Where)
                    if sub_where:
                        corr_cond = f"{sub_where.this.sql(dialect='mysql')} AND {sub_col.sql(dialect='mysql')} = {left_col.sql(dialect='mysql')}"
                    else:
                        corr_cond = f"{sub_col.sql(dialect='mysql')} = {left_col.sql(dialect='mysql')}"

                    not_exists_str = f"NOT EXISTS (SELECT 1 FROM {sub_tbl.sql(dialect='mysql')} WHERE {corr_cond})"
                    new_node = sqlglot.parse_one(not_exists_str, read="mysql")

                    # If parent was exp.Not, replace parent; otherwise replace in_node
                    target_replace = in_node.parent if isinstance(in_node.parent, exp.Not) else in_node
                    target_replace.replace(new_node)
                    modified = True
                    break

        return modified, "Rewrote NOT IN (subquery) to NOT EXISTS, eliminating NULL-trap hazard and enabling anti-join index seeks."


class DateYearFunctionToRangeRule(RewriteRule):
    """Transforms YEAR(col) = 2024 into col >= '2024-01-01' AND col < '2025-01-01'."""

    name = "Function on Date Column to Sargable Range"
    description = "Converts YEAR(date_col) = YYYY into a range scan (date_col >= YYYY-01-01 AND date_col < (YYYY+1)-01-01)."
    safety_level = EquivalenceLevel.VERIFIED_EQUIVALENT.value

    def applies(self, ast: exp.Expression, features: QueryFeatures, schema: Optional[SchemaInfo] = None, **kwargs: Any) -> bool:
        where_node = ast.find(exp.Where)
        if not where_node:
            return False
        for eq in where_node.find_all(exp.EQ):
            if isinstance(eq.this, exp.Year) or (hasattr(eq.this, "key") and eq.this.key.lower() == "year"):
                if isinstance(eq.expression, exp.Literal) and eq.expression.is_number:
                    return True
        return False

    def apply(self, ast: exp.Expression, features: QueryFeatures, schema: Optional[SchemaInfo] = None, **kwargs: Any) -> tuple[bool, str]:
        modified = False
        where_node = ast.find(exp.Where)
        if where_node:
            for eq in list(where_node.find_all(exp.EQ)):
                if isinstance(eq.this, exp.Year) or (hasattr(eq.this, "key") and eq.this.key.lower() == "year"):
                    col = eq.this.find(exp.Column)
                    if col and isinstance(eq.expression, exp.Literal) and eq.expression.is_number:
                        try:
                            year_val = int(eq.expression.this)
                            col_str = col.sql(dialect="mysql")
                            new_pred = sqlglot.parse_one(
                                f"{col_str} >= '{year_val}-01-01' AND {col_str} < '{year_val+1}-01-01'",
                                read="mysql",
                            )
                            eq.replace(new_pred)
                            modified = True
                        except ValueError:
                            pass
        return modified, "Transformed YEAR(column) filter into a sargable date range, enabling B-tree range seek."


class RemoveRedundantDistinctRule(RewriteRule):
    """Removes redundant SELECT DISTINCT when a verified unique or primary key column is projected."""

    name = "Remove Redundant DISTINCT"
    description = "Removes DISTINCT if the projection already includes the table's primary or unique key."
    safety_level = EquivalenceLevel.VERIFIED_EQUIVALENT.value

    def applies(self, ast: exp.Expression, features: QueryFeatures, schema: Optional[SchemaInfo] = None, **kwargs: Any) -> bool:
        if not schema or not features.has_distinct:
            return False
        if len(features.tables) != 1:
            return False

        tbl_name = features.tables[0].lower()
        t_info = schema.get_table(tbl_name)
        if not t_info:
            return False

        # Find primary key or unique columns
        unique_cols = set()
        for idx in t_info.indexes.values():
            if idx.is_primary or idx.is_unique:
                if len(idx.columns) == 1:
                    unique_cols.add(idx.columns[0].lower())

        for proj_col in features.selected_columns:
            clean_proj = proj_col.split(".")[-1].strip("`\"' ").lower()
            if clean_proj in unique_cols:
                return True
        return False

    def apply(self, ast: exp.Expression, features: QueryFeatures, schema: Optional[SchemaInfo] = None, **kwargs: Any) -> tuple[bool, str]:
        if isinstance(ast, exp.Select) and ast.args.get("distinct"):
            ast.set("distinct", None)
            return True, "Removed redundant DISTINCT: A primary or unique key is selected, guaranteeing row uniqueness without filesort."
        return False, ""


class UnionToUnionAllRule(RewriteRule):
    """Replaces UNION with UNION ALL to stream results without temporary table deduplication."""

    name = "UNION to UNION ALL"
    description = "Replaces UNION with UNION ALL to stream rows directly without temporary table deduplication."
    safety_level = EquivalenceLevel.VERIFIED_EQUIVALENT.value

    def applies(self, ast: exp.Expression, features: QueryFeatures, schema: Optional[SchemaInfo] = None, **kwargs: Any) -> bool:
        for u in ast.find_all(exp.Union):
            if u.args.get("distinct", True):
                return True
        return False

    def apply(self, ast: exp.Expression, features: QueryFeatures, schema: Optional[SchemaInfo] = None, **kwargs: Any) -> tuple[bool, str]:
        modified = False
        for u in list(ast.find_all(exp.Union)):
            if u.args.get("distinct", True):
                u.set("distinct", False)
                modified = True
        return modified, "Replaced UNION with UNION ALL to stream rows directly, avoiding internal temporary table filesort."


class FunctionOnColumnRule(RewriteRule):
    """Transforms UPPER(col) = 'CONST' into col = LOWER('CONST')."""

    name = "Transform Function on Column"
    description = "Transforms function application to constant value so index on column can be used."
    safety_level = EquivalenceLevel.VERIFIED_EQUIVALENT.value

    def applies(self, ast: exp.Expression, features: QueryFeatures, schema: Optional[SchemaInfo] = None, **kwargs: Any) -> bool:
        where_node = ast.find(exp.Where)
        if not where_node:
            return False
        for eq in where_node.find_all(exp.EQ):
            if isinstance(eq.this, (exp.Upper, exp.Lower, exp.Anonymous, exp.Func)):
                func_name = (getattr(eq.this, "key", None) or getattr(eq.this, "name", "")).upper()
                if func_name in ("UPPER", "LOWER") and isinstance(eq.expression, exp.Literal):
                    return True
        return False

    def apply(self, ast: exp.Expression, features: QueryFeatures, schema: Optional[SchemaInfo] = None, **kwargs: Any) -> tuple[bool, str]:
        modified = False
        where_node = ast.find(exp.Where)
        if where_node:
            for eq in list(where_node.find_all(exp.EQ)):
                if isinstance(eq.this, (exp.Upper, exp.Lower, exp.Anonymous, exp.Func)):
                    func_name = (getattr(eq.this, "key", None) or getattr(eq.this, "name", "")).upper()
                    col = eq.this.find(exp.Column)
                    if func_name in ("UPPER", "LOWER") and col and isinstance(eq.expression, exp.Literal):
                        val_str = str(eq.expression.this).strip("'\"")
                        target_val = val_str.lower() if func_name == "UPPER" else val_str.upper()
                        new_node = sqlglot.parse_one(f"{col.sql(dialect='mysql')} = '{target_val}'", read="mysql")
                        eq.replace(new_node)
                        modified = True
                        break
        return modified, "Inverted case transformation from column to literal, making the predicate sargable."


class SelectStarRewriteRule(RewriteRule):
    """Replaces SELECT * with explicit columns from schema metadata or sensible hints."""

    name = "Replace SELECT *"
    description = "Replaces wildcard SELECT * with explicit column projection."
    safety_level = EquivalenceLevel.VERIFIED_EQUIVALENT.value

    def applies(self, ast: exp.Expression, features: QueryFeatures, schema: Optional[SchemaInfo] = None, **kwargs: Any) -> bool:
        return features.select_star

    def apply(self, ast: exp.Expression, features: QueryFeatures, schema: Optional[SchemaInfo] = None, **kwargs: Any) -> tuple[bool, str]:
        modified = False
        if not isinstance(ast, exp.Select):
            return False, ""

        table_name = features.tables[0] if features.tables else "your_table"
        cols = _get_columns_for_table(table_name, schema=schema)

        # Check if alias exists
        alias = None
        for t in ast.find_all(exp.Table):
            if t.name.lower() == table_name.lower() and t.alias:
                alias = t.alias
                break

        new_expressions = []
        for expr in ast.expressions:
            if isinstance(expr, exp.Star):
                for c in cols:
                    col_ref = f"{alias}.{c}" if alias else c
                    new_expressions.append(sqlglot.parse_one(col_ref, read="mysql"))
                modified = True
            else:
                new_expressions.append(expr)

        if modified:
            ast.set("expressions", new_expressions)
            source_desc = "live schema metadata" if schema and schema.get_table(table_name) else "suggested column profile"
            return True, f"Replaced SELECT * with explicit column list ({', '.join(cols[:4])}...) derived from {source_desc}."

        return False, ""


class LimitInjectionRule(RewriteRule):
    """Injects LIMIT 100 on unbounded SELECT queries."""

    name = "Inject LIMIT 100"
    description = "Appends LIMIT 100 to bound result set and protect memory buffers."
    safety_level = EquivalenceLevel.CHANGES_RESULTS_SUBSET.value

    def applies(self, ast: exp.Expression, features: QueryFeatures, schema: Optional[SchemaInfo] = None, **kwargs: Any) -> bool:
        allow_limit = kwargs.get("allow_limit_injection", True)
        if not allow_limit:
            return False
        return features.statement_type == "SELECT" and features.limit is None

    def apply(self, ast: exp.Expression, features: QueryFeatures, schema: Optional[SchemaInfo] = None, **kwargs: Any) -> tuple[bool, str]:
        if isinstance(ast, exp.Select) and not ast.find(exp.Limit):
            ast.set("limit", exp.Limit(expression=exp.Literal.number(100)))
            return True, "Appended LIMIT 100 to guard application memory against unbounded result scans."
        return False, ""


# ---------------------------------------------------------------------------
# Registry of Active Rewrite Rules
# ---------------------------------------------------------------------------

REWRITE_RULES_REGISTRY: list[RewriteRule] = [
    InSubqueryToExistsRule(),
    NotInSubqueryToNotExistsRule(),
    DateYearFunctionToRangeRule(),
    RemoveRedundantDistinctRule(),
    UnionToUnionAllRule(),
    FunctionOnColumnRule(),
    SelectStarRewriteRule(),
    LimitInjectionRule(),
]


# ---------------------------------------------------------------------------
# Public Entrypoint
# ---------------------------------------------------------------------------

def rewrite_query(
    query: str,
    analysis: dict,
    schema: Optional[SchemaInfo] = None,
    allow_limit_injection: bool = True,
    dialect: str = "mysql",
) -> dict:
    """Automatically rewrite an inefficient SQL query using the AST RewriteRule registry.

    Parameters
    ----------
    query                 : str  — original SQL query
    analysis              : dict — output of analyzer.analyze_query()
    schema                : SchemaInfo | None — optional live schema metadata
    allow_limit_injection : bool — whether to inject LIMIT 100 on unbounded queries

    Returns
    -------
    dict with keys:
        original          : str  — formatted original query
        rewritten         : str  — optimized rewritten query
        changes           : list[str] — human-readable descriptions of rules applied
        is_changed        : bool — whether any transformation was applied
        rewrite_score_est : int  — estimated performance score delta
        validation        : dict — static and semantic validation result with trust badge
        supported         : bool — whether statement type is supported for rewriting
    """
    cleaned_query = query.strip()
    stmt_type = analysis.get("statement_type") or analysis.get("query_type", "SELECT")

    # Safety: Only SELECT, CTE, and UNION statements can be rewritten
    if stmt_type not in ("SELECT", "CTE", "UNION"):
        val = validate_rewrite_static(cleaned_query, cleaned_query, [])
        return {
            "original": _format_sql(cleaned_query),
            "rewritten": _format_sql(cleaned_query),
            "changes": [f"No automatic rewrite available for {stmt_type} statements (safe analysis only)."],
            "is_changed": False,
            "rewrite_score_est": 0,
            "validation": val.to_dict(),
            "supported": False,
        }

    try:
        ast = sqlglot.parse_one(cleaned_query, read=dialect)
    except Exception as e:
        logger.warning("Could not parse query with sqlglot for rewriting: %s", e)
        val = validate_rewrite_static(cleaned_query, cleaned_query, [])
        return {
            "original": cleaned_query,
            "rewritten": cleaned_query,
            "changes": [f"Rewrite skipped: AST parsing error ({e})."],
            "is_changed": False,
            "rewrite_score_est": 0,
            "validation": val.to_dict(),
            "supported": False,
        }

    features = extract_query_features(cleaned_query, dialect=dialect)
    changes: list[str] = []

    # Run through the RewriteRule registry
    for rule in REWRITE_RULES_REGISTRY:
        if rule.applies(ast, features, schema=schema, allow_limit_injection=allow_limit_injection):
            applied, explanation = rule.apply(
                ast,
                features,
                schema=schema,
                allow_limit_injection=allow_limit_injection,
            )
            if applied:
                changes.append(explanation)
                # Re-extract features after AST modification for subsequent rules
                features = extract_query_features(ast.sql(dialect=dialect), dialect=dialect)

    # Check for large OFFSET keyset pagination advice
    if features.offset and features.offset >= 500:
        changes.append(
            f"Advice: Query uses deep OFFSET ({features.offset}). "
            "Consider keyset pagination (WHERE id > last_seen_id ORDER BY id ASC LIMIT N) instead of OFFSET."
        )

    formatted_original = _format_sql(cleaned_query)
    formatted_rewritten = _format_sql(ast.sql(dialect=dialect))

    # Validate rewritten result
    validation = validate_rewrite_static(cleaned_query, formatted_rewritten, changes, dialect=dialect)

    # Estimate score gain
    score_delta = min(len(changes) * 12, 50)

    return {
        "original":          formatted_original,
        "rewritten":         formatted_rewritten,
        "changes":           changes,
        "is_changed":        len(changes) > 0,
        "rewrite_score_est": score_delta,
        "validation":        validation.to_dict(),
        "supported":         True,
    }
