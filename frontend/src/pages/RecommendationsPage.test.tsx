import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as apiClient from "../api/client";
import type { RecommendationsResponse } from "../api/types";
import { RecommendationsPage } from "./RecommendationsPage";
import { createMockAxiosError, createMockNetworkError } from "../test/test-utils";

vi.mock("../api/client", async () => {
  const actual = await vi.importActual("../api/client");
  return {
    ...actual,
    getRecommendations: vi.fn(),
  };
});

const mockRecsSuccess: RecommendationsResponse = {
  query: "SELECT * FROM orders WHERE customer_id = 42;",
  count: 2,
  recommendations: [
    {
      index_name: "idx_orders_customer_id",
      table: "orders",
      columns: ["customer_id"],
      ddl: "CREATE INDEX idx_orders_customer_id ON orders(customer_id);",
      reason: "Eliminates full table scan on orders for customer_id filter",
      priority: "HIGH",
      index_type: "Secondary Index",
      trade_offs: "Small overhead on inserts/updates to orders table",
    },
    {
      index_name: "idx_orders_status_date",
      table: "orders",
      columns: ["status", "order_date"],
      ddl: "CREATE INDEX idx_orders_status_date ON orders(status, order_date);",
      reason: "Composite index matching equality filter + range",
      priority: "MEDIUM",
      index_type: "Composite Index",
      trade_offs: "Additional storage space required",
    },
  ],
};

describe("RecommendationsPage Component", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders default layout with initial query and get index advice button", () => {
    render(<RecommendationsPage />);
    expect(screen.getByText(/Index Recommendations \(POST \/api\/recommendations\)/)).toBeInTheDocument();
    expect(screen.getByDisplayValue(/SELECT \* FROM orders/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Get Index Advice/i })).toBeInTheDocument();
  });

  it("shows loading indicator during recommendation calculation", async () => {
    let resolvePromise: (val: any) => void;
    const promise = new Promise((resolve) => {
      resolvePromise = resolve;
    });
    vi.mocked(apiClient.getRecommendations).mockReturnValue(promise as any);

    render(<RecommendationsPage />);
    const runBtn = screen.getByRole("button", { name: /Get Index Advice/i });
    fireEvent.click(runBtn);

    expect(screen.getByText("Running...")).toBeInTheDocument();
    expect(runBtn).toBeDisabled();

    resolvePromise!(mockRecsSuccess);
    await waitFor(() => {
      expect(screen.queryByText("Running...")).not.toBeInTheDocument();
    });
  });

  it("renders generated recommendations with DDL and trade-offs", async () => {
    vi.mocked(apiClient.getRecommendations).mockResolvedValue(mockRecsSuccess);

    render(<RecommendationsPage />);
    fireEvent.click(screen.getByRole("button", { name: /Get Index Advice/i }));

    await waitFor(() => {
      expect(screen.getByText(/Index Recommendations \(2 Generated\)/)).toBeInTheDocument();
    });
    expect(screen.getAllByText(/CREATE INDEX idx_orders_customer_id/)[0]).toBeInTheDocument();
    expect(screen.getAllByText(/Eliminates full table scan on orders/)[0]).toBeInTheDocument();
    expect(screen.getAllByText(/Small overhead on inserts/)[0]).toBeInTheDocument();
    expect(screen.getAllByText(/CREATE INDEX idx_orders_status_date/)[0]).toBeInTheDocument();
  });

  it("renders empty state when no recommendations are required", async () => {
    vi.mocked(apiClient.getRecommendations).mockResolvedValue({
      query: "SELECT * FROM orders WHERE customer_id = 42;",
      count: 0,
      recommendations: [],
    });

    render(<RecommendationsPage />);
    fireEvent.click(screen.getByRole("button", { name: /Get Index Advice/i }));

    await waitFor(() => {
      expect(screen.getByText(/No secondary indexes required/)).toBeInTheDocument();
    });
  });

  it("handles 400 Bad Request error cleanly with ErrorBanner", async () => {
    vi.mocked(apiClient.getRecommendations).mockRejectedValue(
      createMockAxiosError(400, { error: "Query syntax invalid near position 10" })
    );

    render(<RecommendationsPage />);
    fireEvent.click(screen.getByRole("button", { name: /Get Index Advice/i }));

    await waitFor(() => {
      expect(screen.getByText("Query syntax invalid near position 10")).toBeInTheDocument();
      expect(screen.getByText(/HTTP 400/i)).toBeInTheDocument();
    });
  });

  it("handles 422 Unprocessable Entity validation error", async () => {
    vi.mocked(apiClient.getRecommendations).mockRejectedValue(
      createMockAxiosError(422, {
        detail: [{ loc: ["body", "query"], msg: "SQL query string cannot be empty or blank" }],
      })
    );

    render(<RecommendationsPage />);
    fireEvent.click(screen.getByRole("button", { name: /Get Index Advice/i }));

    await waitFor(() => {
      expect(screen.getAllByText(/SQL query string cannot be empty/)[0]).toBeInTheDocument();
      expect(screen.getByText(/HTTP 422/i)).toBeInTheDocument();
    });
  });

  it("handles 500 Server Error cleanly", async () => {
    vi.mocked(apiClient.getRecommendations).mockRejectedValue(
      createMockAxiosError(500, { error: "Index generator exception" })
    );

    render(<RecommendationsPage />);
    fireEvent.click(screen.getByRole("button", { name: /Get Index Advice/i }));

    await waitFor(() => {
      expect(screen.getByText("Index generator exception")).toBeInTheDocument();
      expect(screen.getByText(/HTTP 500/i)).toBeInTheDocument();
    });
  });

  it("handles network failure cleanly", async () => {
    vi.mocked(apiClient.getRecommendations).mockRejectedValue(createMockNetworkError());

    render(<RecommendationsPage />);
    fireEvent.click(screen.getByRole("button", { name: /Get Index Advice/i }));

    await waitFor(() => {
      expect(screen.getByText(/Network Error: Unable to reach backend/)).toBeInTheDocument();
    });
  });
});
