/**
 * frontend/src/pages/HealthPage.tsx
 * QA Test Page for GET /api/health endpoint.
 */

import React, { useEffect, useState } from "react";
import { extractErrorMessage, fetchHealth, getBaseUrl } from "../api/client";
import type { HealthResponse } from "../api/types";
import { ErrorBanner } from "../components/ErrorBanner";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { ResultPanel } from "../components/ResultPanel";
import { StatusBadge } from "../components/StatusBadge";

export const HealthPage: React.FC = () => {
  const [data, setData] = useState<HealthResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [latencyMs, setLatencyMs] = useState<number | null>(null);
  const [errorInfo, setErrorInfo] = useState<{ message: string; status?: number; detail?: any } | null>(null);

  const checkHealth = async () => {
    setLoading(true);
    setErrorInfo(null);
    const start = performance.now();
    try {
      const res = await fetchHealth();
      const end = performance.now();
      setLatencyMs(Math.round(end - start));
      setData(res);
    } catch (err) {
      setErrorInfo(extractErrorMessage(err));
      setData(null);
      setLatencyMs(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    checkHealth();
  }, []);

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
        <div>
          <h2 style={{ margin: "0 0 4px 0", color: "#e6edf3" }}>🩺 System Health & Connectivity (GET /api/health)</h2>
          <p style={{ margin: 0, color: "#8b949e", fontSize: "0.9rem" }}>
            Tests backend liveness probe, network round-trip latency, and API semantic versioning.
          </p>
        </div>
        <button
          type="button"
          onClick={checkHealth}
          disabled={loading}
          style={{
            backgroundColor: "#238636",
            border: "1px solid #2ea043",
            color: "#ffffff",
            padding: "6px 14px",
            borderRadius: "6px",
            cursor: loading ? "not-allowed" : "pointer",
            fontSize: "0.85rem",
            fontWeight: 600,
          }}
        >
          {loading ? <LoadingSpinner label="Pinging..." size={14} /> : "⚡ Ping Now"}
        </button>
      </div>

      <ErrorBanner
        error={errorInfo?.message || null}
        status={errorInfo?.status}
        detail={errorInfo?.detail}
        onDismiss={() => setErrorInfo(null)}
      />

      <ResultPanel title="Health Probe Report" rawData={data}>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
            gap: "12px",
            marginBottom: "16px",
          }}
        >
          <div style={{ backgroundColor: "#0d1117", padding: "14px", borderRadius: "6px", border: "1px solid #30363d" }}>
            <div style={{ fontSize: "0.8rem", color: "#8b949e" }}>SERVICE STATUS</div>
            <div style={{ fontSize: "1.4rem", fontWeight: "bold", marginTop: "4px" }}>
              <StatusBadge
                text={data ? data.status.toUpperCase() : errorInfo ? "OFFLINE" : "CHECKING"}
                variant={data ? "success" : "danger"}
              />
            </div>
          </div>

          <div style={{ backgroundColor: "#0d1117", padding: "14px", borderRadius: "6px", border: "1px solid #30363d" }}>
            <div style={{ fontSize: "0.8rem", color: "#8b949e" }}>ROUND-TRIP LATENCY</div>
            <div
              style={{
                fontSize: "1.4rem",
                fontWeight: "bold",
                color: latencyMs && latencyMs < 50 ? "#2ecc71" : latencyMs ? "#f39c12" : "#8b949e",
                marginTop: "4px",
              }}
            >
              {latencyMs !== null ? `${latencyMs} ms` : "N/A"}
            </div>
          </div>

          <div style={{ backgroundColor: "#0d1117", padding: "14px", borderRadius: "6px", border: "1px solid #30363d" }}>
            <div style={{ fontSize: "0.8rem", color: "#8b949e" }}>API VERSION</div>
            <div style={{ fontSize: "1.4rem", fontWeight: "bold", color: "#58a6ff", marginTop: "4px" }}>
              {data?.version || "N/A"}
            </div>
          </div>

          <div style={{ backgroundColor: "#0d1117", padding: "14px", borderRadius: "6px", border: "1px solid #30363d" }}>
            <div style={{ fontSize: "0.8rem", color: "#8b949e" }}>TARGET BASE URL</div>
            <div style={{ fontSize: "0.95rem", fontFamily: "monospace", color: "#c9d1d9", marginTop: "8px" }}>
              {getBaseUrl()}
            </div>
          </div>
        </div>
      </ResultPanel>
    </div>
  );
};
