"""history_store.py
Persistent query history storage using local SQLite database.

Provides query record persistence across app restarts, text search,
score range filtering, pagination, JSON/CSV exports, and side-by-side comparison.
"""

from __future__ import annotations

import csv
import io
import json
import logging
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Generator, Optional

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = os.path.join("data", "history.db")


class HistoryStore:
    """SQLite repository for storing and querying historical analysis runs."""

    def __init__(self, db_path: str = DEFAULT_DB_PATH) -> None:
        self.db_path = db_path
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        self._init_db()

    @contextmanager
    def _connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager that guarantees connection is closed on exit."""
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        """Create schema and indexes if they do not exist."""
        with self._connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS query_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    query TEXT NOT NULL,
                    statement_type TEXT DEFAULT 'SELECT',
                    score INTEGER NOT NULL,
                    complexity TEXT DEFAULT 'O(n)',
                    cost REAL DEFAULT 0.0,
                    dialect TEXT DEFAULT 'mysql',
                    mode TEXT DEFAULT 'offline',
                    source_badges TEXT DEFAULT '',
                    report_json TEXT NOT NULL
                );
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_history_created ON query_history(created_at DESC);"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_history_score ON query_history(score);"
            )
            conn.commit()

    def add(
        self,
        query: str,
        score: int,
        report_dict: dict[str, Any],
        statement_type: str = "SELECT",
        complexity: str = "O(n)",
        cost: float = 0.0,
        dialect: str = "mysql",
        mode: str = "offline",
        source_badges: str = "",
    ) -> int:
        """Insert a query analysis record into history."""
        report_json = json.dumps(report_dict)
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO query_history (
                    created_at, query, statement_type, score,
                    complexity, cost, dialect, mode, source_badges, report_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    now_str,
                    query.strip(),
                    statement_type,
                    int(score),
                    complexity,
                    float(cost),
                    dialect,
                    mode,
                    source_badges,
                    report_json,
                ),
            )
            conn.commit()
            return int(cursor.lastrowid or 0)

    def get(self, record_id: int) -> Optional[dict[str, Any]]:
        """Retrieve a single history record with parsed JSON report."""
        with self._connection() as conn:
            row = conn.execute(
                "SELECT * FROM query_history WHERE id = ?;", (record_id,)
            ).fetchone()
            if not row:
                return None
            res = dict(row)
            try:
                res["report"] = json.loads(res["report_json"])
            except Exception:
                res["report"] = {}
            return res

    def list(
        self,
        search: Optional[str] = None,
        min_score: int = 0,
        max_score: int = 100,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """List historical query records with optional search filter and pagination."""
        query_sql = "SELECT id, created_at, query, statement_type, score, complexity, cost, dialect, mode, source_badges FROM query_history WHERE score BETWEEN ? AND ?"
        params: list[Any] = [min_score, max_score]

        if search and search.strip():
            query_sql += " AND query LIKE ?"
            params.append(f"%{search.strip()}%")

        query_sql += " ORDER BY id DESC LIMIT ? OFFSET ?;"
        params.extend([limit, offset])

        with self._connection() as conn:
            rows = conn.execute(query_sql, params).fetchall()
            return [dict(r) for r in rows]

    def count(
        self,
        search: Optional[str] = None,
        min_score: int = 0,
        max_score: int = 100,
    ) -> int:
        """Return count of matching records for pagination."""
        count_sql = "SELECT COUNT(*) as cnt FROM query_history WHERE score BETWEEN ? AND ?"
        params: list[Any] = [min_score, max_score]

        if search and search.strip():
            count_sql += " AND query LIKE ?"
            params.append(f"%{search.strip()}%")

        with self._connection() as conn:
            row = conn.execute(count_sql, params).fetchone()
            return int(row["cnt"]) if row else 0

    def delete(self, record_id: int) -> bool:
        """Delete a record by ID."""
        with self._connection() as conn:
            cursor = conn.execute(
                "DELETE FROM query_history WHERE id = ?;", (record_id,)
            )
            conn.commit()
            return cursor.rowcount > 0

    def clear_all(self) -> None:
        """Clear all historical records."""
        with self._connection() as conn:
            conn.execute("DELETE FROM query_history;")
            conn.commit()

    def export_csv(self) -> str:
        """Export all history rows as CSV string."""
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT id, created_at, statement_type, score, complexity, cost, dialect, mode, query FROM query_history ORDER BY id DESC;"
            ).fetchall()
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(["ID", "Timestamp", "Statement", "Score", "Complexity", "Cost", "Dialect", "Mode", "Query"])
            for r in rows:
                writer.writerow([r["id"], r["created_at"], r["statement_type"], r["score"], r["complexity"], r["cost"], r["dialect"], r["mode"], r["query"]])
            return output.getvalue()

    def export_json(self) -> str:
        """Export all history rows as formatted JSON string."""
        with self._connection() as conn:
            rows = conn.execute("SELECT * FROM query_history ORDER BY id DESC;").fetchall()
            records = []
            for r in rows:
                rec = dict(r)
                try:
                    rec["report"] = json.loads(rec["report_json"])
                except Exception:
                    rec["report"] = {}
                records.append(rec)
            return json.dumps(records, indent=2)
