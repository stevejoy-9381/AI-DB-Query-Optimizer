import { test, expect } from "@playwright/test";

test.describe("E2E Simulate Index Workflow (POST /api/simulate-index)", () => {
  test("projects speedup factor, latency drop, and row scan reduction", async ({ page }) => {
    await page.goto("/simulate-index");
    await expect(page.getByRole("heading", { name: /Index Impact Simulator/i })).toBeVisible();

    const simBtn = page.getByRole("button", { name: /Simulate Impact/i });
    await simBtn.click();

    // Verify simulation results render
    await expect(page.getByText("Simulation Projection")).toBeVisible({ timeout: 15000 });
    await expect(page.getByText("SPEEDUP FACTOR", { exact: true })).toBeVisible();
    await expect(page.getByText("SCORE PROJECTION", { exact: true })).toBeVisible();
    await expect(page.getByText("ESTIMATED ROWS SCANNED", { exact: true })).toBeVisible();
    await expect(page.getByText("ESTIMATED LATENCY", { exact: true })).toBeVisible();
  });
});
