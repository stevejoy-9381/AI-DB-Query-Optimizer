"""Compare regex vs AST analyzer across data/sample_queries.csv."""

import csv
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from analyzer import _analyze_query_regex_fallback, analyze_query


def main():
    csv_path = Path(__file__).parent.parent / "data" / "sample_queries.csv"
    if not csv_path.exists():
        print(f"Error: {csv_path} not found.")
        return

    differences = []
    total = 0

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader, 1):
            query = row["query"].strip()
            if not query:
                continue
            total += 1

            # Run regex fallback
            regex_res = _analyze_query_regex_fallback(query)
            # Run AST analyzer
            ast_res = analyze_query(query)

            regex_issues = {item["code"] for item in regex_res["issues"]}
            ast_issues = {item["code"] for item in ast_res["issues"]}

            regex_warns = {item["code"] for item in regex_res["warnings"]}
            ast_warns = {item["code"] for item in ast_res["warnings"]}

            diff_issues = regex_issues ^ ast_issues
            diff_warns = regex_warns ^ ast_warns
            diff_complexity = (regex_res["complexity"] != ast_res["complexity"])

            if diff_issues or diff_warns or diff_complexity:
                differences.append({
                    "row": i,
                    "name": row.get("name", f"Query #{i}"),
                    "query": query,
                    "regex_issues": sorted(list(regex_issues)),
                    "ast_issues": sorted(list(ast_issues)),
                    "regex_warns": sorted(list(regex_warns)),
                    "ast_warns": sorted(list(ast_warns)),
                    "regex_complexity": regex_res["complexity"],
                    "ast_complexity": ast_res["complexity"],
                })

    print(f"============================================================")
    print(f"GOLDEN COMPARISON REPORT: AST vs REGEX ({total} queries)")
    print(f"============================================================")
    print(f"Total queries analyzed: {total}")
    print(f"Identical pattern detections: {total - len(differences)}")
    print(f"Queries with pattern differences: {len(differences)}")
    print(f"------------------------------------------------------------\n")

    for d in differences:
        print(f"Query #{d['row']}: {d['name']}")
        print(f"  SQL: {d['query']}")
        print(f"  Regex Issues:     {d['regex_issues']}")
        print(f"  AST Issues:       {d['ast_issues']}")
        print(f"  Regex Warnings:   {d['regex_warns']}")
        print(f"  AST Warnings:     {d['ast_warns']}")
        print(f"  Complexity:       Regex={d['regex_complexity']} vs AST={d['ast_complexity']}")
        print("")


if __name__ == "__main__":
    main()
