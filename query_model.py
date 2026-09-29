"""Structured SQL AST feature extraction using sqlglot for MySQL 8.x."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError

logger = logging.getLogger(__name__)


@dataclass
class PredicateInfo:
    """Represents a condition in a WHERE or ON clause."""

    column: str
    operator: str
    literal: str | None = None
    is_function_wrapped: bool = False
    function_name: str | None = None
    table: str | None = None


@dataclass
class JoinInfo:
    """Represents a JOIN clause."""

    join_type: str  # INNER, LEFT, RIGHT, CROSS, etc.
    table: str
    alias: str | None = None
    on_condition: str | None = None
    left_column: str | None = None
    right_column: str | None = None


@dataclass
class SubqueryInfo:
    """Represents a nested subquery."""

    subquery_type: str  # SCALAR, IN, EXISTS, DERIVED_TABLE
    is_correlated: bool = False
    sql: str = ""


@dataclass
class QueryFeatures:
    """Comprehensive AST features extracted from a SQL statement."""

    statement_type: str = "UNKNOWN"
    tables: list[str] = field(default_factory=list)
    alias_map: dict[str, str] = field(default_factory=dict)
    selected_columns: list[str] = field(default_factory=list)
    select_star: bool = False
    joins: list[JoinInfo] = field(default_factory=list)
    where_predicates: list[PredicateInfo] = field(default_factory=list)
    group_by_cols: list[str] = field(default_factory=list)
    having_predicates: list[str] = field(default_factory=list)
    order_by_cols: list[str] = field(default_factory=list)
    limit: int | None = None
    offset: int | None = None
    subqueries: list[SubqueryInfo] = field(default_factory=list)
    ctes: list[str] = field(default_factory=list)
    has_distinct: bool = False
    aggregates: list[str] = field(default_factory=list)
    wildcard_likes: list[str] = field(default_factory=list)
    has_where: bool = False
    filter_columns: list[str] = field(default_factory=list)
    is_valid: bool = True
    raw_ast: Any = None
    # Statement-type specific attributes
    is_insert_select: bool = False
    insert_row_count: int | None = None
    is_cte: bool = False
    cte_references: dict[str, int] = field(default_factory=dict)
    has_window_functions: bool = False
    window_functions: list[dict] = field(default_factory=list)


def extract_query_features(sql: str, dialect: str = "mysql") -> QueryFeatures:
    """Parse a SQL string into an AST and extract structured QueryFeatures.

    Args:
        sql: Raw SQL query string.
        dialect: SQL dialect (defaults to 'mysql').

    Returns:
        Populated QueryFeatures dataclass.

    Raises:
        ParseError: When sqlglot cannot parse the statement.
    """
    if not sql or not sql.strip():
        return QueryFeatures(is_valid=False)

    # Parse using sqlglot with mysql dialect
    ast = sqlglot.parse_one(sql, read=dialect)
    features = QueryFeatures(raw_ast=ast)

    # 1. Statement Type
    if isinstance(ast, exp.Select):
        features.statement_type = "SELECT"
    elif isinstance(ast, exp.Insert):
        if ast.find(exp.Select):
            features.statement_type = "INSERT...SELECT"
            features.is_insert_select = True
        else:
            features.statement_type = "INSERT"
        values_node = ast.find(exp.Values)
        if values_node and values_node.expressions:
            features.insert_row_count = len(values_node.expressions)
    elif isinstance(ast, exp.Update):
        features.statement_type = "UPDATE"
    elif isinstance(ast, exp.Delete):
        features.statement_type = "DELETE"
    elif isinstance(ast, exp.Union):
        features.statement_type = "UNION"
    else:
        features.statement_type = ast.key.upper()

    # 2. CTEs (WITH clause)
    with_clause = ast.args.get("with")
    if with_clause:
        features.is_cte = True
        for cte in with_clause.expressions:
            if hasattr(cte, "alias") and cte.alias:
                alias_name = cte.alias.lower()
                features.ctes.append(cte.alias)
                # Count occurrences of this CTE alias in table references
                ref_count = 0
                for tbl in ast.find_all(exp.Table):
                    if tbl.name.lower() == alias_name and tbl.parent != cte:
                        ref_count += 1
                features.cte_references[alias_name] = ref_count

        if features.statement_type == "SELECT" and features.ctes:
            features.statement_type = "CTE"

    # 2b. Window Functions
    for w in ast.find_all(exp.Window):
        features.has_window_functions = True
        func = w.this
        func_name = getattr(func, "key", str(func)).upper()
        partition_by = w.args.get("partition_by")
        has_partition = bool(partition_by)
        features.window_functions.append({
            "function": func_name,
            "has_partition": has_partition,
        })

    # 3. Tables & Aliases
    tables_found: list[str] = []
    alias_map: dict[str, str] = {}
    for table_node in ast.find_all(exp.Table):
        tbl_name = table_node.name
        if tbl_name and tbl_name not in features.ctes:
            if tbl_name not in tables_found:
                tables_found.append(tbl_name)
            alias = table_node.alias
            if alias:
                alias_map[alias.lower()] = tbl_name.lower()
    features.tables = tables_found
    features.alias_map = alias_map

    # 4. Projections / Selected columns & SELECT *
    if isinstance(ast, exp.Select):
        features.has_distinct = bool(ast.args.get("distinct"))
        for expr in ast.expressions:
            if isinstance(expr, exp.Star):
                features.select_star = True
            elif isinstance(expr, exp.Column):
                features.selected_columns.append(expr.name)
            else:
                features.selected_columns.append(expr.sql(dialect=dialect))
                # Star is only SELECT * if not inside an aggregate like COUNT(*)
                for s in expr.find_all(exp.Star):
                    curr = s.parent
                    inside_agg = False
                    while curr and curr != expr:
                        if isinstance(curr, (exp.Count, exp.AggFunc, exp.Anonymous)):
                            inside_agg = True
                            break
                        curr = curr.parent
                    if not inside_agg and not isinstance(expr, exp.Count):
                        features.select_star = True

    # 5. Joins
    for join_node in ast.find_all(exp.Join):
        kind = join_node.kind or "INNER"
        side = join_node.side or ""
        join_type = f"{side} {kind}".strip().upper() if side else kind.upper()
        tbl_expr = join_node.this
        join_tbl = tbl_expr.name if isinstance(tbl_expr, exp.Table) else str(tbl_expr)
        join_alias = tbl_expr.alias if hasattr(tbl_expr, "alias") else None
        on_cond = join_node.args.get("on")

        left_col, right_col = None, None
        if isinstance(on_cond, exp.EQ):
            if isinstance(on_cond.left, exp.Column):
                left_col = on_cond.left.name
            if isinstance(on_cond.right, exp.Column):
                right_col = on_cond.right.name

        features.joins.append(JoinInfo(
            join_type=join_type,
            table=join_tbl,
            alias=join_alias,
            on_condition=on_cond.sql(dialect=dialect) if on_cond else None,
            left_column=left_col,
            right_column=right_col,
        ))

    # 6. WHERE Clause & Predicates
    where_clause = ast.args.get("where") or ast.find(exp.Where)
    features.has_where = where_clause is not None

    filter_cols: set[str] = set()
    if where_clause:
        # Detect leading wildcard in LIKE predicates
        for like_node in where_clause.find_all(exp.Like):
            col_node = like_node.find(exp.Column)
            col_name = col_node.name if col_node else str(like_node.this)
            expr_val = like_node.expression.this if hasattr(like_node.expression, "this") else str(like_node.expression)
            pattern_str = str(expr_val).strip("'\"")
            if pattern_str.startswith("%") or pattern_str.startswith("_"):
                features.wildcard_likes.append(col_name)

        # Detect comparison predicates and function wrapping
        for comp_node in where_clause.find_all((exp.EQ, exp.NEQ, exp.GT, exp.GTE, exp.LT, exp.LTE, exp.In)):
            left = comp_node.left if hasattr(comp_node, "left") else comp_node.this
            is_func = False
            func_name = None
            col_name = None
            table_name = None

            if isinstance(left, (exp.Func, exp.Anonymous)):
                col_node = left.find(exp.Column)
                if col_node:
                    is_func = True
                    func_name = left.key.upper()
                    col_name = col_node.name
                    table_name = col_node.table
            elif isinstance(left, exp.Column):
                col_name = left.name
                table_name = left.table

            if col_name:
                filter_cols.add(col_name.lower())
                features.where_predicates.append(PredicateInfo(
                    column=col_name,
                    operator=comp_node.key.upper(),
                    is_function_wrapped=is_func,
                    function_name=func_name,
                    table=table_name,
                ))

    features.filter_columns = sorted(list(filter_cols))

    # 7. GROUP BY & HAVING
    group_clause = ast.args.get("group")
    if group_clause:
        for g_expr in group_clause.expressions:
            features.group_by_cols.append(g_expr.sql(dialect=dialect))

    having_clause = ast.args.get("having")
    if having_clause:
        features.having_predicates.append(having_clause.this.sql(dialect=dialect))

    # 8. ORDER BY
    order_clause = ast.args.get("order")
    if order_clause:
        for o_expr in order_clause.expressions:
            features.order_by_cols.append(o_expr.sql(dialect=dialect))

    # 9. LIMIT & OFFSET
    limit_clause = ast.args.get("limit") or ast.find(exp.Limit)
    if limit_clause and limit_clause.expression:
        try:
            features.limit = int(limit_clause.expression.name)
        except (ValueError, TypeError, AttributeError):
            pass

    offset_clause = ast.args.get("offset") or ast.find(exp.Offset)
    if offset_clause and offset_clause.expression:
        try:
            features.offset = int(offset_clause.expression.name)
        except (ValueError, TypeError, AttributeError):
            pass

    # 10. Subqueries
    outer_tables = set(tables_found)
    for subquery in ast.find_all(exp.Select):
        if subquery != ast:  # Exclude root select
            sub_sql = subquery.sql(dialect=dialect)
            # Check correlation (references tables from outer query)
            sub_cols = [c.table for c in subquery.find_all(exp.Column) if c.table]
            correlated = any(tbl in outer_tables for tbl in sub_cols)
            features.subqueries.append(SubqueryInfo(
                subquery_type="SUBQUERY",
                is_correlated=correlated,
                sql=sub_sql,
            ))

    # 11. Aggregates (COUNT, SUM, AVG, MAX, MIN)
    for func in ast.find_all((exp.Count, exp.Sum, exp.Avg, exp.Max, exp.Min)):
        features.aggregates.append(func.key.upper())

    return features
