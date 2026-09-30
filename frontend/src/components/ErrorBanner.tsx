/**
 * frontend/src/components/ErrorBanner.tsx
 * Explicit error banner displaying backend error messages and HTTP status codes.
 */

import React from "react";

interface Props {
  error: string | null;
  status?: number;
  detail?: any;
  onDismiss?: () => void;
}

export const ErrorBanner: React.FC<Props> = ({ error, status, detail, onDismiss }) => {
  if (!error) return null;

  return (
    <div
      style={{
        backgroundColor: "#2d1515",
        border: "1px solid #e74c3c",
        borderRadius: "8px",
        padding: "16px",
        margin: "16px 0",
        color: "#ffcdd2",
        display: "flex",
        flexDirection: "column",
        gap: "8px",
      }}
      role="alert"
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "10px", fontWeight: "bold" }}>
          <span style={{ fontSize: "1.2rem" }}>⚠️</span>
          <span>{status ? `Error (HTTP ${status})` : "Error"}</span>
        </div>
        {onDismiss && (
          <button
            onClick={onDismiss}
            style={{
              background: "transparent",
              border: "none",
              color: "#ffcdd2",
              cursor: "pointer",
              fontSize: "1rem",
            }}
            title="Dismiss"
          >
            ✕
          </button>
        )}
      </div>

      <div style={{ fontFamily: "monospace", fontSize: "0.95rem", color: "#ff8a80" }}>
        {error}
      </div>

      {detail && (
        <details style={{ marginTop: "6px", fontSize: "0.85rem", color: "#ffb4ab" }}>
          <summary style={{ cursor: "pointer" }}>View Technical Details</summary>
          <pre
            style={{
              backgroundColor: "#1f0d0d",
              padding: "8px",
              borderRadius: "4px",
              overflowX: "auto",
              marginTop: "4px",
            }}
          >
            {typeof detail === "object" ? JSON.stringify(detail, null, 2) : String(detail)}
          </pre>
        </details>
      )}
    </div>
  );
};
