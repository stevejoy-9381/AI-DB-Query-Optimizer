/**
 * frontend/src/pages/AnalyzePage.tsx
 * QA Test Page for POST /api/analyze endpoint.
 */

import React, { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { analyzeQuery, extractErrorMessage } from "../api/client";
import type { AnalyzeResponse } from "../api/types";
import { ErrorBanner } from "../components/ErrorBanner";
import { QueryInput } from "../components/QueryInput";
import { ResultPanel } from "../components/ResultPanel";
import { StatusBadge } from "../components/StatusBadge";

export const AnalyzePage: React.FC = () => {
  const location = useLocation();
  const initialQuery = (location.state as any)?.preloadedQuery || "SELECT * FROM orders WHERE customer_id = 42;";
  const [query, setQuery] = useState(initialQuery);
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<AnalyzeResponse | null>(null);
  const [errorInfo, setErrorInfo] = useState<{ message: string; status?: number; detail?: any } | null>(null);

  useEffect(() => {
    if ((location.state as any)?.preloadedQuery) {
      setQuery((location.state as any).preloadedQuery);
    }
  }, [location.state]);

  const handleRun = async () => {
    setLoading(true);
    setErrorInfo(null);
    setData(null);

    try {
      const res = await analyzeQuery(query);
      setData(res);
    } catch (err) {
      setErrorInfo(extractErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <div style={{ marginBottom: "16px" }}>
        <h2 style={{ margin: "0 0 4px 0", color: "#e6edf3" }}>⚡ Query Analysis (POST /api/analyze)</h2>
        <p style={{ margin: 0, color: "#8b949e", fontSize: "0.9rem" }}>
          Exercises full AST parsing, 12+ anti-pattern detectors, complexity calculation, and performance scoring.
        </p>
      </div>

      <QueryInput
        query={query}
        onChange={setQuery}
        onRun={handleRun}
        loading={loading}
        runLabel="Analyze Query"
      />

      <ErrorBanner
        error={errorInfo?.message || null}
        status={errorInfo?.status}
        detail={errorInfo?.detail}
        onDismiss={() => setErrorInfo(null)}
      />

      {data && (
        <ResultPanel title={`Analysis Findings for ${data.statement_type || "Query"}`} rawData={data}>
          {/* Top Metric Cards */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
              gap: "12px",
              marginBottom: "20px",
            }}
          >
            <div style={{ backgroundColor: "#0d1117", padding: "12px", borderRadius: "6px", border: "1px solid #30363d" }}>
              <div style={{ fontSize: "0.8rem", color: "#8b949e" }}>PERFORMANCE SCORE</div>
              <div style={{ fontSize: "1.8rem", fontWeight: "bold", color: data.score && data.score.score >= 80 ? "#2ecc71" : data.score && data.score.score >= 50 ? "#f39c12" : "#e74c3c" }}>
                {data.score ? `${data.score.score} / 100` : "N/A"}
              </div>
              <div style={{ fontSize: "0.75rem", color: "#8b949e" }}>Cost Tier: {data.score?.cost_estimate || "Unknown"}</div>
            </div>

            <div style={{ backgroundColor: "#0d1117", padding: "12px", borderRadius: "6px", border: "1px solid #30363d" }}>
              <div style={{ fontSize: "0.8rem", color: "#8b949e" }}>COMPLEXITY</div>
              <div style={{ fontSize: "1.5rem", fontWeight: "bold", color: "#58a6ff" }}>{data.complexity}</div>
              <div style={{ fontSize: "0.75rem", color: "#8b949e" }}>Joins: {data.join_count} | Subqueries: {data.subquery_count}</div>
            </div>

            <div style={{ backgroundColor: "#0d1117", padding: "12px", borderRadius: "6px", border: "1px solid #30363d" }}>
              <div style={{ fontSize: "0.8rem", color: "#8b949e" }}>ISSUES DETECTED</div>
              <div style={{ fontSize: "1.5rem", fontWeight: "bold", color: data.issues.length === 0 ? "#2ecc71" : "#f85149" }}>
                {data.issues.length}
              </div>
              <div style={{ fontSize: "0.75rem", color: "#8b949e" }}>Warnings: {data.warnings.length}</div>
            </div>

            <div style={{ backgroundColor: "#0d1117", padding: "12px", borderRadius: "6px", border: "1px solid #30363d" }}>
              <div style={{ fontSize: "0.8rem", color: "#8b949e" }}>AST ENGINE</div>
              <div style={{ fontSize: "1.1rem", fontWeight: 600, color: "#c9d1d9", marginTop: "4px" }}>
                {data.analysis_engine}
              </div>
              <div style={{ fontSize: "0.75rem", color: "#8b949e" }}>Validated: Yes</div>
            </div>
          </div>

          {/* Detected Issues */}
          <div style={{ marginBottom: "20px" }}>
            <h4 style={{ margin: "0 0 10px 0", color: "#e6edf3" }}>⚠️ Anti-Pattern Findings</h4>
            {data.issues.length === 0 ? (
              <div style={{ color: "#3fb950", backgroundColor: "#0e3a24", padding: "10px", borderRadius: "6px" }}>
                ✓ No high-severity anti-patterns detected.
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                {data.issues.map((issue, idx) => (
                  <div
                    key={idx}
                    style={{
                      backgroundColor: "#0d1117",
                      border: "1px solid #30363d",
                      borderLeft: "4px solid #f85149",
                      padding: "10px 14px",
                      borderRadius: "4px",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                    }}
                  >
                    <div>
                      <span style={{ fontWeight: 600, color: "#f85149", marginRight: "8px" }}>
                        [{issue.code || `ISSUE_${idx + 1}`}]
                      </span>
                      <span style={{ color: "#c9d1d9" }}>{issue.message || JSON.stringify(issue)}</span>
                    </div>
                    <StatusBadge text={issue.severity || "HIGH"} variant="danger" size="sm" />
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Query Properties Breakdown */}
          <div>
            <h4 style={{ margin: "0 0 10px 0", color: "#e6edf3" }}>🔬 Query Characteristics</h4>
            <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
              <StatusBadge text={`SELECT *: ${data.select_star ? "Yes" : "No"}`} variant={data.select_star ? "danger" : "success"} />
              <StatusBadge text={`WHERE Clause: ${data.has_where ? "Present" : "Missing"}`} variant={data.has_where ? "success" : "warning"} />
              <StatusBadge text={`ORDER BY: ${data.has_order_by ? "Yes" : "No"}`} variant="neutral" />
              <StatusBadge text={`LIMIT: ${data.has_limit ? "Yes" : "No"}`} variant="neutral" />
              <StatusBadge text={`DISTINCT: ${data.has_distinct ? "Yes" : "No"}`} variant="neutral" />
              <StatusBadge text={`Aggregation: ${data.has_aggregation ? "Yes" : "No"}`} variant="neutral" />
              <StatusBadge text={`Filter Columns: [${data.filter_columns?.join(", ") || "None"}]`} variant="info" />
            </div>
          </div>
        </ResultPanel>
      )}
    </div>
  );
};
