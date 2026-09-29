"""utils/diff.py
Side-by-side SQL diff visualizer and comparison engine.
Formats both queries identically using sqlglot and generates structured,
theme-adaptive side-by-side diff views highlighting additions and deletions.
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass, field
from typing import Literal

import sqlglot


def format_sqlglot_pretty(sql: str, dialect: str = "mysql") -> str:
    """Format SQL query consistently using sqlglot pretty printing."""
    if not sql or not sql.strip():
        return ""
    try:
        return sqlglot.transpile(sql.strip(), read=dialect, write=dialect, pretty=True)[0]
    except Exception:
        return sql.strip()


@dataclass
class DiffLine:
    """Single line in a side-by-side diff."""
    line_num: int | None
    text: str
    tag: Literal["equal", "insert", "delete", "replace", "empty"]


@dataclass
class SideBySideDiff:
    """Structured representation of side-by-side diff."""
    left_lines: list[DiffLine] = field(default_factory=list)
    right_lines: list[DiffLine] = field(default_factory=list)
    lines_added: int = 0
    lines_removed: int = 0
    lines_modified: int = 0
    has_changes: bool = False


def generate_side_by_side_diff(
    original_sql: str,
    rewritten_sql: str,
    dialect: str = "mysql",
) -> SideBySideDiff:
    """Generate structured side-by-side diff lines between original and rewritten SQL.

    Both queries are first formatted with identical sqlglot pretty printing
    so the diff only reflects semantic and keyword changes, not whitespace quirks.
    """
    orig_formatted = format_sqlglot_pretty(original_sql, dialect=dialect)
    rew_formatted = format_sqlglot_pretty(rewritten_sql, dialect=dialect)

    orig_lines = orig_formatted.splitlines()
    rew_lines = rew_formatted.splitlines()

    matcher = difflib.SequenceMatcher(None, orig_lines, rew_lines)
    left_result: list[DiffLine] = []
    right_result: list[DiffLine] = []

    lines_added = 0
    lines_removed = 0
    lines_modified = 0

    orig_idx = 1
    rew_idx = 1

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for line_o, line_r in zip(orig_lines[i1:i2], rew_lines[j1:j2]):
                left_result.append(DiffLine(orig_idx, line_o, "equal"))
                right_result.append(DiffLine(rew_idx, line_r, "equal"))
                orig_idx += 1
                rew_idx += 1
        elif tag == "replace":
            lines_modified += max(i2 - i1, j2 - j1)
            chunk_len = max(i2 - i1, j2 - j1)
            for k in range(chunk_len):
                if i1 + k < i2:
                    left_result.append(DiffLine(orig_idx, orig_lines[i1 + k], "replace"))
                    orig_idx += 1
                else:
                    left_result.append(DiffLine(None, "", "empty"))

                if j1 + k < j2:
                    right_result.append(DiffLine(rew_idx, rew_lines[j1 + k], "replace"))
                    rew_idx += 1
                else:
                    right_result.append(DiffLine(None, "", "empty"))
        elif tag == "delete":
            lines_removed += (i2 - i1)
            for k in range(i1, i2):
                left_result.append(DiffLine(orig_idx, orig_lines[k], "delete"))
                right_result.append(DiffLine(None, "", "empty"))
                orig_idx += 1
        elif tag == "insert":
            lines_added += (j2 - j1)
            for k in range(j1, j2):
                left_result.append(DiffLine(None, "", "empty"))
                right_result.append(DiffLine(rew_idx, rew_lines[k], "insert"))
                rew_idx += 1

    has_changes = (lines_added > 0 or lines_removed > 0 or lines_modified > 0)
    return SideBySideDiff(
        left_lines=left_result,
        right_lines=right_result,
        lines_added=lines_added,
        lines_removed=lines_removed,
        lines_modified=lines_modified,
        has_changes=has_changes,
    )


def render_diff_html(diff: SideBySideDiff) -> str:
    """Render a responsive side-by-side diff in HTML suitable for Streamlit display."""
    left_rows = []
    right_rows = []

    style_map = {
        "equal":   "background: transparent; color: inherit;",
        "insert":  "background: rgba(46, 204, 113, 0.22); color: #2ecc71; font-weight: 600; border-left: 3px solid #2ecc71;",
        "delete":  "background: rgba(231, 76, 60, 0.22); color: #e74c3c; font-weight: 600; border-left: 3px solid #e74c3c;",
        "replace": "background: rgba(243, 156, 18, 0.20); color: #f39c12; font-weight: 600; border-left: 3px solid #f39c12;",
        "empty":   "background: rgba(255, 255, 255, 0.02); color: transparent; user-select: none;",
    }

    prefix_map = {
        "equal": "&nbsp; ",
        "insert": "+ ",
        "delete": "- ",
        "replace": "~ ",
        "empty": "&nbsp; ",
    }

    for l_line, r_line in zip(diff.left_lines, diff.right_lines):
        l_num = f"{l_line.line_num:>3} " if l_line.line_num is not None else "    "
        r_num = f"{r_line.line_num:>3} " if r_line.line_num is not None else "    "

        l_text = l_line.text if l_line.text else "&nbsp;"
        r_text = r_line.text if r_line.text else "&nbsp;"

        l_style = style_map.get(l_line.tag, style_map["equal"])
        r_style = style_map.get(r_line.tag, style_map["equal"])

        l_pref = prefix_map.get(l_line.tag, "&nbsp; ")
        r_pref = prefix_map.get(r_line.tag, "&nbsp; ")

        left_rows.append(
            f'<div style="font-family: monospace; font-size: 0.82rem; padding: 2px 4px; {l_style}">'
            f'<span style="color:#777; user-select:none;">{l_num}</span> '
            f'<span style="user-select:none; font-weight:bold;">{l_pref}</span>{l_text}</div>'
        )
        right_rows.append(
            f'<div style="font-family: monospace; font-size: 0.82rem; padding: 2px 4px; {r_style}">'
            f'<span style="color:#777; user-select:none;">{r_num}</span> '
            f'<span style="user-select:none; font-weight:bold;">{r_pref}</span>{r_text}</div>'
        )

    left_html = "".join(left_rows)
    right_html = "".join(right_rows)

    return f"""
    <div style="display: flex; gap: 12px; width: 100%; border: 1px solid #333; border-radius: 8px; overflow: hidden; background: #161b22; margin-top: 8px; margin-bottom: 12px;">
      <div style="flex: 1; border-right: 1px solid #333; overflow-x: auto; padding: 8px;">
        <div style="font-size: 0.78rem; text-transform: uppercase; color: #888; font-weight: bold; margin-bottom: 6px; padding-bottom: 4px; border-bottom: 1px solid #2a2a2a;">Original SQL</div>
        {left_html}
      </div>
      <div style="flex: 1; overflow-x: auto; padding: 8px;">
        <div style="font-size: 0.78rem; text-transform: uppercase; color: #888; font-weight: bold; margin-bottom: 6px; padding-bottom: 4px; border-bottom: 1px solid #2a2a2a;">Rewritten SQL</div>
        {right_html}
      </div>
    </div>
    """
