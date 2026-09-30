import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import * as apiClient from "../api/client";
import { Navbar } from "./Navbar";

vi.mock("../api/client", async () => {
  const actual = await vi.importActual("../api/client");
  return {
    ...actual,
    fetchHealth: vi.fn(),
  };
});

describe("Navbar Component", () => {
  it("renders all navigation items", async () => {
    vi.mocked(apiClient.fetchHealth).mockResolvedValue({ status: "ok", version: "1.0.0" });

    render(
      <MemoryRouter initialEntries={["/"]}>
        <Navbar />
      </MemoryRouter>
    );

    expect(screen.getByText("⚡ Analyze")).toBeInTheDocument();
    expect(screen.getByText("📊 Score")).toBeInTheDocument();
    expect(screen.getByText("💡 Recommendations")).toBeInTheDocument();
    expect(screen.getByText("🔄 Rewrite")).toBeInTheDocument();
    expect(screen.getByText("🌳 Execution Plan")).toBeInTheDocument();
    expect(screen.getByText("🧪 Simulate Index")).toBeInTheDocument();
    expect(screen.getByText("📁 Sample Queries")).toBeInTheDocument();
    expect(screen.getByText("🩺 Health")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText("API Online")).toBeInTheDocument();
    });
  });

  it("displays green health indicator when backend is online", async () => {
    vi.mocked(apiClient.fetchHealth).mockResolvedValue({ status: "ok", version: "1.0.0" });

    render(
      <MemoryRouter initialEntries={["/"]}>
        <Navbar />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText("API Online")).toBeInTheDocument();
      expect(screen.getByTitle(/Backend online \(v1\.0\.0\)/)).toBeInTheDocument();
    });
  });

  it("displays offline indicator when health check fails", async () => {
    vi.mocked(apiClient.fetchHealth).mockRejectedValue(new Error("Connection refused"));

    render(
      <MemoryRouter initialEntries={["/"]}>
        <Navbar />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText("API Offline")).toBeInTheDocument();
    });
  });
});
