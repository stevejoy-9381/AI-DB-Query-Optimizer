/**
 * frontend/src/components/StatusBadge.tsx
 * Visual status badge for HTTP status, severity, cost tiers, and complexity.
 */

import React from "react";

interface Props {
  text: string | number;
  variant?: "success" | "warning" | "danger" | "info" | "neutral";
  size?: "sm" | "md";
}

const COLOR_MAP: Record<string, { bg: string; border: string; text: string }> = {
  success: { bg: "#0e3a24", border: "#2ecc71", text: "#a3e9b9" },
  warning: { bg: "#3a2e0e", border: "#f39c12", text: "#f8cf89" },
  danger: { bg: "#3a1212", border: "#e74c3c", text: "#f59a9a" },
  info: { bg: "#102a45", border: "#3498db", text: "#a0c8ee" },
  neutral: { bg: "#22272e", border: "#444c56", text: "#adbac7" },
};

export const StatusBadge: React.FC<Props> = ({ text, variant = "neutral", size = "md" }) => {
  const colors = COLOR_MAP[variant] || COLOR_MAP.neutral;
  const padding = size === "sm" ? "2px 8px" : "4px 12px";
  const fontSize = size === "sm" ? "0.75rem" : "0.85rem";

  return (
    <span
      style={{
        display: "inline-block",
        backgroundColor: colors.bg,
        border: `1px solid ${colors.border}`,
        color: colors.text,
        borderRadius: "12px",
        padding,
        fontSize,
        fontWeight: 600,
        fontFamily: "monospace",
        letterSpacing: "0.5px",
      }}
    >
      {text}
    </span>
  );
};
