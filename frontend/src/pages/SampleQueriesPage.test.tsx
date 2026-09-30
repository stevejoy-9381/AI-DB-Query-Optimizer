import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as apiClient from "../api/client";
import type { SampleQueryItem } from "../api/types";
import { SampleQueriesPage } from "./SampleQueriesPage";
import { createMockAxiosError, createMockNetworkError } from "../test/test-utils";

vi.mock("../api/client", async () => {
  const actual = await vi.importActual("../api/client");
  return {
    ...actual,
    fetchSampleQueries: vi.fn(),
  };
});

const mockSamples: SampleQueryItem[] = [
  {
    category: "Anti-Pattern",
    description: "SELECT * without limit on large table",
    query: "SELECT * FROM orders WHERE customer_id = 42;",
  },
  {
    category: "Anti-Pattern",
    description: "Leading wildcard LIKE query",
    query: "SELECT name FROM customers WHERE name LIKE '%son';",
  },
  {
    category: "Optimized",
    description: "Covering index lookup with projection",
    query: "SELECT id, status FROM orders WHERE status = 'PENDING';",
  },
];

describe("SampleQueriesPage Component", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("fetches and renders sample queries catalog on mount", async () => {
    vi.mocked(apiClient.fetchSampleQueries).mockResolvedValue(mockSamples);

    render(
      <MemoryRouter>
        <SampleQueriesPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText(/Catalog \(3 of 3 Queries\)/)).toBeInTheDocument();
    });

    expect(screen.getByText("SELECT * without limit on large table")).toBeInTheDocument();
    expect(screen.getByText("Leading wildcard LIKE query")).toBeInTheDocument();
    expect(screen.getByText("Covering index lookup with projection")).toBeInTheDocument();
  });

  it("filters query catalog dynamically by search keyword", async () => {
    vi.mocked(apiClient.fetchSampleQueries).mockResolvedValue(mockSamples);

    render(
      <MemoryRouter>
        <SampleQueriesPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText(/Catalog \(3 of 3 Queries\)/)).toBeInTheDocument();
    });

    const searchInput = screen.getByPlaceholderText(/Filter sample queries/i);
    fireEvent.change(searchInput, { target: { value: "wildcard" } });

    expect(screen.getByText(/Catalog \(1 of 3 Queries\)/)).toBeInTheDocument();
    expect(screen.getByText("Leading wildcard LIKE query")).toBeInTheDocument();
    expect(screen.queryByText("Covering index lookup with projection")).not.toBeInTheDocument();
  });

  it("allows manual dataset reload via reload button", async () => {
    vi.mocked(apiClient.fetchSampleQueries).mockResolvedValue(mockSamples);

    render(
      <MemoryRouter>
        <SampleQueriesPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText(/Catalog \(3 of 3 Queries\)/)).toBeInTheDocument();
    });

    const reloadBtn = screen.getByRole("button", { name: /Reload Dataset/i });
    fireEvent.click(reloadBtn);

    await waitFor(() => {
      expect(apiClient.fetchSampleQueries).toHaveBeenCalledTimes(2);
    });
  });

  it("handles 500 Server Error cleanly when catalog fails to load", async () => {
    vi.mocked(apiClient.fetchSampleQueries).mockRejectedValue(
      createMockAxiosError(500, { error: "Failed to load CSV catalog" })
    );

    render(
      <MemoryRouter>
        <SampleQueriesPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText("Failed to load CSV catalog")).toBeInTheDocument();
      expect(screen.getByText(/HTTP 500/i)).toBeInTheDocument();
    });
  });

  it("handles network error gracefully when API is unreachable", async () => {
    vi.mocked(apiClient.fetchSampleQueries).mockRejectedValue(createMockNetworkError());

    render(
      <MemoryRouter>
        <SampleQueriesPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText(/Network Error: Unable to reach backend/)).toBeInTheDocument();
    });
  });
});
