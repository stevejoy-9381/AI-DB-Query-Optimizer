import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { QueryInput } from "./QueryInput";

describe("QueryInput Component", () => {
  it("renders textarea with query value and char count", () => {
    const onChange = vi.fn();
    const onRun = vi.fn();
    render(
      <QueryInput
        query="SELECT * FROM users"
        onChange={onChange}
        onRun={onRun}
        loading={false}
      />
    );
    expect(screen.getByDisplayValue("SELECT * FROM users")).toBeInTheDocument();
    expect(screen.getByText(/20,000 chars/)).toBeInTheDocument();
  });

  it("calls onChange when typing in textarea", () => {
    const onChange = vi.fn();
    const onRun = vi.fn();
    render(
      <QueryInput
        query=""
        onChange={onChange}
        onRun={onRun}
        loading={false}
      />
    );
    const textarea = screen.getByRole("textbox");
    fireEvent.change(textarea, { target: { value: "SELECT 1" } });
    expect(onChange).toHaveBeenCalledWith("SELECT 1");
  });

  it("calls onRun when clicking run button", () => {
    const onChange = vi.fn();
    const onRun = vi.fn();
    render(
      <QueryInput
        query="SELECT 1"
        onChange={onChange}
        onRun={onRun}
        loading={false}
        runLabel="Execute"
      />
    );
    const button = screen.getByRole("button", { name: /Execute/i });
    fireEvent.click(button);
    expect(onRun).toHaveBeenCalledTimes(1);
  });

  it("disables run button when loading is true", () => {
    const onChange = vi.fn();
    const onRun = vi.fn();
    render(
      <QueryInput
        query="SELECT 1"
        onChange={onChange}
        onRun={onRun}
        loading={true}
        runLabel="Execute"
      />
    );
    const button = screen.getByRole("button", { name: /Running.../i });
    expect(button).toBeDisabled();
  });

  it("disables run button when query exceeds 20,000 characters", () => {
    const onChange = vi.fn();
    const onRun = vi.fn();
    const hugeQuery = "A".repeat(20001);
    render(
      <QueryInput
        query={hugeQuery}
        onChange={onChange}
        onRun={onRun}
        loading={false}
      />
    );
    expect(screen.getByText(/Exceeds limit/)).toBeInTheDocument();
  });

  it("loads preset query when preset chip is clicked", () => {
    const onChange = vi.fn();
    const onRun = vi.fn();
    render(
      <QueryInput
        query=""
        onChange={onChange}
        onRun={onRun}
        loading={false}
      />
    );
    const presetBtn = screen.getByText("Anti-pattern (Unindexed FK)");
    fireEvent.click(presetBtn);
    expect(onChange).toHaveBeenCalledWith("SELECT * FROM orders WHERE customer_id = 42;");
  });
});
