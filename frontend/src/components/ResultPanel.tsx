/**
 * frontend/src/components/ResultPanel.tsx
 * Structured result presentation container with collapsible raw JSON viewer and copy button.
 */

import React, { useState } from "react";

interface Props {
  title: string;
  children: React.ReactNode;
  rawData?: any;
}

export const ResultPanel: React.FC<Props> = ({ title, children, rawData }) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    if (!rawData) return;
    navigator.clipboard.writeText(JSON.stringify(rawData, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div
      style={{
        backgroundColor: "#161b22",
        border: "1px solid #30363d",
        borderRadius: "8px",
        padding: "20px",
        margin: "16px 0",
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          borderBottom: "1px solid #30363d",
          paddingBottom: "12px",
          marginBottom: "16px",
        }}
      >
        <h3 style={{ margin: 0, fontSize: "1.1rem", color: "#e6edf3" }}>{title}</h3>
        {rawData !== undefined && (
          <button
            type="button"
            onClick={handleCopy}
            style={{
              backgroundColor: "#21262d",
              border: "1px solid #30363d",
              color: copied ? "#3fb950" : "#c9d1d9",
              padding: "4px 10px",
              borderRadius: "4px",
              fontSize: "0.8rem",
              cursor: "pointer",
            }}
          >
            {copied ? "✓ Copied JSON" : "📋 Copy Raw JSON"}
          </button>
        )}
      </div>

      {/* Structured View */}
      <div style={{ color: "#c9d1d9" }}>{children}</div>

      {/* Collapsible Raw JSON Dump for QA Verification */}
      {rawData !== undefined && (
        <details style={{ marginTop: "20px", borderTop: "1px dashed #30363d", paddingTop: "12px" }}>
          <summary style={{ cursor: "pointer", color: "#8b949e", fontSize: "0.85rem", fontWeight: 600 }}>
            🔍 Inspect Raw API Response (JSON)
          </summary>
          <pre
            style={{
              backgroundColor: "#0d1117",
              border: "1px solid #30363d",
              borderRadius: "6px",
              padding: "12px",
              overflowX: "auto",
              fontSize: "0.8rem",
              color: "#58a6ff",
              marginTop: "8px",
              maxHeight: "350px",
            }}
          >
            {JSON.stringify(rawData, null, 2)}
          </pre>
        </details>
      )}
    </div>
  );
};
