/**
 * frontend/src/components/LoadingSpinner.tsx
 * Clean spinner indicator with optional label.
 */

import React from "react";

interface Props {
  label?: string;
  size?: number;
}

export const LoadingSpinner: React.FC<Props> = ({ label = "Calling API...", size = 20 }) => {
  return (
    <div style={{ display: "inline-flex", alignItems: "center", gap: "10px", color: "#90caf9" }}>
      <div
        data-testid="spinner-circle"
        style={{
          width: `${size}px`,
          height: `${size}px`,
          border: "3px solid rgba(144, 202, 249, 0.2)",
          borderTopColor: "#90caf9",
          borderRadius: "50%",
          animation: "spin 0.8s linear infinite",
        }}
      />
      {label && <span style={{ fontSize: "0.9rem" }}>{label}</span>}
      <style>{`
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
};
