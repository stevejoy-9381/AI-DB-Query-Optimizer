/**
 * frontend/src/pages/ExecutionPlanPage.tsx
 * QA Test Page for POST /api/execution-plan endpoint.
 */

import React, { useState } from "react";
import { extractErrorMessage, getExecutionPlan } from "../api/client";
import type { ExecutionPlanResponse, PlanNode } from "../api/types";
import { ErrorBanner } from "../components/ErrorBanner";
import { QueryInput } from "../components/QueryInput";
import { ResultPanel } from "../components/ResultPanel";
import { StatusBadge } from "../components/StatusBadge";

export const ExecutionPlanPage: React.FC = () => {
  const [query, setQuery] = useState(
    "SELECT c.name, o.id, o.total_amount FROM customers c JOIN orders o ON c.id = o.customer_id WHERE o.status = 'PENDING';"
  );
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<ExecutionPlanResponse | null>(null);
  const [errorInfo, setErrorInfo] = useState<{ message: string; status?: number; detail?: any } | null>(null);

  const handleRun = async () => {
    setLoading(true);
    setErrorInfo(null);
    setData(null);

    try {
      const res = await getExecutionPlan(query);
      setData(res);
    } catch (err) {
      setErrorInfo(extractErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  const renderNodeTree = (node: PlanNode, depth = 0) => {
    const isScan = node.node_type.includes("Scan") || node.access_type === "ALL";
    const isIndex = node.node_type.includes("Index") || node.access_type === "ref" || node.access_type === "range";

    return (
      <div key={`${node.node_type}-${depth}-${Math.random()}`} style={{ marginLeft: `${depth * 24}px`, marginBottom: "8px" }}>
        <div
          style={{
            backgroundColor: "#0d1117",
            border: "1px solid #30363d",
            borderLeft: `4px solid ${isScan ? "#f85149" : isIndex ? "#2ecc71" : "#58a6ff"}`,
            padding: "8px 12px",
            borderRadius: "4px",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <span style={{ fontSize: "1.1rem" }}>{node.icon || "⚙️"}</span>
            <span style={{ fontWeight: 600, color: "#e6edf3" }}>{node.node_type}</span>
            {node.table && <span style={{ color: "#8b949e", fontSize: "0.8rem" }}>on `{node.table}`</span>}
            {node.access_type && <StatusBadge text={node.access_type} variant={isScan ? "danger" : "success"} size="sm" />}
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: "10px", fontSize: "0.8rem", color: "#8b949e" }}>
            <span>Est. Rows: <strong style={{ color: "#c9d1d9" }}>{node.estimated_rows.toLocaleString()}</strong></span>
            <span>Cost: <strong style={{ color: "#f39c12" }}>{node.total_cost.toFixed(2)}</strong></span>
          </div>
        </div>
        {node.children && node.children.map((child) => renderNodeTree(child, depth + 1))}
      </div>
    );
  };

  return (
    <div>
      <div style={{ marginBottom: "16px" }}>
        <h2 style={{ margin: "0 0 4px 0", color: "#e6edf3" }}>🌳 Execution Plan Visualizer (POST /api/execution-plan)</h2>
        <p style={{ margin: 0, color: "#8b949e", fontSize: "0.9rem" }}>
          Simulates MySQL 8.x InnoDB cost-based execution plan trees, access types (ALL, ref, range), and filesort stages.
        </p>
      </div>

      <QueryInput
        query={query}
        onChange={setQuery}
        onRun={handleRun}
        loading={loading}
        runLabel="Generate Plan"
      />

      <ErrorBanner
        error={errorInfo?.message || null}
        status={errorInfo?.status}
        detail={errorInfo?.detail}
        onDismiss={() => setErrorInfo(null)}
      />

      {data && (
        <ResultPanel title="Simulated MySQL Execution Plan Tree" rawData={data}>
          {/* Summary Badges */}
          <div style={{ display: "flex", flexWrap: "wrap", gap: "8px", marginBottom: "16px" }}>
            <StatusBadge text={`Total Cost: ${data.summary.total_cost?.toFixed(2) || "N/A"}`} variant="warning" />
            <StatusBadge text={`Total Nodes: ${data.summary.total_nodes || data.flattened_nodes.length}`} variant="info" />
            <StatusBadge text={`Max Depth: ${data.summary.max_depth || "N/A"}`} variant="neutral" />
            <StatusBadge
              text={`Full Table Scan: ${data.summary.has_full_scan ? "Detected" : "None"}`}
              variant={data.summary.has_full_scan ? "danger" : "success"}
            />
            <StatusBadge
              text={`Filesort: ${data.summary.has_filesort ? "Detected" : "None"}`}
              variant={data.summary.has_filesort ? "warning" : "success"}
            />
          </div>

          {/* Tree Structure */}
          <div>
            <h4 style={{ margin: "0 0 10px 0", color: "#e6edf3" }}>Execution Tree Flow</h4>
            {data.plan_root ? renderNodeTree(data.plan_root) : <div>No plan nodes generated.</div>}
          </div>
        </ResultPanel>
      )}
    </div>
  );
};
