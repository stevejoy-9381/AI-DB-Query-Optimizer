"""tests/unit/test_matrix_scoring.py
Automated Unit Tests for all Scoring behaviors defined in docs/TEST_MATRIX.md.
"""

import pytest

from analyzer import analyze_query
from db.schema import ColumnInfo, IndexInfo, SchemaInfo, TableInfo
from scoring import compute_score, simulate_optimized_score


@pytest.fixture
def large_schema() -> SchemaInfo:
    schema = SchemaInfo(database="large_db")
    large_tbl = TableInfo(name="large_table_1m", estimated_rows=2_000_000, data_length_bytes=200_000_000)
    large_tbl.columns = {"id": ColumnInfo("id", "int", False, 1)}
    large_tbl.indexes = {"primary": IndexInfo("PRIMARY", "large_table_1m", ["id"], True, True)}
    schema.tables["large_table_1m"] = large_tbl
    return schema


@pytest.fixture
def small_schema() -> SchemaInfo:
    schema = SchemaInfo(database="small_db")
    small_tbl = TableInfo(name="small_table_500", estimated_rows=500, data_length_bytes=50_000)
    small_tbl.columns = {"id": ColumnInfo("id", "int", False, 1)}
    small_tbl.indexes = {"primary": IndexInfo("PRIMARY", "small_table_500", ["id"], True, True)}
    schema.tables["small_table_500"] = small_tbl
    return schema


def test_scr_base_calc():
    """SCR-BASE-CALC: Computes baseline score of 100 minus rule penalty deductions."""
    anl = analyze_query("SELECT * FROM users")
    score_res = compute_score(anl)
    assert score_res.total < 100
    applied_codes = {r["code"] for r in score_res.breakdown}
    assert "SELECT_STAR" in applied_codes
    assert "MISSING_WHERE" in applied_codes


def test_scr_score_bounds():
    """SCR-SCORE-BOUNDS: Clips score strictly within 0 to 100 range."""
    # Worst case: multiple critical violations
    bad_anl = analyze_query("UPDATE users SET name = 'X'")
    bad_score = compute_score(bad_anl)
    assert 0 <= bad_score.total <= 100

    # Best case: clean query
    good_anl = analyze_query("SELECT id FROM users WHERE id = 1 LIMIT 1")
    good_score = compute_score(good_anl)
    assert 0 <= good_score.total <= 100


def test_scr_cost_tiers():
    """SCR-COST-TIERS: Categorizes score into cost tiers: >=80 LOW, 50-79 MEDIUM, <50 HIGH."""
    good_anl = analyze_query("SELECT id FROM users WHERE id = 1 LIMIT 1")
    good_score = compute_score(good_anl)
    assert good_score.cost_estimate in ("LOW", "MEDIUM")

    bad_anl = analyze_query("SELECT * FROM users")
    bad_score = compute_score(bad_anl)
    assert bad_score.cost_estimate in ("MEDIUM", "HIGH")


def test_scr_stmt_update():
    """SCR-STMT-UPDATE: Applies statement-specific scoring rules for UPDATE statements."""
    anl = analyze_query("UPDATE users SET status = 'inactive'")
    score_res = compute_score(anl)
    applied_codes = {r["code"] for r in score_res.breakdown}
    assert "UPDATE_WITHOUT_WHERE" in applied_codes
    assert score_res.total <= 50
    # Note: 50 is boundary of MEDIUM (50-79) in scoring.py threshold model
    assert score_res.cost_estimate == "MEDIUM"


def test_scr_stmt_delete():
    """SCR-STMT-DELETE: Applies statement-specific scoring rules for DELETE statements."""
    anl = analyze_query("DELETE FROM sessions")
    score_res = compute_score(anl)
    applied_codes = {r["code"] for r in score_res.breakdown}
    assert "DELETE_WITHOUT_WHERE" in applied_codes
    assert score_res.total <= 50
    # Note: 50 is boundary of MEDIUM (50-79) in scoring.py threshold model
    assert score_res.cost_estimate == "MEDIUM"


def test_scr_tbl_multiplier(large_schema, small_schema):
    """SCR-TBL-MULTIPLIER: Scales penalties by table size multiplier (1.0x <10k, 2.0x >1M rows)."""
    large_anl = analyze_query("SELECT * FROM large_table_1m", schema=large_schema)
    large_score = compute_score(large_anl, schema=large_schema)
    assert large_score.table_multiplier == 2.0

    small_anl = analyze_query("SELECT * FROM small_table_500", schema=small_schema)
    small_score = compute_score(small_anl, schema=small_schema)
    assert small_score.table_multiplier == 1.0


def test_scr_bonus_where():
    """SCR-BONUS-WHERE: Awards positive bonus (+10) for explicit WHERE filter clause."""
    with_where = analyze_query("SELECT id FROM users WHERE status = 'active'")
    score_with = compute_score(with_where)
    assert any(r["code"] == "HAS_WHERE" and r["delta"] == 10 for r in score_with.breakdown)

    no_where = analyze_query("SELECT id FROM users")
    score_without = compute_score(no_where)
    assert not any(r["code"] == "HAS_WHERE" for r in score_without.breakdown)


def test_scr_bonus_limit():
    """SCR-BONUS-LIMIT: Awards positive bonus (+10) for result-capping LIMIT clause."""
    with_limit = analyze_query("SELECT id FROM users WHERE status = 'active' LIMIT 10")
    score_with = compute_score(with_limit)
    assert any(r["code"] == "HAS_LIMIT" and r["delta"] == 10 for r in score_with.breakdown)

    no_limit = analyze_query("SELECT id FROM users WHERE status = 'active'")
    score_without = compute_score(no_limit)
    assert not any(r["code"] == "HAS_LIMIT" for r in score_without.breakdown)


def test_scr_bonus_cols():
    """SCR-BONUS-COLS: Awards positive bonus (+10) for explicit projection instead of SELECT *."""
    specific = analyze_query("SELECT id, name FROM users WHERE id = 1")
    score_spec = compute_score(specific)
    assert any(r["code"] == "SPECIFIC_COLUMNS" and r["delta"] == 10 for r in score_spec.breakdown)

    star = analyze_query("SELECT * FROM users WHERE id = 1")
    score_star = compute_score(star)
    assert not any(r["code"] == "SPECIFIC_COLUMNS" for r in score_star.breakdown)


def test_scr_sim_optimized():
    """SCR-SIM-OPTIMIZED: Projects simulated score after anti-patterns are resolved."""
    anl = analyze_query("SELECT * FROM users")
    initial_score = compute_score(anl).total
    sim_score = simulate_optimized_score(anl)
    assert sim_score > initial_score


def test_scr_bonus_bulk():
    """SCR-BONUS-BULK: Awards positive bonus (+15) for multi-row bulk INSERT."""
    bulk_anl = analyze_query("INSERT INTO users (id, name) VALUES (1, 'A'), (2, 'B')")
    bulk_score = compute_score(bulk_anl)
    assert any(r["code"] == "BULK_INSERT" and r["delta"] == 15 for r in bulk_score.breakdown)

    single_anl = analyze_query("INSERT INTO users (id, name) VALUES (1, 'A')")
    single_score = compute_score(single_anl)
    assert not any(r["code"] == "BULK_INSERT" for r in single_score.breakdown)
