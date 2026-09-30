import { test, expect } from "@playwright/test";

test.describe("E2E Query Analysis Workflow (POST /api/analyze)", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
  });

  test("analyzes default query and displays performance score, complexity, and AST engine", async ({ page }) => {
    const runBtn = page.getByRole("button", { name: /Analyze Query/i });
    await expect(runBtn).toBeVisible();

    await runBtn.click();

    // Verify ResultPanel renders
    await expect(page.getByText(/Analysis Findings for SELECT/i)).toBeVisible({ timeout: 15000 });
    await expect(page.getByText("PERFORMANCE SCORE", { exact: true })).toBeVisible();
    await expect(page.getByText("COMPLEXITY", { exact: true })).toBeVisible();
    await expect(page.getByText("AST ENGINE", { exact: true })).toBeVisible();

    // Characteristics badges
    await expect(page.getByText(/SELECT \*: Yes/i)).toBeVisible();
    await expect(page.getByText(/WHERE Clause: Present/i)).toBeVisible();
  });

  test("loads quick preset chips into SQL editor", async ({ page }) => {
    const textarea = page.locator("textarea");

    // Click Leading Wildcard preset
    await page.click("text=Leading Wildcard");
    await expect(textarea).toHaveValue(/LIKE '%@gmail\.com'/i);

    // Click PK lookup preset
    await page.click("text=Good (PK Lookup)");
    await expect(textarea).toHaveValue(/1050/);

    // Click Clear preset
    await page.click("text=Clear");
    await expect(textarea).toHaveValue("");
  });

  test("handles empty query validation error (HTTP 422)", async ({ page }) => {
    // Clear textarea
    await page.click("text=Clear");

    // Click Analyze Query
    await page.getByRole("button", { name: /Analyze Query/i }).click();

    // Expect ErrorBanner with HTTP 422
    await expect(page.locator('[role="alert"]')).toBeVisible({ timeout: 10000 });
    await expect(page.getByText(/Error \(HTTP 422\)/i)).toBeVisible();

    // Dismiss error
    await page.click('button[title="Dismiss"]');
    await expect(page.locator('[role="alert"]')).not.toBeVisible();
  });

  test("handles SQL syntax error (HTTP 422)", async ({ page }) => {
    const textarea = page.locator("textarea");
    await textarea.fill("SELECT * FORM orders WHERE ;");

    await page.getByRole("button", { name: /Analyze Query/i }).click();

    await expect(page.locator('[role="alert"]')).toBeVisible({ timeout: 10000 });
    await expect(page.getByText(/Error \(HTTP 422\)/i)).toBeVisible();
    await expect(page.locator('[role="alert"]').getByText(/SQL Syntax Error/i).first()).toBeVisible();
  });
});
