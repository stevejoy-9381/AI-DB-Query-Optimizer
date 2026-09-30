import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { LoadingSpinner } from "./LoadingSpinner";

describe("LoadingSpinner Component", () => {
  it("renders with default label", () => {
    render(<LoadingSpinner />);
    expect(screen.getByText("Calling API...")).toBeInTheDocument();
  });

  it("renders with custom label", () => {
    render(<LoadingSpinner label="Analyzing query AST..." />);
    expect(screen.getByText("Analyzing query AST...")).toBeInTheDocument();
  });

  it("renders spinner element with custom size", () => {
    render(<LoadingSpinner size={16} />);
    const spinnerDiv = screen.getByTestId("spinner-circle");
    expect(spinnerDiv).toBeInTheDocument();
    expect(spinnerDiv.getAttribute("style")).toContain("16px");
  });
});
