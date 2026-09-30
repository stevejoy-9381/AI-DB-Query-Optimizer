/**
 * frontend/src/components/Navbar.tsx
 * Top navigation bar with active links, real-time health indicator, and API port switcher.
 */

import React, { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { fetchHealth, getBaseUrl, setBaseUrl } from "../api/client";

const NAV_ITEMS = [
  { path: "/", label: "⚡ Analyze" },
  { path: "/score", label: "📊 Score" },
  { path: "/recommendations", label: "💡 Recommendations" },
  { path: "/rewrite", label: "🔄 Rewrite" },
  { path: "/execution-plan", label: "🌳 Execution Plan" },
  { path: "/simulate-index", label: "🧪 Simulate Index" },
  { path: "/sample-queries", label: "📁 Sample Queries" },
  { path: "/health", label: "🩺 Health" },
];

export const Navbar: React.FC = () => {
  const location = useLocation();
  const [healthy, setHealthy] = useState<boolean | null>(null);
  const [version, setVersion] = useState<string>("");
  const [apiUrl, setApiUrlState] = useState<string>(getBaseUrl());
  const [showConfig, setShowConfig] = useState(false);

  const checkStatus = async () => {
    try {
      const data = await fetchHealth();
      setHealthy(data.status === "ok");
      setVersion(data.version || "1.0.0");
    } catch {
      setHealthy(false);
    }
  };

  useEffect(() => {
    checkStatus();
    const interval = setInterval(checkStatus, 8000);
    return () => clearInterval(interval);
  }, [apiUrl]);

  const handleUpdateApiUrl = (newUrl: string) => {
    setApiUrlState(newUrl);
    setBaseUrl(newUrl);
    checkStatus();
  };

  return (
    <header
      style={{
        backgroundColor: "#161b22",
        borderBottom: "1px solid #30363d",
        padding: "0 20px",
        position: "sticky",
        top: 0,
        zIndex: 100,
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          height: "56px",
          maxWidth: "1400px",
          margin: "0 auto",
        }}
      >
        {/* Brand & QA Badge */}
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <span style={{ fontSize: "1.1rem", fontWeight: "bold", color: "#58a6ff" }}>
            🛠️ SQL Optimizer QA Harness
          </span>

          {/* Health indicator dot */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "6px",
              padding: "2px 8px",
              borderRadius: "12px",
              backgroundColor: healthy === true ? "#0e3a24" : healthy === false ? "#3a1212" : "#21262d",
              border: `1px solid ${healthy === true ? "#2ecc71" : healthy === false ? "#e74c3c" : "#444c56"}`,
              fontSize: "0.75rem",
              fontWeight: 600,
              color: healthy === true ? "#a3e9b9" : healthy === false ? "#f59a9a" : "#8b949e",
            }}
            title={
              healthy === true
                ? `Backend online (v${version}) at ${apiUrl}`
                : `Backend offline or unreachable at ${apiUrl}`
            }
          >
            <span
              style={{
                width: "8px",
                height: "8px",
                borderRadius: "50%",
                backgroundColor: healthy === true ? "#2ecc71" : healthy === false ? "#e74c3c" : "#8b949e",
              }}
            />
            {healthy === true ? "API Online" : healthy === false ? "API Offline" : "Checking..."}
          </div>
        </div>

        {/* Navigation Tabs */}
        <nav style={{ display: "flex", gap: "4px", overflowX: "auto" }}>
          {NAV_ITEMS.map((item) => {
            const isActive = location.pathname === item.path;
            return (
              <Link
                key={item.path}
                to={item.path}
                style={{
                  padding: "8px 12px",
                  color: isActive ? "#ffffff" : "#8b949e",
                  textDecoration: "none",
                  fontSize: "0.85rem",
                  fontWeight: isActive ? 600 : 500,
                  borderBottom: isActive ? "2px solid #f78166" : "2px solid transparent",
                  transition: "all 0.15s ease",
                  whiteSpace: "nowrap",
                }}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>

        {/* API Target Switcher Button */}
        <div>
          <button
            type="button"
            onClick={() => setShowConfig(!showConfig)}
            style={{
              backgroundColor: "#21262d",
              border: "1px solid #30363d",
              color: "#c9d1d9",
              padding: "4px 8px",
              borderRadius: "4px",
              fontSize: "0.75rem",
              cursor: "pointer",
            }}
            title="Configure Target API URL"
          >
            ⚙️ {apiUrl.replace("http://", "")}
          </button>
        </div>
      </div>

      {/* Target URL Modal / Dropdown */}
      {showConfig && (
        <div
          style={{
            padding: "10px 0",
            borderTop: "1px solid #30363d",
            display: "flex",
            alignItems: "center",
            gap: "10px",
            fontSize: "0.85rem",
            color: "#c9d1d9",
            maxWidth: "1400px",
            margin: "0 auto",
          }}
        >
          <span>Target Backend URL:</span>
          <input
            type="text"
            value={apiUrl}
            onChange={(e) => handleUpdateApiUrl(e.target.value)}
            style={{
              backgroundColor: "#0d1117",
              border: "1px solid #30363d",
              color: "#e6edf3",
              padding: "4px 8px",
              borderRadius: "4px",
              fontFamily: "monospace",
              fontSize: "0.8rem",
              width: "240px",
            }}
          />
          <button
            type="button"
            onClick={() => handleUpdateApiUrl("http://localhost:8000")}
            style={{
              backgroundColor: "#21262d",
              border: "1px solid #30363d",
              color: "#8b949e",
              padding: "2px 6px",
              borderRadius: "4px",
              fontSize: "0.75rem",
              cursor: "pointer",
            }}
          >
            :8000
          </button>
          <button
            type="button"
            onClick={() => handleUpdateApiUrl("http://localhost:8001")}
            style={{
              backgroundColor: "#21262d",
              border: "1px solid #30363d",
              color: "#8b949e",
              padding: "2px 6px",
              borderRadius: "4px",
              fontSize: "0.75rem",
              cursor: "pointer",
            }}
          >
            :8001
          </button>
        </div>
      )}
    </header>
  );
};
