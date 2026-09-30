/**
 * frontend/src/components/QueryInput.tsx
 * Reusable SQL query input component with character counter, quick presets, and run trigger.
 */

import React from "react";
import { LoadingSpinner } from "./LoadingSpinner";

interface Props {
  query: string;
  onChange: (query: string) => void;
  onRun: () => void;
  loading: boolean;
  runLabel?: string;
  placeholder?: string;
  rows?: number;
}

const PRESETS = [
  {
    label: "Anti-pattern (Unindexed FK)",
    sql: "SELECT * FROM orders WHERE customer_id = 42;",
  },
  {
    label: "Non-Sargable Date",
    sql: "SELECT * FROM orders WHERE YEAR(order_date) = 2024;",
  },
  {
    label: "Leading Wildcard",
    sql: "SELECT * FROM customers WHERE email LIKE '%@gmail.com';",
  },
  {
    label: "Good (PK Lookup)",
    sql: "SELECT id, name, email FROM customers WHERE id = 1050;",
  },
  {
    label: "Edge: Blank/Whitespace",
    sql: "   ",
  },
  {
    label: "Edge: >20,000 Chars",
    sql: "SELECT 1; " + "/* padding */ ".repeat(1500),
  },
];

export const QueryInput: React.FC<Props> = ({
  query,
  onChange,
  onRun,
  loading,
  runLabel = "Run Query",
  placeholder = "Enter MySQL 8.x query to analyze...",
  rows = 5,
}) => {
  const charCount = query.length;
  const isTooLong = charCount > 20000;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "10px", margin: "16px 0" }}>
      {/* Quick Test Presets */}
      <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "8px" }}>
        <span style={{ fontSize: "0.8rem", color: "#8b949e", fontWeight: "bold" }}>
          Quick Test Presets:
        </span>
        {PRESETS.map((p) => (
          <button
            key={p.label}
            type="button"
            onClick={() => onChange(p.sql)}
            disabled={loading}
            style={{
              backgroundColor: "#21262d",
              border: "1px solid #30363d",
              color: "#c9d1d9",
              padding: "4px 8px",
              borderRadius: "4px",
              fontSize: "0.75rem",
              cursor: loading ? "not-allowed" : "pointer",
            }}
          >
            {p.label}
          </button>
        ))}
        <button
          type="button"
          onClick={() => onChange("")}
          disabled={loading || !query}
          style={{
            backgroundColor: "#21262d",
            border: "1px solid #30363d",
            color: "#f85149",
            padding: "4px 8px",
            borderRadius: "4px",
            fontSize: "0.75rem",
            cursor: loading || !query ? "not-allowed" : "pointer",
          }}
        >
          Clear
        </button>
      </div>

      {/* SQL Editor Area */}
      <div style={{ position: "relative" }}>
        <textarea
          value={query}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          rows={rows}
          disabled={loading}
          style={{
            width: "100%",
            boxSizing: "border-box",
            backgroundColor: "#0d1117",
            border: `1px solid ${isTooLong ? "#f85149" : "#30363d"}`,
            borderRadius: "6px",
            color: "#e6edf3",
            fontFamily: "monospace",
            fontSize: "0.9rem",
            padding: "12px",
            lineHeight: "1.4",
            outline: "none",
          }}
        />
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginTop: "4px",
            fontSize: "0.75rem",
            color: isTooLong ? "#f85149" : "#8b949e",
          }}
        >
          <span>Max length: 20,000 characters</span>
          <span>
            {charCount.toLocaleString()} / 20,000 chars {isTooLong && "⚠️ Exceeds limit"}
          </span>
        </div>
      </div>

      {/* Action Buttons */}
      <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
        <button
          type="button"
          onClick={onRun}
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
          {loading ? <LoadingSpinner label="Running..." size={16} /> : `▶ ${runLabel}`}
        </button>
      </div>
    </div>
  );
};
