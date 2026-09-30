import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as apiClient from "../api/client";
import { HealthPage } from "./HealthPage";
import { createMockAxiosError, createMockNetworkError } from "../test/test-utils";

vi.mock("../api/client", async () => {
  const actual = await vi.importActual("../api/client");
  return {
    ...actual,
    fetchHealth: vi.fn(),
  };
});

describe("HealthPage Component", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("checks health on initial render and displays online status and version", async () => {
    vi.mocked(apiClient.fetchHealth).mockResolvedValue({ status: "ok", version: "1.0.0" });

    render(<HealthPage />);

    await waitFor(() => {
      expect(screen.getByText("Health Probe Report")).toBeInTheDocument();
      expect(screen.getAllByText("OK")[0]).toBeInTheDocument();
      expect(screen.getAllByText("1.0.0")[0]).toBeInTheDocument();
    });

    expect(screen.getByText(/Target Base URL/i)).toBeInTheDocument();
  });

  it("re-pings health endpoint when clicking Ping Now button", async () => {
    vi.mocked(apiClient.fetchHealth).mockResolvedValue({ status: "ok", version: "1.0.0" });

    render(<HealthPage />);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /Ping Now/i })).toBeInTheDocument();
    });

    const pingBtn = screen.getByRole("button", { name: /Ping Now/i });
    fireEvent.click(pingBtn);

    await waitFor(() => {
      expect(apiClient.fetchHealth).toHaveBeenCalledTimes(2);
    });
  });

  it("handles backend offline/failure cleanly with error banner and OFFLINE badge", async () => {
    vi.mocked(apiClient.fetchHealth).mockRejectedValue(createMockNetworkError());

    render(<HealthPage />);

    await waitFor(() => {
      expect(screen.getByText(/Network Error: Unable to reach backend/)).toBeInTheDocument();
      expect(screen.getByText("OFFLINE")).toBeInTheDocument();
    });
  });

  it("handles 500 Server Error response", async () => {
    vi.mocked(apiClient.fetchHealth).mockRejectedValue(
      createMockAxiosError(500, { error: "Database probe connection refused" })
    );

    render(<HealthPage />);

    await waitFor(() => {
      expect(screen.getByText("Database probe connection refused")).toBeInTheDocument();
      expect(screen.getByText(/HTTP 500/i)).toBeInTheDocument();
      expect(screen.getByText("OFFLINE")).toBeInTheDocument();
    });
  });
});
