import { test, expect } from "@playwright/test";

test.describe("E2E Navigation & Header Controls", () => {
  test("loads home page with active navbar and green backend indicator", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("header")).toBeVisible();
    await expect(page.getByText("🛠️ SQL Optimizer QA Harness")).toBeVisible();
    await expect(page.getByText(/API Online/i)).toBeVisible({ timeout: 15000 });
  });

  test("navigates through all 8 pages seamlessly via top navigation bar", async ({ page }) => {
    await page.goto("/");

    // 1. Analyze
    await expect(page.getByRole("heading", { name: /Query Analysis/i })).toBeVisible();

    // 2. Score
    await page.click("text=📊 Score");
    await expect(page).toHaveURL(/.*score/);
    await expect(page.getByRole("heading", { name: /Performance Scoring/i })).toBeVisible();

    // 3. Recommendations
    await page.click("text=💡 Recommendations");
    await expect(page).toHaveURL(/.*recommendations/);
    await expect(page.getByRole("heading", { name: /Index Recommendations/i })).toBeVisible();

    // 4. Rewrite
    await page.click("text=🔄 Rewrite");
    await expect(page).toHaveURL(/.*rewrite/);
    await expect(page.getByRole("heading", { name: /AST Query Rewriter/i })).toBeVisible();

    // 5. Execution Plan
    await page.click("text=🌳 Execution Plan");
    await expect(page).toHaveURL(/.*execution-plan/);
    await expect(page.getByRole("heading", { name: /Execution Plan Visualizer/i })).toBeVisible();

    // 6. Simulate Index
    await page.click("text=🧪 Simulate Index");
    await expect(page).toHaveURL(/.*simulate-index/);
    await expect(page.getByRole("heading", { name: /Index Impact Simulator/i })).toBeVisible();

    // 7. Sample Queries
    await page.click("text=📁 Sample Queries");
    await expect(page).toHaveURL(/.*sample-queries/);
    await expect(page.getByRole("heading", { name: /Sample Queries Catalog/i })).toBeVisible();

    // 8. Health
    await page.click("text=🩺 Health");
    await expect(page).toHaveURL(/.*health/);
    await expect(page.getByRole("heading", { name: /System Health & Connectivity/i })).toBeVisible();

    // Return to Analyze
    await page.click("text=⚡ Analyze");
    await expect(page).toHaveURL(/.*\//);
    await expect(page.getByRole("heading", { name: /Query Analysis/i })).toBeVisible();
  });
});
