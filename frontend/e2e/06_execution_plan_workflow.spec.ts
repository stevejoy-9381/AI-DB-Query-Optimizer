import { test, expect } from "@playwright/test";

test.describe("E2E Execution Plan Workflow (POST /api/execution-plan)", () => {
  test("generates visual InnoDB execution plan tree with node details", async ({ page }) => {
    await page.goto("/execution-plan");
    await expect(page.getByRole("heading", { name: /Execution Plan Visualizer/i })).toBeVisible();

    const planBtn = page.getByRole("button", { name: /Generate Plan/i });
    await planBtn.click();

    // Verify tree result panel renders
    await expect(page.getByText("Simulated MySQL Execution Plan Tree")).toBeVisible({ timeout: 15000 });
    await expect(page.getByText(/Total Cost:/i)).toBeVisible();
    await expect(page.getByText(/Total Nodes:/i)).toBeVisible();

    // Verify tree flow exists
    await expect(page.getByText("Execution Tree Flow")).toBeVisible();
    await expect(page.locator("span:has-text('Scan')").or(page.locator("span:has-text('Join')")).first()).toBeVisible();
  });
});
