/**
 * frontend/src/App.tsx
 * Top-level application router wiring all QA test pages.
 */

import React from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Navbar } from "./components/Navbar";
import { AnalyzePage } from "./pages/AnalyzePage";
import { ExecutionPlanPage } from "./pages/ExecutionPlanPage";
import { HealthPage } from "./pages/HealthPage";
import { RecommendationsPage } from "./pages/RecommendationsPage";
import { RewritePage } from "./pages/RewritePage";
import { SampleQueriesPage } from "./pages/SampleQueriesPage";
import { ScorePage } from "./pages/ScorePage";
import { SimulateIndexPage } from "./pages/SimulateIndexPage";

export const App: React.FC = () => {
  return (
    <BrowserRouter>
      <div style={{ minHeight: "100vh", backgroundColor: "#0d1117", color: "#e6edf3" }}>
        <Navbar />
        <main style={{ maxWidth: "1400px", margin: "0 auto", padding: "24px 20px" }}>
          <Routes>
            <Route path="/" element={<AnalyzePage />} />
            <Route path="/score" element={<ScorePage />} />
            <Route path="/recommendations" element={<RecommendationsPage />} />
            <Route path="/rewrite" element={<RewritePage />} />
            <Route path="/execution-plan" element={<ExecutionPlanPage />} />
            <Route path="/simulate-index" element={<SimulateIndexPage />} />
            <Route path="/sample-queries" element={<SampleQueriesPage />} />
            <Route path="/health" element={<HealthPage />} />
            <Route
              path="*"
              element={
                <div style={{ textAlign: "center", padding: "40px" }}>
                  <h2>404 — Page Not Found</h2>
                  <p style={{ color: "#8b949e" }}>Select an endpoint from the top navigation bar.</p>
                </div>
              }
            />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
};

export default App;
