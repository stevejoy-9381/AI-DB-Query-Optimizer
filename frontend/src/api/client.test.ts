import { describe, expect, it } from "vitest";
import { extractErrorMessage, getBaseUrl, setBaseUrl, apiClient } from "./client";
import { createMockAxiosError, createMockNetworkError } from "../test/test-utils";

describe("API Client & Error Utilities", () => {
  it("extracts error message from data.error property", () => {
    const err = createMockAxiosError(400, { error: "Custom syntax error" });
    const result = extractErrorMessage(err);
    expect(result.message).toBe("Custom syntax error");
    expect(result.status).toBe(400);
  });

  it("extracts string detail from data.detail property", () => {
    const err = createMockAxiosError(404, { detail: "Item not found" });
    const result = extractErrorMessage(err);
    expect(result.message).toBe("Item not found");
    expect(result.status).toBe(404);
  });

  it("formats validation array details into semicolon-separated string", () => {
    const err = createMockAxiosError(422, {
      detail: [
        { loc: ["body", "query"], msg: "Cannot be blank" },
        { loc: ["body", "index"], msg: "Invalid format" },
      ],
    });
    const result = extractErrorMessage(err);
    expect(result.message).toContain("body.query: Cannot be blank; body.index: Invalid format");
    expect(result.status).toBe(422);
    expect(result.detail).toHaveLength(2);
  });

  it("handles Network Error with helpful connectivity message", () => {
    const err = createMockNetworkError();
    const result = extractErrorMessage(err);
    expect(result.message).toContain("Network Error: Unable to reach backend");
    expect(result.status).toBe(0);
  });

  it("extracts message from standard Error object", () => {
    const err = new Error("Standard runtime error");
    const result = extractErrorMessage(err);
    expect(result.message).toBe("Standard runtime error");
  });

  it("handles unknown non-Error objects gracefully", () => {
    const result = extractErrorMessage("random string error");
    expect(result.message).toBe("An unexpected error occurred");
  });

  it("gets and sets base URL in localStorage and Axios defaults", () => {
    setBaseUrl("http://localhost:9999");
    expect(getBaseUrl()).toBe("http://localhost:9999");
    expect(apiClient.defaults.baseURL).toBe("http://localhost:9999");
  });
});
