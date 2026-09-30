/**
 * frontend/src/pages/RecommendationsPage.tsx
 * QA Test Page for POST /api/recommendations endpoint.
 */

import React, { useState } from "react";
import { extractErrorMessage, getRecommendations } from "../api/client";
import type { RecommendationsResponse } from "../api/types";
import { ErrorBanner } from "../components/ErrorBanner";
import { QueryInput } from "../components/QueryInput";
import { ResultPanel } from "../components/ResultPanel";
import { StatusBadge } from "../components/StatusBadge";

export const RecommendationsPage: React.FC = () => {
  const [query, setQuery] = useState("SELECT * FROM orders WHERE customer_id = 42;");
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<RecommendationsResponse | null>(null);
  const [errorInfo, setErrorInfo] = useState<{ message: string; status?: number; detail?: any } | null>(null);

  const handleRun = async () => {
    setLoading(true);
    setErrorInfo(null);
    setData(null);

    try {
      const res = await getRecommendations(query);
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
        <h2 style={{ margin: "0 0 4px 0", color: "#e6edf3" }}>💡 Index Recommendations (POST /api/recommendations)</h2>
        <p style={{ margin: 0, color: "#8b949e", fontSize: "0.9rem" }}>
          Tests MySQL 8.x index generation: composite indexes (equality first), covering indexes, and DDL syntax.
        </p>
      </div>

      <QueryInput
        query={query}
        onChange={setQuery}
        onRun={handleRun}
        loading={loading}
        runLabel="Get Index Advice"
      />

      <ErrorBanner
        error={errorInfo?.message || null}
        status={errorInfo?.status}
        detail={errorInfo?.detail}
        onDismiss={() => setErrorInfo(null)}
      />

      {data && (
        <ResultPanel title={`Index Recommendations (${data.count} Generated)`} rawData={data}>
          {data.count === 0 ? (
            <div style={{ color: "#3fb950", backgroundColor: "#0e3a24", padding: "12px", borderRadius: "6px" }}>
              ✓ No secondary indexes required (query may already use clustered primary key or lacks filter columns).
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
              {data.recommendations.map((rec, idx) => (
                <div
                  key={idx}
                  style={{
                    backgroundColor: "#0d1117",
                    border: "1px solid #30363d",
                    borderRadius: "6px",
                    padding: "16px",
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                      <span style={{ fontWeight: "bold", color: "#58a6ff" }}>#{idx + 1}</span>
                      <StatusBadge text={rec.index_type || "Secondary Index"} variant="info" size="sm" />
                      {rec.table && <span style={{ color: "#8b949e", fontSize: "0.85rem" }}>Table: `{rec.table}`</span>}
                    </div>
                    {rec.priority && <StatusBadge text={rec.priority} variant={rec.priority === "HIGH" ? "danger" : "warning"} size="sm" />}
                  </div>

                  {/* DDL Code Box */}
                  <pre
                    style={{
                      backgroundColor: "#161b22",
                      border: "1px solid #30363d",
                      borderRadius: "4px",
                      padding: "10px",
                      fontFamily: "monospace",
                      color: "#3fb950",
                      fontSize: "0.85rem",
                      margin: "8px 0",
                      overflowX: "auto",
                    }}
                  >
                    {rec.ddl}
                  </pre>

                  {/* Rationale & Trade-offs */}
                  <div style={{ fontSize: "0.85rem", color: "#c9d1d9", marginTop: "6px" }}>
                    <strong>Reason:</strong> {rec.reason}
                  </div>
                  {rec.trade_offs && (
                    <div style={{ fontSize: "0.8rem", color: "#8b949e", marginTop: "4px" }}>
                      <strong>Trade-offs:</strong> {rec.trade_offs}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </ResultPanel>
      )}
    </div>
  );
};
