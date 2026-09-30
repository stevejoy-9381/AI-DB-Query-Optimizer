import { test, expect } from "@playwright/test";

test.describe("E2E Score Workflow (POST /api/score)", () => {
  test("computes performance score and displays deduction waterfall table", async ({ page }) => {
    await page.goto("/score");
    await expect(page.getByRole("heading", { name: /Performance Scoring/i })).toBeVisible();

    const calcBtn = page.getByRole("button", { name: /Calculate Score/i });
    await calcBtn.click();

    // Verify ResultPanel renders
    await expect(page.getByText("SCORE", { exact: true })).toBeVisible({ timeout: 15000 });
    await expect(page.getByText("COST ESTIMATE", { exact: true })).toBeVisible();
    await expect(page.getByText("COMPLEXITY TIER", { exact: true })).toBeVisible();
    await expect(page.getByText(/Deduction Waterfall Breakdown/i)).toBeVisible();

    // Verify deduction table items in table cell
    await expect(page.locator("td:has-text('SELECT_STAR')").first()).toBeVisible();
  });
});
