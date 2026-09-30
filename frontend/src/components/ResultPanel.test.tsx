import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ResultPanel } from "./ResultPanel";

describe("ResultPanel Component", () => {
  it("renders title and children content", () => {
    render(
      <ResultPanel title="Test Analysis Result">
        <p>Custom structured findings</p>
      </ResultPanel>
    );
    expect(screen.getByText("Test Analysis Result")).toBeInTheDocument();
    expect(screen.getByText("Custom structured findings")).toBeInTheDocument();
  });

  it("renders collapsible raw JSON inspection when rawData is provided", () => {
    const rawData = { status: "ok", count: 42 };
    const { container } = render(
      <ResultPanel title="Results" rawData={rawData}>
        <div>Body</div>
      </ResultPanel>
    );
    expect(screen.getByText("🔍 Inspect Raw API Response (JSON)")).toBeInTheDocument();
    const pre = container.querySelector("pre");
    expect(pre?.textContent).toContain('"status": "ok"');
    expect(pre?.textContent).toContain('"count": 42');
  });

  it("copies raw JSON to clipboard when copy button clicked", () => {
    const writeTextMock = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      value: {
        writeText: writeTextMock,
      },
      writable: true,
      configurable: true,
    });

    const rawData = { score: 85 };
    render(
      <ResultPanel title="Results" rawData={rawData}>
        <div>Body</div>
      </ResultPanel>
    );

    const copyBtn = screen.getByRole("button", { name: /Copy Raw JSON/i });
    fireEvent.click(copyBtn);
    expect(writeTextMock).toHaveBeenCalledWith(JSON.stringify(rawData, null, 2));
    expect(screen.getByText("✓ Copied JSON")).toBeInTheDocument();
  });
});
