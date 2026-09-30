/**
 * frontend/src/pages/SampleQueriesPage.tsx
 * QA Test Page for GET /api/sample-queries endpoint.
 */

import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { extractErrorMessage, fetchSampleQueries } from "../api/client";
import type { SampleQueryItem } from "../api/types";
import { ErrorBanner } from "../components/ErrorBanner";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { ResultPanel } from "../components/ResultPanel";
import { StatusBadge } from "../components/StatusBadge";

export const SampleQueriesPage: React.FC = () => {
  const navigate = useNavigate();
  const [queries, setQueries] = useState<SampleQueryItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [filter, setFilter] = useState("");
  const [errorInfo, setErrorInfo] = useState<{ message: string; status?: number; detail?: any } | null>(null);

  const loadData = async () => {
    setLoading(true);
    setErrorInfo(null);
    try {
      const data = await fetchSampleQueries();
      setQueries(data);
    } catch (err) {
      setErrorInfo(extractErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const filteredQueries = queries.filter(
    (q) =>
      q.query.toLowerCase().includes(filter.toLowerCase()) ||
      q.description.toLowerCase().includes(filter.toLowerCase()) ||
      q.category.toLowerCase().includes(filter.toLowerCase())
  );

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
        <div>
          <h2 style={{ margin: "0 0 4px 0", color: "#e6edf3" }}>📁 Sample Queries Catalog (GET /api/sample-queries)</h2>
          <p style={{ margin: 0, color: "#8b949e", fontSize: "0.9rem" }}>
            Loads preloaded benchmark catalog from CSV dataset for instant test regression.
          </p>
        </div>
        <button
          type="button"
          onClick={loadData}
          disabled={loading}
          style={{
            backgroundColor: "#21262d",
            border: "1px solid #30363d",
            color: "#c9d1d9",
            padding: "6px 14px",
            borderRadius: "6px",
            cursor: loading ? "not-allowed" : "pointer",
            fontSize: "0.85rem",
          }}
        >
          {loading ? <LoadingSpinner label="Refreshing..." size={14} /> : "🔄 Reload Dataset"}
        </button>
      </div>

      <ErrorBanner
        error={errorInfo?.message || null}
        status={errorInfo?.status}
        detail={errorInfo?.detail}
        onDismiss={() => setErrorInfo(null)}
      />

      {/* Filter Bar */}
      <div style={{ marginBottom: "16px" }}>
        <input
          type="text"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="Filter sample queries by text, category, or table name..."
          style={{
            width: "100%",
            boxSizing: "border-box",
            backgroundColor: "#0d1117",
            border: "1px solid #30363d",
            borderRadius: "6px",
            color: "#e6edf3",
            padding: "10px",
            fontSize: "0.85rem",
          }}
        />
      </div>

      {loading ? (
        <div style={{ textAlign: "center", padding: "40px" }}>
          <LoadingSpinner label="Fetching sample queries from backend..." size={28} />
        </div>
      ) : (
        <ResultPanel title={`Catalog (${filteredQueries.length} of ${queries.length} Queries)`} rawData={queries}>
          <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
            {filteredQueries.map((item, idx) => (
              <div
                key={idx}
                style={{
                  backgroundColor: "#0d1117",
                  border: "1px solid #30363d",
                  borderRadius: "6px",
                  padding: "12px 16px",
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  gap: "16px",
                }}
              >
                <div style={{ flex: 1 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "4px" }}>
                    <StatusBadge
                      text={item.category}
                      variant={
                        item.category.toLowerCase().includes("anti")
                          ? "danger"
                          : item.category.toLowerCase().includes("mod")
                          ? "warning"
                          : "success"
                      }
                      size="sm"
                    />
                    <span style={{ fontSize: "0.85rem", color: "#8b949e" }}>{item.description}</span>
                  </div>
                  <pre
                    style={{
                      margin: 0,
                      fontFamily: "monospace",
                      fontSize: "0.85rem",
                      color: "#e6edf3",
                      backgroundColor: "#161b22",
                      padding: "6px 8px",
                      borderRadius: "4px",
                      overflowX: "auto",
                    }}
                  >
                    {item.query}
                  </pre>
                </div>

                <div style={{ display: "flex", gap: "8px" }}>
                  <button
                    type="button"
                    onClick={() => {
                      navigator.clipboard.writeText(item.query);
                      alert("Query copied to clipboard!");
                    }}
                    style={{
                      backgroundColor: "#21262d",
                      border: "1px solid #30363d",
                      color: "#c9d1d9",
                      padding: "4px 8px",
                      borderRadius: "4px",
                      fontSize: "0.75rem",
                      cursor: "pointer",
                      whiteSpace: "nowrap",
                    }}
                  >
                    📋 Copy
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      navigate("/", { state: { preloadedQuery: item.query } });
                    }}
                    style={{
                      backgroundColor: "#1f6feb",
                      border: "1px solid #388bfd",
                      color: "#ffffff",
                      padding: "4px 8px",
                      borderRadius: "4px",
                      fontSize: "0.75rem",
                      cursor: "pointer",
                      whiteSpace: "nowrap",
                      fontWeight: 600,
                    }}
                  >
                    ⚡ Test in Analyze
                  </button>
                </div>
              </div>
            ))}
          </div>
        </ResultPanel>
      )}
    </div>
  );
};
