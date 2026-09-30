import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as apiClient from "../api/client";
import type { SimulateIndexResponse } from "../api/types";
import { SimulateIndexPage } from "./SimulateIndexPage";
import { createMockAxiosError, createMockNetworkError } from "../test/test-utils";

vi.mock("../api/client", async () => {
  const actual = await vi.importActual("../api/client");
  return {
    ...actual,
    simulateIndex: vi.fn(),
  };
});

const mockSimulationSuccess: SimulateIndexResponse = {
  query: "SELECT * FROM orders WHERE customer_id = 42;",
  index: "CREATE INDEX idx_orders_customer_id ON orders(customer_id);",
  simulation: {
    impact_level: "HIGH",
    before_score: 55,
    after_score: 95,
    score_improvement: 40,
    before_cost: "HIGH",
    after_cost: "LOW",
    before_rows: 10000,
    after_rows: 10,
    rows_reduction_pct: 99.9,
    before_time_ms: 45.2,
    after_time_ms: 1.1,
    speedup_factor: 41.1,
    speedup_label: "41.1x faster",
  },
};

describe("SimulateIndexPage Component", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders default layout with query textarea, index input, and simulate button", () => {
    render(<SimulateIndexPage />);
    expect(screen.getByText(/Index Impact Simulator \(POST \/api\/simulate-index\)/)).toBeInTheDocument();
    expect(screen.getByDisplayValue(/SELECT \* FROM orders WHERE customer_id = 42;/)).toBeInTheDocument();
    expect(screen.getByDisplayValue(/CREATE INDEX idx_orders_customer_id/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Simulate Impact/i })).toBeInTheDocument();
  });

  it("shows loading indicator during index simulation", async () => {
    let resolvePromise: (val: any) => void;
    const promise = new Promise((resolve) => {
      resolvePromise = resolve;
    });
    vi.mocked(apiClient.simulateIndex).mockReturnValue(promise as any);

    render(<SimulateIndexPage />);
    const runBtn = screen.getByRole("button", { name: /Simulate Impact/i });
    fireEvent.click(runBtn);

    expect(screen.getByText("Simulating...")).toBeInTheDocument();
    expect(runBtn).toBeDisabled();

    resolvePromise!(mockSimulationSuccess);
    await waitFor(() => {
      expect(screen.queryByText("Simulating...")).not.toBeInTheDocument();
    });
  });

  it("renders projection metrics, speedup factor, and row reductions upon success", async () => {
    vi.mocked(apiClient.simulateIndex).mockResolvedValue(mockSimulationSuccess);

    render(<SimulateIndexPage />);
    fireEvent.click(screen.getByRole("button", { name: /Simulate Impact/i }));

    await waitFor(() => {
      expect(screen.getByText("Simulation Projection")).toBeInTheDocument();
    });

    expect(screen.getAllByText(/41\.1x faster/)[0]).toBeInTheDocument();
    expect(screen.getByText(/Impact: HIGH/)).toBeInTheDocument();
    expect(screen.getAllByText(/\+40 points/)[0]).toBeInTheDocument();
    expect(screen.getAllByText(/99\.9% reduction/)[0]).toBeInTheDocument();
  });

  it("handles 400 Bad Request error cleanly with ErrorBanner", async () => {
    vi.mocked(apiClient.simulateIndex).mockRejectedValue(
      createMockAxiosError(400, { error: "Invalid index definition syntax" })
    );

    render(<SimulateIndexPage />);
    fireEvent.click(screen.getByRole("button", { name: /Simulate Impact/i }));

    await waitFor(() => {
      expect(screen.getByText("Invalid index definition syntax")).toBeInTheDocument();
      expect(screen.getByText(/HTTP 400/i)).toBeInTheDocument();
    });
  });

  it("handles 422 Unprocessable Entity validation error", async () => {
    vi.mocked(apiClient.simulateIndex).mockRejectedValue(
      createMockAxiosError(422, {
        detail: [{ loc: ["body", "index"], msg: "Index DDL cannot be empty" }],
      })
    );

    render(<SimulateIndexPage />);
    fireEvent.click(screen.getByRole("button", { name: /Simulate Impact/i }));

    await waitFor(() => {
      expect(screen.getAllByText(/Index DDL cannot be empty/)[0]).toBeInTheDocument();
      expect(screen.getByText(/HTTP 422/i)).toBeInTheDocument();
    });
  });

  it("handles 500 Server Error cleanly", async () => {
    vi.mocked(apiClient.simulateIndex).mockRejectedValue(
      createMockAxiosError(500, { error: "Simulator calculation failed" })
    );

    render(<SimulateIndexPage />);
    fireEvent.click(screen.getByRole("button", { name: /Simulate Impact/i }));

    await waitFor(() => {
      expect(screen.getByText("Simulator calculation failed")).toBeInTheDocument();
      expect(screen.getByText(/HTTP 500/i)).toBeInTheDocument();
    });
  });

  it("handles network failure cleanly", async () => {
    vi.mocked(apiClient.simulateIndex).mockRejectedValue(createMockNetworkError());

    render(<SimulateIndexPage />);
    fireEvent.click(screen.getByRole("button", { name: /Simulate Impact/i }));

    await waitFor(() => {
      expect(screen.getByText(/Network Error: Unable to reach backend/)).toBeInTheDocument();
    });
  });
});
