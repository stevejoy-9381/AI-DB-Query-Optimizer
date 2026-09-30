import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import App from "./App";

vi.mock("./api/client", async () => {
  const actual = await vi.importActual("./api/client");
  return {
    ...actual,
    fetchHealth: vi.fn().mockResolvedValue({ status: "ok", version: "1.0.0" }),
    analyzeQuery: vi.fn(),
  };
});

describe("App Root Router", () => {
  it("renders Navbar and default Analyze page", async () => {
    render(<App />);
    expect(screen.getByText(/SQL Optimizer QA Harness/)).toBeInTheDocument();
    expect(screen.getByText(/Query Analysis \(POST \/api\/analyze\)/)).toBeInTheDocument();
  });
});
