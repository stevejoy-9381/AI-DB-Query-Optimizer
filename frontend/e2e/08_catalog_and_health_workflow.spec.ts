import { test, expect } from "@playwright/test";

test.describe("E2E Catalog & Health Probes", () => {
  test("loads sample query benchmark catalog and tests filtering", async ({ page }) => {
    await page.goto("/sample-queries");
    await expect(page.getByRole("heading", { name: /Sample Queries Catalog/i })).toBeVisible();

    // Verify catalog loaded items
    await expect(page.getByRole("heading", { level: 3, name: /Catalog \(\d+ of \d+ Queries\)/i })).toBeVisible({ timeout: 15000 });

    // Filter by join
    const filterInput = page.getByPlaceholder(/Filter sample queries/i);
    await filterInput.fill("join");

    // Click 'Test in Analyze' button on first matching query
    const testAnalyzeBtn = page.getByRole("button", { name: /Test in Analyze/i }).first();
    await testAnalyzeBtn.click();

    // Verify redirected to / and query is populated in textarea
    await expect(page).toHaveURL(/.*\//);
    const textarea = page.locator("textarea");
    await expect(textarea).not.toHaveValue("");
    await expect(textarea).toHaveValue(/join/i);
  });

  test("runs live system health probe and manual re-ping", async ({ page }) => {
    await page.goto("/health");
    await expect(page.getByRole("heading", { name: /System Health & Connectivity/i })).toBeVisible();

    // Verify probe results
    await expect(page.getByText("Health Probe Report")).toBeVisible({ timeout: 15000 });
    await expect(page.getByText("OK", { exact: true })).toBeVisible();
    await expect(page.locator("div:has-text('1.0.0')").first()).toBeVisible();

    // Click Ping Now button
    const pingBtn = page.getByRole("button", { name: /Ping Now/i });
    await pingBtn.click();
    await expect(pingBtn).toBeEnabled({ timeout: 10000 });
  });
});
