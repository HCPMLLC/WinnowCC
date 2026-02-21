import { test, expect } from "@playwright/test";
import {
  generateTestEmail,
  signUpViaAPI,
  signUpAndOnboard,
} from "./helpers/auth";

test.describe("Dashboard journey", () => {
  test("shows dashboard metrics after onboarding", async ({ page }) => {
    const email = generateTestEmail();
    await signUpAndOnboard(page, email, "TestPassword123!");

    await page.goto("/dashboard");
    await expect(page).toHaveURL(/\/dashboard/, { timeout: 10_000 });

    // Verify key metric headings are visible
    await expect(page.getByText("Dashboard")).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText("Profile Completeness")).toBeVisible();
    await expect(page.getByText("Qualified Jobs")).toBeVisible();
  });

  test("unauthenticated user redirects to login", async ({ page }) => {
    await page.goto("/dashboard");
    await expect(page).toHaveURL(/\/(login\?redirect=|\?redirect=)/, {
      timeout: 10_000,
    });
  });

  test("incomplete onboarding redirects to onboarding", async ({ page }) => {
    const email = generateTestEmail();
    await signUpViaAPI(page, email, "TestPassword123!");

    await page.goto("/dashboard");
    await expect(page).toHaveURL(/\/onboarding/, { timeout: 10_000 });
  });

  test("dashboard shows navigation links", async ({ page }) => {
    const email = generateTestEmail();
    await signUpAndOnboard(page, email, "TestPassword123!");

    await page.goto("/dashboard");
    await expect(page).toHaveURL(/\/dashboard/, { timeout: 10_000 });

    // Verify key navigation elements are present
    await expect(
      page.getByRole("link", { name: /match|job/i }).first(),
    ).toBeVisible({ timeout: 10_000 });
  });
});
