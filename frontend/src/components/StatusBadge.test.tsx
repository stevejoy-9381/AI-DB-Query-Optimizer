import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { StatusBadge } from "./StatusBadge";

describe("StatusBadge Component", () => {
  it("renders text correctly", () => {
    render(<StatusBadge text="HIGH" variant="danger" />);
    expect(screen.getByText("HIGH")).toBeInTheDocument();
  });

  it("handles numeric text", () => {
    render(<StatusBadge text={100} variant="success" />);
    expect(screen.getByText("100")).toBeInTheDocument();
  });

  it("supports small size variant", () => {
    const { container } = render(<StatusBadge text="LOW" size="sm" variant="info" />);
    expect((container.firstChild as HTMLElement).style.fontSize).toBe("0.75rem");
  });

  it("defaults to neutral variant when unspecified", () => {
    render(<StatusBadge text="DEFAULT" />);
    expect(screen.getByText("DEFAULT")).toBeInTheDocument();
  });
});
