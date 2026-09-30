import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as apiClient from "../api/client";
import type { ScoreResponse } from "../api/types";
import { ScorePage } from "./ScorePage";
import { createMockAxiosError, createMockNetworkError } from "../test/test-utils";

vi.mock("../api/client", async () => {
  const actual = await vi.importActual("../api/client");
  return {
    ...actual,
    scoreQuery: vi.fn(),
  };
});

const mockScoreSuccess: ScoreResponse = {
  score: 75,
  cost_estimate: "MEDIUM",
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
    {
      code: "NO_INDEX_FILTER",
      label: "Unindexed Filter",
      delta: -10,
      severity: "LOW",
      explanation: "Filter on unindexed column",
    },
  ],
};

describe("ScorePage Component", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders default layout with initial query and calculate button", () => {
    render(<ScorePage />);
    expect(screen.getByText(/Performance Scoring \(POST \/api\/score\)/)).toBeInTheDocument();
    expect(screen.getByDisplayValue(/SELECT \* FROM orders/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Calculate Score/i })).toBeInTheDocument();
  });

  it("shows loading indicator while score computation is pending", async () => {
    let resolvePromise: (val: any) => void;
    const promise = new Promise((resolve) => {
      resolvePromise = resolve;
    });
    vi.mocked(apiClient.scoreQuery).mockReturnValue(promise as any);

    render(<ScorePage />);
    const runBtn = screen.getByRole("button", { name: /Calculate Score/i });
    fireEvent.click(runBtn);

    expect(screen.getByText("Running...")).toBeInTheDocument();
    expect(runBtn).toBeDisabled();

    resolvePromise!(mockScoreSuccess);
    await waitFor(() => {
      expect(screen.queryByText("Running...")).not.toBeInTheDocument();
    });
  });

  it("renders score metrics, cost tier, and deduction breakdown upon success", async () => {
    vi.mocked(apiClient.scoreQuery).mockResolvedValue(mockScoreSuccess);

    render(<ScorePage />);
    fireEvent.click(screen.getByRole("button", { name: /Calculate Score/i }));

    await waitFor(() => {
      expect(screen.getByText(/Performance Score: 75 \/ 100/)).toBeInTheDocument();
      expect(screen.getAllByText("MEDIUM")[0]).toBeInTheDocument();
      expect(screen.getByText(/Rows Scan: 1 - 100 rows/)).toBeInTheDocument();
      expect(screen.getByText("SELECT_STAR")).toBeInTheDocument();
      expect(screen.getByText("-15")).toBeInTheDocument();
      expect(screen.getByText("NO_INDEX_FILTER")).toBeInTheDocument();
      expect(screen.getByText("-10")).toBeInTheDocument();
    });
  });

  it("renders perfect 100 score with no penalties message", async () => {
    const perfectScore: ScoreResponse = {
      score: 100,
      cost_estimate: "LOW",
      complexity: "SIMPLE",
      rows_scanned_estimate: "1 row",
      table_multiplier: 1.0,
      breakdown: [],
    };
    vi.mocked(apiClient.scoreQuery).mockResolvedValue(perfectScore);

    render(<ScorePage />);
    fireEvent.click(screen.getByRole("button", { name: /Calculate Score/i }));

    await waitFor(() => {
      expect(screen.getByText("100 / 100")).toBeInTheDocument();
      expect(screen.getByText(/No penalties applied\. Base score is 100\/100\./)).toBeInTheDocument();
    });
  });

  it("handles 400 Bad Request error cleanly with ErrorBanner", async () => {
    vi.mocked(apiClient.scoreQuery).mockRejectedValue(
      createMockAxiosError(400, { error: "Query syntax invalid near position 5" })
    );

    render(<ScorePage />);
    fireEvent.click(screen.getByRole("button", { name: /Calculate Score/i }));

    await waitFor(() => {
      expect(screen.getByText("Query syntax invalid near position 5")).toBeInTheDocument();
      expect(screen.getByText(/HTTP 400/i)).toBeInTheDocument();
    });
  });

  it("handles 422 Unprocessable Entity validation error", async () => {
    vi.mocked(apiClient.scoreQuery).mockRejectedValue(
      createMockAxiosError(422, {
        detail: [{ loc: ["body", "query"], msg: "SQL query string cannot be empty or blank" }],
      })
    );

    render(<ScorePage />);
    fireEvent.click(screen.getByRole("button", { name: /Calculate Score/i }));

    await waitFor(() => {
      expect(screen.getAllByText(/SQL query string cannot be empty/)[0]).toBeInTheDocument();
      expect(screen.getByText(/HTTP 422/i)).toBeInTheDocument();
    });
  });

  it("handles 500 Server Error cleanly", async () => {
    vi.mocked(apiClient.scoreQuery).mockRejectedValue(
      createMockAxiosError(500, { error: "Scoring engine failure" })
    );

    render(<ScorePage />);
    fireEvent.click(screen.getByRole("button", { name: /Calculate Score/i }));

    await waitFor(() => {
      expect(screen.getByText("Scoring engine failure")).toBeInTheDocument();
      expect(screen.getByText(/HTTP 500/i)).toBeInTheDocument();
    });
  });

  it("handles network failure cleanly", async () => {
    vi.mocked(apiClient.scoreQuery).mockRejectedValue(createMockNetworkError());

    render(<ScorePage />);
    fireEvent.click(screen.getByRole("button", { name: /Calculate Score/i }));

    await waitFor(() => {
      expect(screen.getByText(/Network Error: Unable to reach backend/)).toBeInTheDocument();
    });
  });
});
