/**
 * frontend/src/pages/RewritePage.tsx
 * QA Test Page for POST /api/rewrite endpoint.
 */

import React, { useState } from "react";
import { extractErrorMessage, rewriteQuery } from "../api/client";
import type { RewriteResponse } from "../api/types";
import { ErrorBanner } from "../components/ErrorBanner";
import { QueryInput } from "../components/QueryInput";
import { ResultPanel } from "../components/ResultPanel";
import { StatusBadge } from "../components/StatusBadge";

export const RewritePage: React.FC = () => {
  const [query, setQuery] = useState("SELECT * FROM orders WHERE YEAR(order_date) = 2024;");
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<RewriteResponse | null>(null);
  const [errorInfo, setErrorInfo] = useState<{ message: string; status?: number; detail?: any } | null>(null);

  const handleRun = async () => {
    setLoading(true);
    setErrorInfo(null);
    setData(null);

    try {
      const res = await rewriteQuery(query);
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
        <h2 style={{ margin: "0 0 4px 0", color: "#e6edf3" }}>🔄 AST Query Rewriter (POST /api/rewrite)</h2>
        <p style={{ margin: 0, color: "#8b949e", fontSize: "0.9rem" }}>
          Exercises automated AST transformations (sargable range bounds, projection cuts, LIMIT injection) and semantic validation.
        </p>
      </div>

      <QueryInput
        query={query}
        onChange={setQuery}
        onRun={handleRun}
        loading={loading}
        runLabel="Rewrite Query"
      />

      <ErrorBanner
        error={errorInfo?.message || null}
        status={errorInfo?.status}
        detail={errorInfo?.detail}
        onDismiss={() => setErrorInfo(null)}
      />

      {data && (
        <ResultPanel title={`Rewrite Result: ${data.is_changed ? "Transformed" : "No Changes Needed"}`} rawData={data}>
          {/* Header Summary & Validation Badge */}
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
              <StatusBadge
                text={data.is_changed ? "QUERY REWRITTEN" : "IDENTICAL"}
                variant={data.is_changed ? "success" : "neutral"}
              />
              <span style={{ fontSize: "0.85rem", color: "#8b949e" }}>
                Estimated Score Boost: +{data.rewrite_score_est} pts
              </span>
            </div>
            {data.validation && (
              <div
                style={{
                  padding: "4px 10px",
                  borderRadius: "12px",
                  fontSize: "0.8rem",
                  fontWeight: 600,
                  backgroundColor: data.validation.badge_color ? `${data.validation.badge_color}22` : "#21262d",
                  border: `1px solid ${data.validation.badge_color || "#30363d"}`,
                  color: data.validation.badge_color || "#e6edf3",
                }}
              >
                🛡️ {data.validation.level || "Validation Checked"}
              </div>
            )}
          </div>

          {/* Side-by-side SQL View */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px", marginBottom: "20px" }}>
            {/* Original SQL */}
            <div>
              <div style={{ fontSize: "0.8rem", fontWeight: "bold", color: "#8b949e", marginBottom: "4px" }}>
                BEFORE (ORIGINAL)
              </div>
              <pre
                style={{
                  backgroundColor: "#0d1117",
                  border: "1px solid #30363d",
                  borderLeft: "4px solid #f85149",
                  padding: "12px",
                  borderRadius: "6px",
                  fontFamily: "monospace",
                  fontSize: "0.85rem",
                  color: "#e6edf3",
                  margin: 0,
                  whiteSpace: "pre-wrap",
                  minHeight: "100px",
                }}
              >
                {data.original}
              </pre>
            </div>

            {/* Rewritten SQL */}
            <div>
              <div style={{ fontSize: "0.8rem", fontWeight: "bold", color: "#8b949e", marginBottom: "4px" }}>
                AFTER (OPTIMIZED)
              </div>
              <pre
                style={{
                  backgroundColor: "#0d1117",
                  border: "1px solid #30363d",
                  borderLeft: "4px solid #3fb950",
                  padding: "12px",
                  borderRadius: "6px",
                  fontFamily: "monospace",
                  fontSize: "0.85rem",
                  color: "#3fb950",
                  margin: 0,
                  whiteSpace: "pre-wrap",
                  minHeight: "100px",
                }}
              >
                {data.rewritten}
              </pre>
            </div>
          </div>

          {/* Applied Rules */}
          {data.changes.length > 0 && (
            <div>
              <h4 style={{ margin: "0 0 8px 0", color: "#e6edf3" }}>🛠️ Applied Transformations</h4>
              <ul style={{ margin: 0, paddingLeft: "20px", color: "#c9d1d9", fontSize: "0.85rem" }}>
                {data.changes.map((change, idx) => (
                  <li key={idx} style={{ marginBottom: "4px" }}>
                    {change}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </ResultPanel>
      )}
    </div>
  );
};
