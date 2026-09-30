import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ErrorBanner } from "./ErrorBanner";

describe("ErrorBanner Component", () => {
  it("renders nothing when error is null", () => {
    const { container } = render(<ErrorBanner error={null} />);
    expect(container.firstChild).toBeNull();
  });

  it("renders error message and status code", () => {
    render(<ErrorBanner error="Invalid SQL syntax" status={422} />);
    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(screen.getByText("Error (HTTP 422)")).toBeInTheDocument();
    expect(screen.getByText("Invalid SQL syntax")).toBeInTheDocument();
  });

  it("calls onDismiss handler when dismiss button clicked", () => {
    const onDismiss = vi.fn();
    render(<ErrorBanner error="Something went wrong" onDismiss={onDismiss} />);
    const dismissBtn = screen.getByTitle("Dismiss");
    fireEvent.click(dismissBtn);
    expect(onDismiss).toHaveBeenCalledTimes(1);
  });

  it("renders collapsible detail section when detail prop provided", () => {
    render(<ErrorBanner error="Validation Error" detail={[{ loc: ["query"], msg: "Too long" }]} />);
    expect(screen.getByText("View Technical Details")).toBeInTheDocument();
  });
});
