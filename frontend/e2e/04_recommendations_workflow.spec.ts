import { test, expect } from "@playwright/test";

test.describe("E2E Recommendations Workflow (POST /api/recommendations)", () => {
  test("generates index recommendation DDL and trade-offs for unindexed query", async ({ page }) => {
    await page.goto("/recommendations");
    await expect(page.getByRole("heading", { name: /Index Recommendations/i })).toBeVisible();

    const adviceBtn = page.getByRole("button", { name: /Get Index Advice/i });
    await adviceBtn.click();

    // Verify recommendations panel renders by finding the result heading (h3)
    await expect(page.getByRole("heading", { level: 3, name: /Index Recommendations/i })).toBeVisible({ timeout: 15000 });

    // Look for generated CREATE INDEX statement in pre box
    await expect(page.locator("pre").first()).toContainText(/CREATE INDEX/i);
  });
});
