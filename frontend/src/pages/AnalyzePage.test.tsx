import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi, beforeEach } from "vitest";
import * as apiClient from "../api/client";
import type { AnalyzeResponse } from "../api/types";
import { AnalyzePage } from "./AnalyzePage";
import { createMockAxiosError, createMockNetworkError } from "../test/test-utils";

const renderAnalyzePage = (state?: any) => {
  return render(
    <MemoryRouter initialEntries={state ? [{ pathname: "/", state }] : ["/"]}>
      <AnalyzePage />
    </MemoryRouter>
  );
};

vi.mock("../api/client", async () => {
  const actual = await vi.importActual("../api/client");
  return {
    ...actual,
    analyzeQuery: vi.fn(),
  };
});

const mockAnalyzeSuccess: AnalyzeResponse = {
  query: "SELECT * FROM orders WHERE customer_id = 42;",
  query_type: "SELECT",
  statement_type: "SELECT",
  complexity: "SIMPLE",
  issues: [
    {
      code: "SELECT_STAR",
      rule: "SELECT_STAR",
      severity: "MEDIUM",
      message: "SELECT * returns all columns unnecessarily",
      suggestion: "Specify required columns explicitly",
    },
  ],
  warnings: [],
  filter_columns: ["customer_id"],
  join_count: 0,
  subquery_count: 0,
  has_aggregation: false,
  has_group_by: false,
  has_order_by: false,
  has_limit: false,
  has_distinct: false,
  select_star: true,
  has_where: true,
  analysis_engine: "FastAPI + Sqlglot AST Engine",
  score: {
    score: 85,
    cost_estimate: "LOW",
    complexity: "SIMPLE",
    rows_scanned_estimate: "1 - 100 rows",
    table_multiplier: 1.0,
    breakdown: [
      {
        code: "SELECT_STAR",
        label: "SELECT * Used",
        delta: -15,
        severity: "MEDIUM",
        explanation: "Unnecessary IO and network overhead",
      },
    ],
  },
};

describe("AnalyzePage Component", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders default layout with initial sample query and run button", () => {
    renderAnalyzePage();
    expect(screen.getByText(/Query Analysis \(POST \/api\/analyze\)/)).toBeInTheDocument();
    expect(screen.getByDisplayValue(/SELECT \* FROM orders/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Analyze Query/i })).toBeInTheDocument();
  });

  it("shows loading state while analysis request is in flight", async () => {
    let resolvePromise: (val: any) => void;
    const promise = new Promise((resolve) => {
      resolvePromise = resolve;
    });
    vi.mocked(apiClient.analyzeQuery).mockReturnValue(promise as any);

    renderAnalyzePage();
    const runBtn = screen.getByRole("button", { name: /Analyze Query/i });
    fireEvent.click(runBtn);

    expect(screen.getByText("Running...")).toBeInTheDocument();
    expect(runBtn).toBeDisabled();

    resolvePromise!(mockAnalyzeSuccess);
    await waitFor(() => {
      expect(screen.queryByText("Running...")).not.toBeInTheDocument();
    });
  });

  it("renders analysis metrics, cards, and detected issues upon success", async () => {
    vi.mocked(apiClient.analyzeQuery).mockResolvedValue(mockAnalyzeSuccess);

    renderAnalyzePage();
    const runBtn = screen.getByRole("button", { name: /Analyze Query/i });
    fireEvent.click(runBtn);

    await waitFor(() => {
      expect(screen.getByText("85 / 100")).toBeInTheDocument();
      expect(screen.getByText("SIMPLE")).toBeInTheDocument();
      expect(screen.getByText("SELECT * returns all columns unnecessarily")).toBeInTheDocument();
      expect(screen.getByText("FastAPI + Sqlglot AST Engine")).toBeInTheDocument();
    });
  });

  it("handles 400 Bad Request error cleanly with ErrorBanner", async () => {
    vi.mocked(apiClient.analyzeQuery).mockRejectedValue(
      createMockAxiosError(400, { error: "Query syntax invalid near position 12" })
    );

    renderAnalyzePage();
    fireEvent.click(screen.getByRole("button", { name: /Analyze Query/i }));

    await waitFor(() => {
      expect(screen.getByText("Query syntax invalid near position 12")).toBeInTheDocument();
      expect(screen.getByText(/HTTP 400/i)).toBeInTheDocument();
    });
  });

  it("handles 422 Unprocessable Entity error (e.g. empty or disallowed query)", async () => {
    vi.mocked(apiClient.analyzeQuery).mockRejectedValue(
      createMockAxiosError(422, {
        detail: [{ loc: ["body", "query"], msg: "SQL query string cannot be empty or blank" }],
      })
    );

    renderAnalyzePage();
    fireEvent.click(screen.getByRole("button", { name: /Analyze Query/i }));

    await waitFor(() => {
      expect(screen.getAllByText(/SQL query string cannot be empty/)[0]).toBeInTheDocument();
      expect(screen.getByText(/HTTP 422/i)).toBeInTheDocument();
    });
  });

  it("handles 500 Server Error cleanly", async () => {
    vi.mocked(apiClient.analyzeQuery).mockRejectedValue(
      createMockAxiosError(500, { error: "AST Parser crashed unexpectedly" })
    );

    renderAnalyzePage();
    fireEvent.click(screen.getByRole("button", { name: /Analyze Query/i }));

    await waitFor(() => {
      expect(screen.getByText("AST Parser crashed unexpectedly")).toBeInTheDocument();
      expect(screen.getByText(/HTTP 500/i)).toBeInTheDocument();
    });
  });

  it("handles network failure cleanly", async () => {
    vi.mocked(apiClient.analyzeQuery).mockRejectedValue(createMockNetworkError());

    renderAnalyzePage();
    fireEvent.click(screen.getByRole("button", { name: /Analyze Query/i }));

    await waitFor(() => {
      expect(screen.getByText(/Network Error: Unable to reach backend/)).toBeInTheDocument();
    });
  });

  it("populates textarea when preloadedQuery is passed in router location state", () => {
    renderAnalyzePage({ preloadedQuery: "SELECT id, name FROM users WHERE active = 1;" });
    expect(screen.getByDisplayValue("SELECT id, name FROM users WHERE active = 1;")).toBeInTheDocument();
  });
});
