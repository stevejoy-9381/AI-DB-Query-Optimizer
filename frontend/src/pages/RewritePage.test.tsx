import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as apiClient from "../api/client";
import type { RewriteResponse } from "../api/types";
import { RewritePage } from "./RewritePage";
import { createMockAxiosError, createMockNetworkError } from "../test/test-utils";

vi.mock("../api/client", async () => {
  const actual = await vi.importActual("../api/client");
  return {
    ...actual,
    rewriteQuery: vi.fn(),
  };
});

const mockRewriteChanged: RewriteResponse = {
  original: "SELECT * FROM orders WHERE YEAR(order_date) = 2024;",
  rewritten: "SELECT * FROM orders WHERE order_date >= '2024-01-01' AND order_date < '2025-01-01';",
  is_changed: true,
  changes: [
    "Converted non-sargable YEAR(order_date) = 2024 into date range filter to utilize index on order_date",
  ],
  rewrite_score_est: 25,
  validation: {
    is_valid_sql: true,
    level: "AST Verified",
    badge_color: "#2ecc71",
  },
  supported: true,
};

const mockRewriteUnchanged: RewriteResponse = {
  original: "SELECT id, name FROM users WHERE id = 1;",
  rewritten: "SELECT id, name FROM users WHERE id = 1;",
  is_changed: false,
  changes: [],
  rewrite_score_est: 0,
  validation: {
    is_valid_sql: true,
    level: "AST Verified",
    badge_color: "#3498db",
  },
  supported: true,
};

describe("RewritePage Component", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders default layout with sample query and rewrite button", () => {
    render(<RewritePage />);
    expect(screen.getByText(/AST Query Rewriter \(POST \/api\/rewrite\)/)).toBeInTheDocument();
    expect(screen.getByDisplayValue(/YEAR\(order_date\) = 2024/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Rewrite Query/i })).toBeInTheDocument();
  });

  it("shows loading indicator while rewrite processing is active", async () => {
    let resolvePromise: (val: any) => void;
    const promise = new Promise((resolve) => {
      resolvePromise = resolve;
    });
    vi.mocked(apiClient.rewriteQuery).mockReturnValue(promise as any);

    render(<RewritePage />);
    const runBtn = screen.getByRole("button", { name: /Rewrite Query/i });
    fireEvent.click(runBtn);

    expect(screen.getByText("Running...")).toBeInTheDocument();
    expect(runBtn).toBeDisabled();

    resolvePromise!(mockRewriteChanged);
    await waitFor(() => {
      expect(screen.queryByText("Running...")).not.toBeInTheDocument();
    });
  });

  it("renders side-by-side SQL diff and applied transformations when query is transformed", async () => {
    vi.mocked(apiClient.rewriteQuery).mockResolvedValue(mockRewriteChanged);

    render(<RewritePage />);
    fireEvent.click(screen.getByRole("button", { name: /Rewrite Query/i }));

    await waitFor(() => {
      expect(screen.getByText("QUERY REWRITTEN")).toBeInTheDocument();
    });
    expect(screen.getByText(/Estimated Score Boost/)).toBeInTheDocument();
    expect(screen.getAllByText(/AST Verified/)[0]).toBeInTheDocument();
    expect(screen.getAllByText(/order_date/)[0]).toBeInTheDocument();
    expect(screen.getAllByText(/Converted non-sargable/)[0]).toBeInTheDocument();
  });

  it("renders identical status when query requires no AST changes", async () => {
    vi.mocked(apiClient.rewriteQuery).mockResolvedValue(mockRewriteUnchanged);

    render(<RewritePage />);
    fireEvent.click(screen.getByRole("button", { name: /Rewrite Query/i }));

    await waitFor(() => {
      expect(screen.getByText("IDENTICAL")).toBeInTheDocument();
      expect(screen.getByText(/Estimated Score Boost: \+0 pts/)).toBeInTheDocument();
      expect(screen.queryByText("🛠️ Applied Transformations")).not.toBeInTheDocument();
    });
  });

  it("handles 400 Bad Request error cleanly with ErrorBanner", async () => {
    vi.mocked(apiClient.rewriteQuery).mockRejectedValue(
      createMockAxiosError(400, { error: "Query syntax invalid near position 8" })
    );

    render(<RewritePage />);
    fireEvent.click(screen.getByRole("button", { name: /Rewrite Query/i }));

    await waitFor(() => {
      expect(screen.getByText("Query syntax invalid near position 8")).toBeInTheDocument();
      expect(screen.getByText(/HTTP 400/i)).toBeInTheDocument();
    });
  });

  it("handles 422 Unprocessable Entity validation error", async () => {
    vi.mocked(apiClient.rewriteQuery).mockRejectedValue(
      createMockAxiosError(422, {
        detail: [{ loc: ["body", "query"], msg: "SQL query string cannot be empty or blank" }],
      })
    );

    render(<RewritePage />);
    fireEvent.click(screen.getByRole("button", { name: /Rewrite Query/i }));

    await waitFor(() => {
      expect(screen.getAllByText(/SQL query string cannot be empty/)[0]).toBeInTheDocument();
      expect(screen.getByText(/HTTP 422/i)).toBeInTheDocument();
    });
  });

  it("handles 500 Server Error cleanly", async () => {
    vi.mocked(apiClient.rewriteQuery).mockRejectedValue(
      createMockAxiosError(500, { error: "AST Rewriter crashed" })
    );

    render(<RewritePage />);
    fireEvent.click(screen.getByRole("button", { name: /Rewrite Query/i }));

    await waitFor(() => {
      expect(screen.getByText("AST Rewriter crashed")).toBeInTheDocument();
      expect(screen.getByText(/HTTP 500/i)).toBeInTheDocument();
    });
  });

  it("handles network failure cleanly", async () => {
    vi.mocked(apiClient.rewriteQuery).mockRejectedValue(createMockNetworkError());

    render(<RewritePage />);
    fireEvent.click(screen.getByRole("button", { name: /Rewrite Query/i }));

    await waitFor(() => {
      expect(screen.getByText(/Network Error: Unable to reach backend/)).toBeInTheDocument();
    });
  });
});
