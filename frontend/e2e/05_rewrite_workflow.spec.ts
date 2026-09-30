import { test, expect } from "@playwright/test";

test.describe("E2E AST Query Rewrite Workflow (POST /api/rewrite)", () => {
  test("rewrites non-sargable query into range bounds with side-by-side SQL diff", async ({ page }) => {
    await page.goto("/rewrite");
    await expect(page.getByRole("heading", { name: /AST Query Rewriter/i })).toBeVisible();

    const rewriteBtn = page.getByRole("button", { name: /Rewrite Query/i });
    await rewriteBtn.click();

    // Verify rewrite results render
    await expect(page.getByText(/Rewrite Result: Transformed/i)).toBeVisible({ timeout: 15000 });
    await expect(page.getByText(/QUERY REWRITTEN/i)).toBeVisible();
    await expect(page.getByText(/BEFORE \(ORIGINAL\)/i)).toBeVisible();
    await expect(page.getByText(/AFTER \(OPTIMIZED\)/i)).toBeVisible();
    await expect(page.getByText(/Applied Transformations/i)).toBeVisible();
  });
});
