import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as apiClient from "../api/client";
import type { ExecutionPlanResponse } from "../api/types";
import { ExecutionPlanPage } from "./ExecutionPlanPage";
import { createMockAxiosError, createMockNetworkError } from "../test/test-utils";

vi.mock("../api/client", async () => {
  const actual = await vi.importActual("../api/client");
  return {
    ...actual,
    getExecutionPlan: vi.fn(),
  };
});

const mockPlanSuccess: ExecutionPlanResponse = {
  query: "SELECT c.name, o.id FROM customers c JOIN orders o ON c.id = o.customer_id;",
  plan_root: {
    node_type: "Nested Loop Join",
    description: "Joins customers and orders via index lookup",
    estimated_rows: 500,
    startup_cost: 0.0,
    total_cost: 154.2,
    icon: "🔗",
    children: [
      {
        node_type: "Table Scan",
        description: "Full table scan",
        estimated_rows: 50,
        startup_cost: 0.0,
        total_cost: 45.0,
        icon: "📑",
        table: "customers",
        access_type: "ALL",
      },
      {
        node_type: "Index Lookup",
        description: "Index lookup on customer_id",
        estimated_rows: 10,
        startup_cost: 0.0,
        total_cost: 12.5,
        icon: "🔍",
        table: "orders",
        access_type: "ref",
      },
    ],
  },
  flattened_nodes: [
    { node_type: "Nested Loop Join", description: "Join", estimated_rows: 500, total_cost: 154.2, depth: 0 },
    { node_type: "Table Scan", description: "Scan", estimated_rows: 50, total_cost: 45.0, depth: 1 },
    { node_type: "Index Lookup", description: "Lookup", estimated_rows: 10, total_cost: 12.5, depth: 1 },
  ],
  summary: {
    total_cost: 154.2,
    total_nodes: 3,
    max_depth: 2,
    has_full_scan: true,
    has_filesort: false,
  },
};

describe("ExecutionPlanPage Component", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders default layout with sample join query and generate plan button", () => {
    render(<ExecutionPlanPage />);
    expect(screen.getByText(/Execution Plan Visualizer \(POST \/api\/execution-plan\)/)).toBeInTheDocument();
    expect(screen.getByDisplayValue(/JOIN orders o ON c\.id = o\.customer_id/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Generate Plan/i })).toBeInTheDocument();
  });

  it("shows loading indicator during plan generation", async () => {
    let resolvePromise: (val: any) => void;
    const promise = new Promise((resolve) => {
      resolvePromise = resolve;
    });
    vi.mocked(apiClient.getExecutionPlan).mockReturnValue(promise as any);

    render(<ExecutionPlanPage />);
    const runBtn = screen.getByRole("button", { name: /Generate Plan/i });
    fireEvent.click(runBtn);

    expect(screen.getByText("Running...")).toBeInTheDocument();
    expect(runBtn).toBeDisabled();

    resolvePromise!(mockPlanSuccess);
    await waitFor(() => {
      expect(screen.queryByText("Running...")).not.toBeInTheDocument();
    });
  });

  it("renders execution plan tree, summary badges, and node details upon success", async () => {
    vi.mocked(apiClient.getExecutionPlan).mockResolvedValue(mockPlanSuccess);

    render(<ExecutionPlanPage />);
    fireEvent.click(screen.getByRole("button", { name: /Generate Plan/i }));

    await waitFor(() => {
      expect(screen.getByText("Simulated MySQL Execution Plan Tree")).toBeInTheDocument();
    });

    expect(screen.getByText(/Total Cost: 154\.20/)).toBeInTheDocument();
    expect(screen.getByText(/Total Nodes: 3/)).toBeInTheDocument();
    expect(screen.getByText(/Full Table Scan: Detected/)).toBeInTheDocument();
    expect(screen.getByText(/Filesort: None/)).toBeInTheDocument();

    expect(screen.getAllByText(/Nested Loop Join/)[0]).toBeInTheDocument();
    expect(screen.getAllByText(/Table Scan/)[0]).toBeInTheDocument();
    expect(screen.getAllByText(/Index Lookup/)[0]).toBeInTheDocument();
    expect(screen.getByText(/on `customers`/)).toBeInTheDocument();
    expect(screen.getByText(/on `orders`/)).toBeInTheDocument();
  });

  it("handles 400 Bad Request error cleanly with ErrorBanner", async () => {
    vi.mocked(apiClient.getExecutionPlan).mockRejectedValue(
      createMockAxiosError(400, { error: "Unknown table 'non_existent_table' in plan generator" })
    );

    render(<ExecutionPlanPage />);
    fireEvent.click(screen.getByRole("button", { name: /Generate Plan/i }));

    await waitFor(() => {
      expect(screen.getByText("Unknown table 'non_existent_table' in plan generator")).toBeInTheDocument();
      expect(screen.getByText(/HTTP 400/i)).toBeInTheDocument();
    });
  });

  it("handles 422 Unprocessable Entity validation error", async () => {
    vi.mocked(apiClient.getExecutionPlan).mockRejectedValue(
      createMockAxiosError(422, {
        detail: [{ loc: ["body", "query"], msg: "SQL query string cannot be empty or blank" }],
      })
    );

    render(<ExecutionPlanPage />);
    fireEvent.click(screen.getByRole("button", { name: /Generate Plan/i }));

    await waitFor(() => {
      expect(screen.getAllByText(/SQL query string cannot be empty/)[0]).toBeInTheDocument();
      expect(screen.getByText(/HTTP 422/i)).toBeInTheDocument();
    });
  });

  it("handles 500 Server Error cleanly", async () => {
    vi.mocked(apiClient.getExecutionPlan).mockRejectedValue(
      createMockAxiosError(500, { error: "Plan visualizer internal crash" })
    );

    render(<ExecutionPlanPage />);
    fireEvent.click(screen.getByRole("button", { name: /Generate Plan/i }));

    await waitFor(() => {
      expect(screen.getByText("Plan visualizer internal crash")).toBeInTheDocument();
      expect(screen.getByText(/HTTP 500/i)).toBeInTheDocument();
    });
  });

  it("handles network failure cleanly", async () => {
    vi.mocked(apiClient.getExecutionPlan).mockRejectedValue(createMockNetworkError());

    render(<ExecutionPlanPage />);
    fireEvent.click(screen.getByRole("button", { name: /Generate Plan/i }));

    await waitFor(() => {
      expect(screen.getByText(/Network Error: Unable to reach backend/)).toBeInTheDocument();
    });
  });
});
