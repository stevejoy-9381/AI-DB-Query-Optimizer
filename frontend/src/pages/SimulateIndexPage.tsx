/**
 * frontend/src/pages/SimulateIndexPage.tsx
 * QA Test Page for POST /api/simulate-index endpoint.
 */

import React, { useState } from "react";
import { extractErrorMessage, simulateIndex } from "../api/client";
import type { SimulateIndexResponse } from "../api/types";
import { ErrorBanner } from "../components/ErrorBanner";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { ResultPanel } from "../components/ResultPanel";
import { StatusBadge } from "../components/StatusBadge";

export const SimulateIndexPage: React.FC = () => {
  const [query, setQuery] = useState("SELECT * FROM orders WHERE customer_id = 42;");
  const [indexDdl, setIndexDdl] = useState("CREATE INDEX idx_orders_customer_id ON orders(customer_id);");
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<SimulateIndexResponse | null>(null);
  const [errorInfo, setErrorInfo] = useState<{ message: string; status?: number; detail?: any } | null>(null);

  const handleRun = async () => {
    setLoading(true);
    setErrorInfo(null);
    setData(null);

    try {
      const res = await simulateIndex(query, indexDdl);
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
        <h2 style={{ margin: "0 0 4px 0", color: "#e6edf3" }}>🧪 Index Impact Simulator (POST /api/simulate-index)</h2>
        <p style={{ margin: 0, color: "#8b949e", fontSize: "0.9rem" }}>
          Simulates mathematical performance projection (latency delta, row scan drops, speedup factor) before and after creating an index.
        </p>
      </div>

      {/* Two-Field Form */}
      <div style={{ display: "flex", flexDirection: "column", gap: "12px", margin: "16px 0" }}>
        <div>
          <label style={{ display: "block", fontSize: "0.85rem", color: "#8b949e", marginBottom: "4px", fontWeight: 600 }}>
            Target Query:
          </label>
          <textarea
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            rows={3}
            style={{
              width: "100%",
              boxSizing: "border-box",
              backgroundColor: "#0d1117",
              border: "1px solid #30363d",
              borderRadius: "6px",
              color: "#e6edf3",
              fontFamily: "monospace",
              fontSize: "0.85rem",
              padding: "10px",
            }}
          />
        </div>

        <div>
          <label style={{ display: "block", fontSize: "0.85rem", color: "#8b949e", marginBottom: "4px", fontWeight: 600 }}>
            Index Definition / DDL to Simulate:
          </label>
          <input
            type="text"
            value={indexDdl}
            onChange={(e) => setIndexDdl(e.target.value)}
            style={{
              width: "100%",
              boxSizing: "border-box",
              backgroundColor: "#0d1117",
              border: "1px solid #30363d",
              borderRadius: "6px",
              color: "#3fb950",
              fontFamily: "monospace",
              fontSize: "0.85rem",
              padding: "10px",
            }}
          />
        </div>

        <div>
          <button
            type="button"
            onClick={handleRun}
            disabled={loading}
            style={{
              backgroundColor: loading ? "#238636aa" : "#238636",
              border: "1px solid #2ea043",
              color: "#ffffff",
              padding: "8px 20px",
              borderRadius: "6px",
              fontWeight: 600,
              cursor: loading ? "not-allowed" : "pointer",
              fontSize: "0.95rem",
              display: "inline-flex",
              alignItems: "center",
              gap: "8px",
            }}
          >
            {loading ? <LoadingSpinner label="Simulating..." size={16} /> : "▶ Simulate Impact"}
          </button>
        </div>
      </div>

      <ErrorBanner
        error={errorInfo?.message || null}
        status={errorInfo?.status}
        detail={errorInfo?.detail}
        onDismiss={() => setErrorInfo(null)}
      />

      {data && (
        <ResultPanel title="Simulation Projection" rawData={data}>
          {/* Summary KPIs */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
              gap: "12px",
              marginBottom: "20px",
            }}
          >
            <div style={{ backgroundColor: "#0d1117", padding: "14px", borderRadius: "6px", border: "1px solid #30363d" }}>
              <div style={{ fontSize: "0.8rem", color: "#8b949e" }}>SPEEDUP FACTOR</div>
              <div style={{ fontSize: "2rem", fontWeight: "bold", color: "#2ecc71" }}>
                {data.simulation.speedup_label || `${data.simulation.speedup_factor}x`}
              </div>
              <div style={{ fontSize: "0.75rem", color: "#8b949e" }}>Impact: {data.simulation.impact_level}</div>
            </div>

            <div style={{ backgroundColor: "#0d1117", padding: "14px", borderRadius: "6px", border: "1px solid #30363d" }}>
              <div style={{ fontSize: "0.8rem", color: "#8b949e" }}>SCORE PROJECTION</div>
              <div style={{ fontSize: "1.4rem", fontWeight: "bold", color: "#e6edf3", marginTop: "4px" }}>
                {data.simulation.before_score} → <span style={{ color: "#3fb950" }}>{data.simulation.after_score}</span>
              </div>
              <div style={{ fontSize: "0.75rem", color: "#3fb950" }}>+{data.simulation.score_improvement} points</div>
            </div>

            <div style={{ backgroundColor: "#0d1117", padding: "14px", borderRadius: "6px", border: "1px solid #30363d" }}>
              <div style={{ fontSize: "0.8rem", color: "#8b949e" }}>ESTIMATED ROWS SCANNED</div>
              <div style={{ fontSize: "1.4rem", fontWeight: "bold", color: "#e6edf3", marginTop: "4px" }}>
                {data.simulation.before_rows.toLocaleString()} → <span style={{ color: "#58a6ff" }}>{data.simulation.after_rows.toLocaleString()}</span>
              </div>
              <div style={{ fontSize: "0.75rem", color: "#58a6ff" }}>
                {data.simulation.rows_reduction_pct}% reduction
              </div>
            </div>

            <div style={{ backgroundColor: "#0d1117", padding: "14px", borderRadius: "6px", border: "1px solid #30363d" }}>
              <div style={{ fontSize: "0.8rem", color: "#8b949e" }}>ESTIMATED LATENCY</div>
              <div style={{ fontSize: "1.4rem", fontWeight: "bold", color: "#e6edf3", marginTop: "4px" }}>
                {data.simulation.before_time_ms.toFixed(1)} ms → <span style={{ color: "#2ecc71" }}>{data.simulation.after_time_ms.toFixed(2)} ms</span>
              </div>
            </div>
          </div>

          <div>
            <span style={{ fontSize: "0.85rem", color: "#8b949e" }}>Simulated Index: </span>
            <StatusBadge text={data.index} variant="info" />
          </div>
        </ResultPanel>
      )}
    </div>
  );
};
