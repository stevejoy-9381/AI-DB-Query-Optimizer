import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from analyzer import analyze_query
from history_store import HistoryStore
from scoring import compute_score

hs = HistoryStore()
samples = [
    ("SELECT * FROM orders WHERE customer_id = 42;", "O(n)"),
    ("SELECT * FROM customers WHERE email LIKE '%@gmail.com';", "O(n)"),
    ("SELECT id, name FROM customers WHERE id = 1050;", "O(1)"),
    ("SELECT * FROM orders WHERE YEAR(order_date) = 2024 ORDER BY order_date DESC;", "O(n log n)"),
]

for q, cplx in samples:
    analysis = analyze_query(q)
    score_res = compute_score(analysis)
    hs.add(
        query=q,
        score=score_res.total,
        report_dict={"score": score_res.total, "complexity": cplx},
        statement_type="SELECT",
        complexity=cplx,
        cost=score_res.cost_estimate,
        dialect="mysql",
        mode="offline",
        source_badges="Rule-based",
    )

print(f"Seeded history successfully! Total records: {hs.count()}")
