/**
 * frontend/src/pages/ScorePage.tsx
 * QA Test Page for POST /api/score endpoint.
 */

import React, { useState } from "react";
import { extractErrorMessage, scoreQuery } from "../api/client";
import type { ScoreResponse } from "../api/types";
import { ErrorBanner } from "../components/ErrorBanner";
import { QueryInput } from "../components/QueryInput";
import { ResultPanel } from "../components/ResultPanel";
import { StatusBadge } from "../components/StatusBadge";

export const ScorePage: React.FC = () => {
  const [query, setQuery] = useState("SELECT * FROM orders WHERE customer_id = 42;");
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<ScoreResponse | null>(null);
  const [errorInfo, setErrorInfo] = useState<{ message: string; status?: number; detail?: any } | null>(null);

  const handleRun = async () => {
    setLoading(true);
    setErrorInfo(null);
    setData(null);

    try {
      const res = await scoreQuery(query);
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
        <h2 style={{ margin: "0 0 4px 0", color: "#e6edf3" }}>📊 Performance Scoring (POST /api/score)</h2>
        <p style={{ margin: 0, color: "#8b949e", fontSize: "0.9rem" }}>
          Exercises deterministic 0–100 scoring math, cost classification, and penalty deduction waterfall.
        </p>
      </div>

      <QueryInput
        query={query}
        onChange={setQuery}
        onRun={handleRun}
        loading={loading}
        runLabel="Calculate Score"
      />

      <ErrorBanner
        error={errorInfo?.message || null}
        status={errorInfo?.status}
        detail={errorInfo?.detail}
        onDismiss={() => setErrorInfo(null)}
      />

      {data && (
        <ResultPanel title={`Performance Score: ${data.score} / 100`} rawData={data}>
          {/* Summary KPIs */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
              gap: "12px",
              marginBottom: "20px",
            }}
          >
            <div style={{ backgroundColor: "#0d1117", padding: "14px", borderRadius: "6px", border: "1px solid #30363d" }}>
              <div style={{ fontSize: "0.8rem", color: "#8b949e" }}>SCORE</div>
              <div
                style={{
                  fontSize: "2rem",
                  fontWeight: "bold",
                  color: data.score >= 80 ? "#2ecc71" : data.score >= 50 ? "#f39c12" : "#e74c3c",
                }}
              >
                {data.score} / 100
              </div>
            </div>

            <div style={{ backgroundColor: "#0d1117", padding: "14px", borderRadius: "6px", border: "1px solid #30363d" }}>
              <div style={{ fontSize: "0.8rem", color: "#8b949e" }}>COST ESTIMATE</div>
              <div style={{ fontSize: "1.4rem", fontWeight: "bold", color: "#e6edf3", marginTop: "4px" }}>
                {data.cost_estimate}
              </div>
              <div style={{ fontSize: "0.75rem", color: "#8b949e" }}>Rows Scan: {data.rows_scanned_estimate}</div>
            </div>

            <div style={{ backgroundColor: "#0d1117", padding: "14px", borderRadius: "6px", border: "1px solid #30363d" }}>
              <div style={{ fontSize: "0.8rem", color: "#8b949e" }}>COMPLEXITY TIER</div>
              <div style={{ fontSize: "1.4rem", fontWeight: "bold", color: "#58a6ff", marginTop: "4px" }}>
                {data.complexity}
              </div>
            </div>

            <div style={{ backgroundColor: "#0d1117", padding: "14px", borderRadius: "6px", border: "1px solid #30363d" }}>
              <div style={{ fontSize: "0.8rem", color: "#8b949e" }}>CARDINALITY MULTIPLIER</div>
              <div style={{ fontSize: "1.4rem", fontWeight: "bold", color: "#adbac7", marginTop: "4px" }}>
                {data.table_multiplier}x
              </div>
            </div>
          </div>

          {/* Deduction Breakdown Waterfall */}
          <div>
            <h4 style={{ margin: "0 0 10px 0", color: "#e6edf3" }}>📉 Deduction Waterfall Breakdown</h4>
            {data.breakdown.length === 0 ? (
              <div style={{ color: "#3fb950", backgroundColor: "#0e3a24", padding: "10px", borderRadius: "6px" }}>
                ✓ No penalties applied. Base score is 100/100.
              </div>
            ) : (
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.85rem", marginTop: "8px" }}>
                <thead>
                  <tr style={{ borderBottom: "1px solid #30363d", textAlign: "left", color: "#8b949e" }}>
                    <th style={{ padding: "8px" }}>Rule Code</th>
                    <th style={{ padding: "8px" }}>Deduction</th>
                    <th style={{ padding: "8px" }}>Severity</th>
                    <th style={{ padding: "8px" }}>Explanation</th>
                  </tr>
                </thead>
                <tbody>
                  {data.breakdown.map((item, idx) => (
                    <tr key={idx} style={{ borderBottom: "1px solid #21262d" }}>
                      <td style={{ padding: "8px", fontFamily: "monospace", color: "#f85149" }}>{item.code}</td>
                      <td style={{ padding: "8px", fontWeight: "bold", color: item.delta < 0 ? "#f85149" : "#3fb950" }}>
                        {item.delta > 0 ? `+${item.delta}` : item.delta}
                      </td>
                      <td style={{ padding: "8px" }}>
                        <StatusBadge
                          text={item.severity}
                          variant={item.severity === "CRITICAL" || item.severity === "HIGH" ? "danger" : "warning"}
                          size="sm"
                        />
                      </td>
                      <td style={{ padding: "8px", color: "#c9d1d9" }}>{item.explanation || item.label}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </ResultPanel>
      )}
    </div>
  );
};
